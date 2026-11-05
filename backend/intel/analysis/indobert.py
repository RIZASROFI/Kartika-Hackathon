"""Sinyal pembanding dari model IndoBERT lokal `cynteltika_indobert_v1`.

Model ini **tidak** menentukan verdict analisis. `pipeline.assess_signals`
tetap memakai sinyal heuristik sebagai satu-satunya penentu status, karena
model dilatih pada dua kelompok penerbit (TurnBackHoax vs media arus utama)
sehingga skornya peka terhadap gaya penulisan, bukan hanya kebenaran isi.

Bobot dimuat sekali per proses (lazy, thread-safe). Ketergantungan berat
(`torch`, `transformers`) diimpor di dalam loader agar `manage.py` tetap jalan
di lingkungan yang belum memasangnya.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from intel.analysis.text_stats import (
    VERDICT_HOAX_THRESHOLD,
    VERDICT_VERIFY_THRESHOLD,
    SignalResult,
    make_signal,
    normalize_whitespace,
    word_count,
)

logger = logging.getLogger(__name__)

CATEGORY = "indobert"
MODEL_VERSION = "cynteltika_indobert_v1"
SIGNAL_TITLE = "Sinyal Model IndoBERT"

# Dipakai hanya bila metadata/label_mapping.json tidak terbaca. Urutan ini
# sudah diverifikasi terhadap evaluation/test_predictions.xlsx: 0 = Hoax.
FALLBACK_LABELS = {0: "Hoax", 1: "Fact"}

_load_lock = threading.Lock()
_bundle: ModelBundle | None = None
_load_failed = False


@dataclass(frozen=True)
class ModelBundle:
    tokenizer: object
    model: object
    torch: object
    device: str
    labels: dict[int, str]

    @property
    def hoax_index(self) -> int | None:
        for index, label in self.labels.items():
            if label.strip().lower() == "hoax":
                return index
        return None


def _setting(name: str, default):
    return getattr(settings, name, default)


def _paths() -> tuple[Path, Path]:
    """Kembalikan (folder artefak Hugging Face, folder metadata)."""
    root = Path(str(_setting("INDOBERT_MODEL_DIR", ""))).expanduser()
    hf_dir = root / "model" if (root / "model" / "config.json").is_file() else root
    meta_dir = root / "metadata"
    if not meta_dir.is_dir():
        meta_dir = hf_dir.parent / "metadata"
    return hf_dir, meta_dir


def is_enabled() -> bool:
    return bool(_setting("INDOBERT_ENABLED", False))


def is_available() -> bool:
    """Aktif secara konfigurasi dan artefak model benar-benar ada di disk."""
    if not is_enabled():
        return False
    hf_dir, _ = _paths()
    return (hf_dir / "config.json").is_file() and (hf_dir / "model.safetensors").is_file()


def _read_labels(meta_dir: Path) -> dict[int, str]:
    try:
        raw = json.loads((meta_dir / "label_mapping.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(FALLBACK_LABELS)
    labels = {
        int(key): value
        for key, value in raw.items()
        if str(key).isdigit() and isinstance(value, str)
    }
    return labels or dict(FALLBACK_LABELS)


def load_bundle() -> ModelBundle | None:
    """Muat tokenizer + bobot sekali per proses; kegagalan di-cache."""
    global _bundle, _load_failed

    if _bundle is not None:
        return _bundle
    if _load_failed:
        return None

    with _load_lock:
        if _bundle is not None:
            return _bundle
        if _load_failed:
            return None

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            logger.warning(
                "indobert_dependency_missing",
                extra={"extra_fields": {"error": str(exc)}},
            )
            _load_failed = True
            return None

        hf_dir, meta_dir = _paths()
        try:
            # local_files_only: server tidak boleh menggantung menunggu hub.
            tokenizer = AutoTokenizer.from_pretrained(str(hf_dir), local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(
                str(hf_dir), local_files_only=True
            )
            model.eval()
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device)
        except Exception as exc:  # noqa: BLE001 - sinyal opsional tidak boleh fatal
            logger.warning(
                "indobert_load_failed",
                extra={"extra_fields": {"error": str(exc), "model_dir": str(hf_dir)}},
            )
            _load_failed = True
            return None

        _bundle = ModelBundle(
            tokenizer=tokenizer,
            model=model,
            torch=torch,
            device=device,
            labels=_read_labels(meta_dir),
        )
        logger.info(
            "indobert_loaded",
            extra={
                "extra_fields": {
                    "model": MODEL_VERSION,
                    "device": device,
                    "model_dir": str(hf_dir),
                }
            },
        )
        return _bundle


def reset_cache() -> None:
    """Kosongkan cache model (dipakai pengujian)."""
    global _bundle, _load_failed

    with _load_lock:
        _bundle = None
        _load_failed = False


def _window_ids(
    token_ids: list[int], window: int, max_chunks: int
) -> tuple[list[list[int]], bool, int]:
    """Potong id token menjadi jendela berukuran tetap tanpa overlap."""
    size = max(16, window)
    chunks = [token_ids[start : start + size] for start in range(0, len(token_ids), size)]
    return chunks[: max(1, max_chunks)], len(chunks) > max_chunks, len(chunks)


def _predict(bundle: ModelBundle, texts: list[str]) -> list[list[float]]:
    torch = bundle.torch
    batch_size = max(1, int(_setting("INDOBERT_BATCH_SIZE", 4)))
    distributions: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = bundle.tokenizer(
            texts[start : start + batch_size],
            padding=True,
            truncation=True,
            max_length=max(64, int(_setting("INDOBERT_MAX_TOKENS", 512))),
            return_tensors="pt",
        )
        batch = {key: value.to(bundle.device) for key, value in batch.items()}
        with torch.no_grad():
            logits = bundle.model(**batch).logits
        distributions.extend(torch.softmax(logits.float(), dim=-1).cpu().tolist())
    return distributions


def _explanation(score: float) -> str:
    if score >= VERDICT_HOAX_THRESHOLD:
        return (
            "Model IndoBERT lokal menilai konten ini cenderung hoax. Skor ini hanya "
            "pembanding: status analisis tetap ditentukan sinyal heuristik."
        )
    if score >= VERDICT_VERIFY_THRESHOLD:
        return (
            "Model IndoBERT lokal menilai konten ini ambigu; probabilitas hoax tidak "
            "dominan. Klaim di dalamnya tetap perlu diverifikasi manual."
        )
    return (
        "Model IndoBERT lokal menilai konten ini cenderung faktual. Model tidak "
        "memverifikasi kebenaran isi, hanya kemiripan dengan pola korpus latihnya."
    )


def analyze_with_model(text: str, title: str | None = None) -> SignalResult | None:
    """Kembalikan sinyal model, atau None bila model tidak aktif/tersedia/gagal."""
    if not is_available():
        return None

    bundle = load_bundle()
    if bundle is None:
        return None

    hoax_index = bundle.hoax_index
    if hoax_index is None:
        logger.warning(
            "indobert_label_missing",
            extra={"extra_fields": {"labels": bundle.labels}},
        )
        return None

    corpus = normalize_whitespace(f"{title or ''} {text}")
    total_words = word_count(corpus)
    if not total_words:
        return None

    max_tokens = max(64, int(_setting("INDOBERT_MAX_TOKENS", 512)))
    token_ids = bundle.tokenizer(corpus, add_special_tokens=False)["input_ids"]
    windows, truncated, total_windows = _window_ids(
        token_ids, max_tokens - 2, int(_setting("INDOBERT_MAX_CHUNKS", 4))
    )
    if not windows:
        return None

    chunk_texts = [
        bundle.tokenizer.decode(window, skip_special_tokens=True) or corpus
        for window in windows
    ]
    try:
        distributions = _predict(bundle, chunk_texts)
    except Exception as exc:  # noqa: BLE001 - inference gagal tidak boleh fatal
        logger.warning(
            "indobert_inference_failed", extra={"extra_fields": {"error": str(exc)}}
        )
        return None
    if not distributions:
        return None

    hoax_probs = [
        float(row[hoax_index]) if hoax_index < len(row) else 0.0 for row in distributions
    ]
    worst = max(range(len(hoax_probs)), key=lambda index: hoax_probs[index])
    labelled = {
        bundle.labels.get(index, f"class_{index}"): float(value)
        for index, value in enumerate(distributions[worst])
    }
    dominant = max(labelled, key=labelled.get)
    score = hoax_probs[worst] * 100
    margin = abs(labelled.get("Hoax", 0.0) - labelled.get("Fact", 0.0))

    details = [
        "Label dominan {label} — Hoax {hoax:.1f}% · Fact {fact:.1f}%.".format(
            label=dominant,
            hoax=labelled.get("Hoax", 0.0) * 100,
            fact=labelled.get("Fact", 0.0) * 100,
        ),
        f"Dianalisis {len(chunk_texts)} jendela × maksimal {max_tokens} token "
        f"(teks {total_words} kata).",
    ]
    if truncated:
        details.append(
            f"Sisa teks di luar {len(chunk_texts)} jendela pertama diabaikan agar waktu "
            f"analisis tetap terbatas (total {total_windows} jendela)."
        )
    details.extend(
        [
            f"Versi model {MODEL_VERSION}, perangkat {bundle.device}.",
            "Skor bersifat pembanding dan tidak mengubah verdict analisis.",
        ]
    )

    return make_signal(
        category=CATEGORY,
        title=SIGNAL_TITLE,
        score=score,
        confidence=0.5 + 0.5 * margin,
        explanation=_explanation(score),
        details=details,
    )
