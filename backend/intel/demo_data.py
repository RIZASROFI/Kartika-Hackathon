"""Data demo sintetis KARTIKA Intel.

Semua tokoh, kebijakan, dan peristiwa di bawah ini fiktif dan hanya dipakai
untuk memperagakan kemampuan platform.
"""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class DemoItem:
    title: str
    publisher: str
    text: str
    hours_ago: int
    scenario: str


PEMADAMAN_CORE = (
    "Pemerintah akan memadamkan listrik secara nasional selama 3 hari mulai Senin depan. "
    "Kabarnya keputusan ini diambil diam-diam karena krisis energi yang tidak pernah diberitakan. "
    "Tidak ada satu pun media arus utama yang berani mengungkap fakta ini. "
    "Sebarkan pesan ini ke semua grup sebelum dihapus! "
    "Jangan sampai keluarga kita tidak siap menghadapi pemadaman. "
    "Forward ke sepuluh orang sekarang juga. "
    "Simpan air bersih dan makanan kering, isi daya semua perangkat, dan siapkan lilin. "
    "Jangan tunggu sampai listrik mati total baru panik. "
    "Buruan sebarkan sebelum pesan ini dihapus pihak yang tidak bertanggung jawab."
)

PAJAK_CORE = (
    "Pajak kendaraan akan naik 200 persen tahun depan. "
    "Kabarnya aturan ini sudah ditandatangani pejabat tinggi dan akan berlaku diam-diam tanpa sosialisasi. "
    "Semua pemilik mobil dan motor wajib membayar sebelum akhir tahun. "
    "Sebarkan info ini ke semua grup, jangan sampai kena denda. "
    "Pemerintah tidak pernah menjelaskan dasar kenaikan ini. "
    "Menurut informasi yang beredar, tarif baru dihitung dari nilai jual kendaraan."
)

GERUDUK_CORE = (
    "Kita sudah muak dengan rezim yang mengkhianati rakyat. "
    "Ayo kita geruduk gedung pemerintahan malam ini, jangan diam! "
    "Mereka penindas dan antek asing yang menguras kekayaan negeri. "
    "Gulingkan sekarang sebelum terlambat. "
    "Serukan ke semua orang, kerahkan massa sebanyak mungkin. "
    "Kita harus lawan sampai mereka tumbang. "
    "Sebarkan selebar mungkin, jangan sampai ada yang tidak tahu."
)


DEMO_ITEMS: tuple[DemoItem, ...] = (
    DemoItem(
        title="Studi Panel Surya Kampus Bandung Dorong Efisiensi 11 Persen",
        publisher="Jurnal Energi Terbuka",
        hours_ago=90,
        scenario="artikel_netral",
        text=(
            "Peneliti dari universitas di Bandung mempublikasikan studi tentang efisiensi panel surya "
            "pada atap gedung perkantoran. Menurut laporan penelitian yang dirilis pekan lalu, kombinasi "
            "pendinginan pasif dan sudut panel yang disesuaikan dapat meningkatkan keluaran energi hingga "
            "11 persen. Data dikumpulkan selama enam bulan dari tiga lokasi pengujian. Ketua tim peneliti "
            "menyatakan hasil ini masih perlu diuji pada skala lebih besar sebelum diterapkan secara "
            "komersial. Studi tersebut diterbitkan dalam jurnal energi terbarukan dan dapat diakses publik."
        ),
    ),
    DemoItem(
        title="Rekomendasi Produk Terbaik Minggu Ini",
        publisher="Kanal Promo",
        hours_ago=68,
        scenario="konten_promo_ai",
        text=(
            "Berikut adalah rekomendasi produk terbaik untuk Anda. Penting untuk dicatat bahwa kualitas "
            "adalah prioritas utama. Produk ini dirancang dengan teknologi mutakhir — ringan, praktis, "
            "dan tahan lama. Jangan lupa klik link di bio untuk mendapatkan harga spesial. Info lengkap "
            "tersedia di katalog kami. Bantu sebarkan ke teman dan keluarga. Pertama, pilih varian sesuai "
            "kebutuhan. Kedua, isi formulir pemesanan. Ketiga, konfirmasi pembayaran. Dengan demikian, "
            "pesanan Anda akan segera diproses. Selain itu, tersedia garansi resmi selama satu tahun. "
            "Secara keseluruhan, ini pilihan yang tepat. Saya harap ini membantu. "
            "#promo #diskon #murah #terlaris #viral"
        ),
    ),
    DemoItem(
        title="Gas 3 Kg Dihapus Bulan Depan, Warga Wajib Tukar Tabung",
        publisher="Warta Warga",
        hours_ago=50,
        scenario="hoaks_kebijakan",
        text=(
            "Kabar terbaru, gas elpiji 3 kilogram akan dihapus mulai bulan depan dan diganti tabung 5 "
            "kilogram. Kabarnya kebijakan ini sudah diputuskan tanpa konsultasi dengan pedagang. Semua "
            "warga wajib menukar tabung lama di kantor kelurahan dengan biaya administrasi. Jangan sampai "
            "kehabisan, buruan tukar sebelum stok habis. Sebarkan ke tetangga supaya tidak ada yang "
            "tertipu. Menurut orang dalam, harga tabung baru akan naik dua kali lipat."
        ),
    ),
    DemoItem(
        title="BMKG Imbau Waspada Hujan Lebat di Jawa Barat",
        publisher="Kabar Publik",
        hours_ago=44,
        scenario="artikel_netral",
        text=(
            "Berdasarkan keterangan resmi Badan Meteorologi, Klimatologi, dan Geofisika, hujan dengan "
            "intensitas sedang hingga lebat diperkirakan terjadi di sebagian wilayah Jawa Barat pada 26 "
            "hingga 28 Oktober. Menurut juru bicara BMKG, masyarakat diminta memantau kanal resmi untuk "
            "pembaruan informasi. Data dari sistem pemantauan menunjukkan peningkatan kelembapan udara di "
            "lapisan bawah. Pemerintah daerah menyiapkan posko darurat dan telah berkoordinasi dengan "
            "Badan Penanggulangan Bencana Daerah. Warga diimbau menghindari area rawan longsor dan tidak "
            "menyebarkan informasi yang belum terverifikasi."
        ),
    ),
    DemoItem(
        title="Seruan Geruduk Gedung Pemerintahan Malam Ini",
        publisher="Suara Jalanan",
        hours_ago=34,
        scenario="provokasi",
        text=(
            GERUDUK_CORE
            + " Bawa teman dan tetangga, jangan biarkan mereka tidur. "
            "Ini saatnya rakyat menunjukkan siapa yang berkuasa."
        ),
    ),
    DemoItem(
        title="Saatnya Rakyat Bertindak, Jangan Diam Saja",
        publisher="Kanal Warga",
        hours_ago=30,
        scenario="provokasi",
        text=(
            GERUDUK_CORE
            + " Anak muda harus di depan, jangan biarkan mereka tidur. "
            "Ini saatnya rakyat menunjukkan siapa yang berkuasa. Ayo bergerak, jangan ada yang tinggal di rumah."
        ),
    ),
    DemoItem(
        title="Pajak Kendaraan Naik 200 Persen Tahun Depan, Benarkah?",
        publisher="Lintas Ruang",
        hours_ago=26,
        scenario="hoaks_kebijakan",
        text=(
            PAJAK_CORE
            + " Buruan cek STNK masing-masing, sebelum didenda besar. "
            "Sumber terpercaya menyebut kebijakan ini sudah berjalan di beberapa daerah."
        ),
    ),
    DemoItem(
        title="Kenaikan Pajak Kendaraan 200 Persen, Warga Diminta Bersiap",
        publisher="Nusantara Watch",
        hours_ago=20,
        scenario="hoaks_kebijakan",
        text=(
            PAJAK_CORE
            + " Buruan cek STNK masing-masing dan siapkan dana. "
            "Sumber terpercaya menyebut kebijakan ini sudah berjalan di beberapa daerah."
        ),
    ),
    DemoItem(
        title="BREAKING: Listrik Nasional Akan Padam 3 Hari, Sebarkan Sebelum Dihapus",
        publisher="Warta Digital",
        hours_ago=14,
        scenario="hoaks_terkoordinasi",
        text=(
            "BREAKING! "
            + PEMADAMAN_CORE
            + " Kabarnya petugas akan memutus aliran tanpa pemberitahuan."
        ),
    ),
    DemoItem(
        title="Listrik Padam 3 Hari Mulai Senin, Ini yang Tidak Diberitakan Media",
        publisher="Lintas Ruang",
        hours_ago=10,
        scenario="hoaks_terkoordinasi",
        text=(
            PEMADAMAN_CORE
            + " Ini peringatan penting untuk semua warga. "
            "Kabarnya petugas akan memutus aliran tanpa pemberitahuan."
        ),
    ),
    DemoItem(
        title="Penting untuk Dicatat: Perkembangan AI dan Otomatisasi",
        publisher="Editorial Tekno",
        hours_ago=8,
        scenario="konten_ai",
        text=(
            "Penting untuk dicatat bahwa perkembangan kecerdasan artifisial telah membawa perubahan "
            "signifikan pada berbagai sektor. Pertama, otomatisasi proses bisnis meningkatkan efisiensi "
            "operasional. Kedua, analisis data berskala besar memungkinkan pengambilan keputusan yang "
            "lebih cepat. Ketiga, muncul tantangan baru terkait tata kelola dan transparansi. Selain itu, "
            "adopsi teknologi ini memerlukan kesiapan sumber daya manusia. Dengan demikian, organisasi "
            "perlu menyusun kerangka kebijakan yang jelas — termasuk evaluasi risiko — sebelum menerapkan "
            "sistem secara luas. Secara keseluruhan, pendekatan bertahap akan membantu mengurangi risiko. "
            "Sebagai kesimpulan, kolaborasi antara regulator, industri, dan akademisi menjadi kunci. "
            "Saya harap ini membantu."
        ),
    ),
    DemoItem(
        title="Peringatan: Pemadaman Listrik Nasional 3 Hari, Segera Sebarkan",
        publisher="Suara Publik",
        hours_ago=6,
        scenario="hoaks_terkoordinasi",
        text=(
            "Peringatan penting! "
            + PEMADAMAN_CORE
            + " Simpan air bersih dan makanan kering, isi daya semua perangkat."
        ),
    ),
    DemoItem(
        title="Bansos Rp 3 Juta untuk Semua Warga, Daftar Lewat Link Ini",
        publisher="Info Bantuan",
        hours_ago=3,
        scenario="penipuan_bansos",
        text=(
            "Bantuan sosial Rp 3 juta untuk semua warga bisa diambil lewat link berikut. Buruan daftar "
            "sebelum kuota habis! Cukup isi nama, NIK, dan nomor rekening. Jangan sampai tertipu pihak "
            "lain yang mengaku petugas. Sebarkan link ini ke semua grup keluarga supaya tidak ada yang "
            "ketinggalan. Program ini terbatas dan tidak diumumkan di televisi. Klik link, isi data, lalu "
            "tunggu dana masuk dalam 24 jam. Jangan lupa forward ke sepuluh orang agar pendaftaran "
            "diprioritaskan."
        ),
    ),
    DemoItem(
        title="Narasi Pengkhianatan Mewarnai Diskusi Kebijakan Baru",
        publisher="Pantau Wacana",
        hours_ago=1,
        scenario="provokasi_sedang",
        text=(
            "Narasi yang menyebut kebijakan baru sebagai bentuk pengkhianatan terhadap rakyat mulai "
            "menyebar. Beberapa unggahan menyerukan agar warga turun ke jalan dan mendesak pejabat mundur. "
            "Bahasa yang digunakan cenderung emosional, namun belum ditemukan ajakan kekerasan eksplisit. "
            "Unggahan lain membandingkan situasi saat ini dengan masa kelam dan menuduh lawan politik "
            "sebagai antek asing. Sebagian pesan meminta pembaca menyebarkan konten ke grup lain tanpa "
            "menyertakan sumber."
        ),
    ),
)
