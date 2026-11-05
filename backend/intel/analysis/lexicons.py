"""Leksikon indikator untuk analisis heuristik bahasa Indonesia.

Daftar ini sengaja dibuat eksplisit dan dapat diaudit. Skor yang dihasilkan
bersifat indikatif, bukan penilaian kebenaran atau niat.
"""

SENSATIONAL_TERMS: tuple[str, ...] = (
    "viral", "heboh", "terungkap", "ternyata", "faktanya", "akhirnya terbongkar",
    "menggemparkan", "bikin geger", "diam-diam", "rahasia", "tidak banyak yang tahu",
    "mengagetkan", "bikin heboh",
)

URGENCY_TERMS: tuple[str, ...] = (
    "sebarkan", "viralkan", "jangan sampai", "buruan", "sebelum dihapus",
    "bagikan ke", "forward ke", "screenshot", "sebarluaskan", "segera sebarkan",
)

HEDGE_TERMS: tuple[str, ...] = (
    "kabarnya", "katanya", "konon", "menurut informasi yang beredar",
    "sumber terpercaya", "orang dalam", "dinilai", "diduga kuat",
)

ABSOLUTE_TERMS: tuple[str, ...] = (
    "satu-satunya", "100%", "tidak mungkin", "sudah pasti", "selamanya",
    "semua orang tahu", "pasti benar", "dijamin",
)

# Atribusi yang dapat ditelusuri: ada pihak konkret yang bisa dicek.
TRACEABLE_ATTRIBUTION_TERMS: tuple[str, ...] = (
    "dilansir", "pernyataan", "keterangan resmi", "juru bicara", "data dari",
    "dokumen", "rilis", "kutipan", "sumber resmi", "konferensi pers",
    "siaran pers", "laporan resmi",
)

# Atribusi kabur: terdengar seperti sumber, tetapi tidak menunjuk siapa pun.
# Narasi hoax sering memakai frasa ini justru untuk menutupi klaim tanpa sumber.
VAGUE_ATTRIBUTION_TERMS: tuple[str, ...] = (
    "menurut", "kata ", "berdasarkan", "sumber", "hasil penelitian",
)

OFFICIAL_SOURCE_PATTERN = (
    r"\b(kementerian|kemenkes|kemendikbud|kemenkeu|kpu|bawaslu|polri|polda|"
    r"pemprov|pemkot|pemkab|bnpb|bmkg|bank indonesia|ojk|kpk|bps|"
    r"presiden|menteri|gubernur|bupati|walikota|dinas|lembaga)\b"
)
