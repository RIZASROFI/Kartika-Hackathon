"""Utilitas teks yang dipakai seluruh modul analisis heuristik."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-ÿ0-9]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(?<!\w)#\w+", re.UNICODE)
MENTION_RE = re.compile(r"(?<!\w)@\w+", re.UNICODE)

LEVELS = (
    (75, "kritis"),
    (50, "tinggi"),
    (25, "sedang"),
    (0, "rendah"),
)


def risk_level(score: float) -> str:
    for threshold, label in LEVELS:
        if score >= threshold:
            return label
    return "rendah"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def word_count(text: str) -> int:
    return len(words(text))


def sentences(text: str) -> list[str]:
    parts = [normalize_whitespace(part) for part in SENTENCE_SPLIT_RE.split(text or "")]
    return [part for part in parts if len(part) > 1]


def caps_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def exclamation_ratio(text: str) -> float:
    total = len(words(text))
    if total == 0:
        return 0.0
    return (text.count("!") / total) * 100


def sentence_length_cv(text: str) -> float:
    lengths = [len(words(sentence)) for sentence in sentences(text)]
    lengths = [length for length in lengths if length > 0]
    if len(lengths) < 3:
        return 1.0
    mean = statistics.fmean(lengths)
    if mean == 0:
        return 1.0
    return statistics.pstdev(lengths) / mean


def shingles(text: str, size: int = 4) -> set[str]:
    tokens = [token.lower() for token in words(text)]
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


INFLECTION_PREFIXES = (
    "memper",
    "diper",
    "member",
    "diber",
    "menge",
    "penge",
    "meng",
    "meny",
    "mem",
    "men",
    "pem",
    "pen",
    "ber",
    "ter",
    "di",
    "ke",
    "se",
    "me",
    "pe",
    "be",
)

INFLECTION_SUFFIXES = ("kannya", "annya", "nya", "kan", "an", "i", "lah", "kah", "")

TOKEN_RE = re.compile(r"[a-z]+")


def _token_matches(token: str, term: str) -> bool:
    """Cocokkan kata berimbuhan tanpa menangkap kata lain yang kebetulan berawalan sama."""
    for prefix in ("", *INFLECTION_PREFIXES):
        if prefix and not token.startswith(prefix):
            continue
        remainder = token[len(prefix) :]
        if not remainder.startswith(term):
            continue
        tail = remainder[len(term) :]
        if tail in INFLECTION_SUFFIXES:
            return True
    return False


def count_hits(text: str, terms: tuple[str, ...] | list[str]) -> tuple[int, list[str]]:
    """Hitung kemunculan istilah, toleran terhadap imbuhan bahasa Indonesia.

    Satu kata hanya dihitung sekali walau cocok dengan beberapa istilah; istilah
    terpanjang dipakai agar “pengkhianatan” tidak dihitung ganda sebagai “khianat”.
    """
    lowered = (text or "").lower()
    word_terms = [term.lower() for term in terms if " " not in term]
    phrase_terms = [term.lower() for term in terms if " " in term]
    counts: dict[str, int] = {}

    for token in TOKEN_RE.findall(lowered):
        best: str | None = None
        for term in word_terms:
            if _token_matches(token, term) and (best is None or len(term) > len(best)):
                best = term
        if best is not None:
            counts[best] = counts.get(best, 0) + 1

    for phrase in phrase_terms:
        found = len(re.findall(rf"\b{re.escape(phrase)}\b", lowered))
        if found:
            counts[phrase] = counts.get(phrase, 0) + found

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return sum(counts.values()), [f"{term} (×{found})" for term, found in ordered]


@dataclass
class SignalResult:
    category: str
    title: str
    score: int
    level: str
    confidence: float
    explanation: str
    details: list[str] = field(default_factory=list)


def make_signal(
    *,
    category: str,
    title: str,
    score: float,
    confidence: float,
    explanation: str,
    details: list[str],
) -> SignalResult:
    bounded = max(0, min(100, int(round(score))))
    return SignalResult(
        category=category,
        title=title,
        score=bounded,
        level=risk_level(bounded),
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        explanation=explanation,
        details=details,
    )


@dataclass
class ClaimResult:
    text: str
    verdict: str
    rationale: str


def extract_claims(text: str, hoax_score: int) -> list[ClaimResult]:
    """Ambil kalimat yang paling menyerupai klaim untuk ditinjau manusia."""
    candidates: list[tuple[int, str]] = []
    numeric = re.compile(r"\b\d{1,3}(?:[.,]\d+)?\s?(%|persen|juta|miliar|triliun|ribu|orang|hari)\b", re.I)
    claim_markers = (
        "akan", "telah", "resmi", "dilarang", "dihapus", "diganti", "naik", "turun",
        "bansos", "subsidi", "kebijakan", "aturan", "kabar", "menurut", "dinyatakan",
        "benar", "salah", "palsu", "berbahaya", "mengandung", "ditemukan",
    )
    for sentence in sentences(text):
        length = len(sentence)
        if length < 40 or length > 340:
            continue
        lowered = sentence.lower()
        score = 0
        if numeric.search(lowered):
            score += 2
        score += sum(1 for marker in claim_markers if marker in lowered)
        if re.search(r"\b(sebarkan|viralkan|buruan|bagikan)\b", lowered):
            score += 2
        if score >= 2:
            candidates.append((score, sentence))

    candidates.sort(key=lambda item: (-item[0], -len(item[1])))
    results: list[ClaimResult] = []
    for _, sentence in candidates[:3]:
        if hoax_score >= 60:
            verdict = "terindikasi_menyesatkan"
            rationale = (
                "Kalimat memuat penanda klaim yang tidak disertai atribusi sumber yang dapat "
                "ditelusuri. Verdict ini bersifat indikatif dan wajib diverifikasi manual."
            )
        elif hoax_score >= 35:
            verdict = "perlu_verifikasi"
            rationale = (
                "Klaim belum memiliki bukti pendukung yang tervalidasi. Perlu pencocokan dengan "
                "sumber resmi atau pemberitaan kredibel."
            )
        else:
            verdict = "belum_diverifikasi"
            rationale = (
                "Klaim diambil otomatis sebagai kandidat. Platform belum melakukan pencocokan "
                "fakta eksternal, sehingga statusnya belum dapat ditetapkan."
            )
        results.append(ClaimResult(text=sentence, verdict=verdict, rationale=rationale))
    return results
