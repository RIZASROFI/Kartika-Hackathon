"""Leksikon indikator untuk analisis heuristik bahasa Indonesia.

Daftar ini sengaja dibuat eksplisit dan dapat diaudit. Skor yang dihasilkan
bersifat indikatif, bukan penilaian kebenaran atau niat.
"""

PROVOCATION_GROUPS: dict[str, tuple[float, tuple[str, ...]]] = {
    "dehumanisasi": (
        3.0,
        (
            "anjing", "bangsat", "goblok", "idiot", "tolol", "monyet", "babi",
            "sampah masyarakat", "kafir", "setan", "binatang",
        ),
    ),
    "kekerasan": (
        3.0,
        (
            "bunuh", "bakar", "serang", "hancurkan", "ganyang", "habisi",
            "tumpas", "gempur", "sikat", "bantai", "rusak",
        ),
    ),
    "ajakan_makzul": (
        2.5,
        (
            "gulingkan", "kudeta", "makzulkan", "revolusi", "ganti presiden",
            "turunkan", "kudeta", "kerahkan massa", "demonstrasi besar",
        ),
    ),
    "mobilisasi": (
        2.0,
        (
            "sebarkan", "viralkan", "serukan", "ajak semua", "jangan diam",
            "ayo", "mari kita", "gabung", "kumpulkan", "geruduk", "kepung",
        ),
    ),
    "kami_vs_mereka": (
        1.5,
        (
            "antek", "pengkhianat", "khianat", "penjajah", "penindas", "musuh",
            "lawan", "mereka yang", "orang dalam", "kita harus",
        ),
    ),
    "ancaman": (
        1.0,
        (
            "ancaman", "bahaya besar", "darurat", "kiamat", "dihancurkan",
            "dikuasai asing", "kehancuran", "malapetaka",
        ),
    ),
}

ESCALATION_PATTERN = r"\b(ayo|mari|kita)\b.{0,40}\b(turun|serang|gempur|gulingkan|bakar|kepung|geruduk)\b"

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

ATTRIBUTION_TERMS: tuple[str, ...] = (
    "menurut", "kata ", "dilansir", "berdasarkan", "sumber", "pernyataan",
    "keterangan resmi", "data dari", "hasil penelitian", "dokumen", "rilis",
    "juru bicara", "kutipan",
)

OFFICIAL_SOURCE_PATTERN = (
    r"\b(kementerian|kemenkes|kemendikbud|kemenkeu|kpu|bawaslu|polri|polda|"
    r"pemprov|pemkot|pemkab|bnpb|bmkg|bank indonesia|ojk|kpk|bps|"
    r"presiden|menteri|gubernur|bupati|walikota|dinas|lembaga)\b"
)

AI_CONTENT_TERMS: tuple[str, ...] = (
    "sebagai model bahasa", "saya tidak dapat", "penting untuk dicatat",
    "sebagai kesimpulan", "dalam kesimpulan", "berikut adalah", "perlu diingat bahwa",
    "saya harap ini membantu", "secara keseluruhan", "pertama", "kedua", "ketiga",
    "selain itu", "dengan demikian", "sebagai asisten",
)

TEMPLATE_PHRASES: tuple[str, ...] = (
    "jangan lupa", "klik link", "cek bio", "info lengkap", "ikuti terus",
    "sumber terpercaya", "viral di", "bantu sebarkan",
)
