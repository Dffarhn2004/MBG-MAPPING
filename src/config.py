"""Konstanta bobot & skenario skor prioritas MBG."""

from __future__ import annotations

# Bobot default (transparansi akademik — diuji lewat sensitivity analysis)
DEFAULT_WEIGHTS = {
    "stunting": 0.40,
    "kemiskinan": 0.25,
    "ikp": 0.20,  # inverted: IKP rendah = kerentanan tinggi
    "peserta_didik": 0.15,
}

WEIGHT_SCENARIOS = {
    "Fokus kerentanan": {
        "stunting": 0.40,
        "kemiskinan": 0.25,
        "ikp": 0.20,
        "peserta_didik": 0.15,
    },
    "Seimbang": {
        "stunting": 0.35,
        "kemiskinan": 0.25,
        "ikp": 0.15,
        "peserta_didik": 0.25,
    },
    "Fokus cakupan": {
        "stunting": 0.30,
        "kemiskinan": 0.20,
        "ikp": 0.15,
        "peserta_didik": 0.35,
    },
}

# Label kuartil — posisi relatif, bukan standar kebijakan
PRIORITY_QUARTILE_LABELS = {
    "Q4 Sangat Tinggi": "Sangat perlu ditingkatkan",
    "Q3 Tinggi": "Perlu ditingkatkan",
    "Q2 Sedang": "Perlu dipantau",
    "Q1 Rendah": "Relatif tidak prioritas",
}

# alias pendek untuk filter/warna
PRIORITY_SHORT = {
    "Q4 Sangat Tinggi": "Sangat Tinggi",
    "Q3 Tinggi": "Tinggi",
    "Q2 Sedang": "Sedang",
    "Q1 Rendah": "Rendah",
}

PRIORITY_LABELS = PRIORITY_QUARTILE_LABELS  # backward compat

CLUSTER_NAME_TEMPLATES = [
    "Gizi buruk, kemiskinan tinggi, IKP rendah",
    "Populasi siswa besar, risiko sosial sedang",
    "Gizi sedang, ketahanan pangan rendah",
    "Kondisi relatif baik",
    "Risiko campuran / transisi",
    "Kerentanan tinggi dengan cakupan sedang",
]

# Total kab/kota referensi IKP master (setelah cleaning)
REFERENCE_WILAYAH_TOTAL = 514

METHODOLOGY_NOTES = {
    "peserta_didik": (
        "Kolom 'Jumlah Peserta Didik' diambil dari portal Residu Data Induk "
        "Kemendikdasmen, tetapi merupakan **total peserta didik** (bukan hitungan "
        "residu NISN/kependudukan). Total nasional ~70 juta — konsisten dengan "
        "populasi siswa lintas jenjang, bukan orde residual."
    ),
    "ikp_invert": (
        "Nilai IKP dibalik setelah normalisasi min-max karena IKP lebih tinggi "
        "berarti ketahanan pangan lebih baik; IKP rendah menaikkan skor kerentanan."
    ),
    "kuartil": (
        "Kategori prioritas memakai kuartil skor (qcut): posisi relatif antarwilayah "
        "dalam dataset, bukan batas standar kebijakan nasional."
    ),
    "skor": (
        "Skor 0–100 adalah skor relatif hasil normalisasi gabungan indikator. "
        "Bukan persentase kebutuhan dan bukan estimasi anggaran."
    ),
}
