"""Konstanta bobot, status keputusan, dan label proyeksi (display layer).

Catatan: formula skor/proyeksi di scoring.py tidak diubah di sini.
Layer ini hanya merapikan label, warna, dan salinan untuk dashboard.
"""

from __future__ import annotations

# Bobot renorm dari 40:25:20 (tanpa peserta didik) → 47:29:24
DEFAULT_WEIGHTS = {
    "stunting": 0.47,
    "kemiskinan": 0.29,
    "ikp": 0.24,
}

ANALYSIS_YEARS = (2022, 2023, 2024)
ACTUAL_END_YEAR = 2024
CURRENT_YEAR = ACTUAL_END_YEAR
PROJECTION_YEAR = 2025
PROJECTION_LABEL = f"Simulasi proyeksi {PROJECTION_YEAR} berbasis data 2022–{ACTUAL_END_YEAR}"

# Threshold early warning (poin skor) — sama dengan pipeline scoring
EARLY_WARNING_DELTA = 10.0

# Status keputusan (label baru, decision-first)
STATUS_PRIORITAS_UTAMA = "Prioritas utama"
STATUS_EARLY_WARNING = "Early warning"
STATUS_PERTAHANKAN = "Pertahankan intervensi"
STATUS_PEMANTAUAN = "Pemantauan rutin"

DECISION_STATUS_ORDER = [
    STATUS_PRIORITAS_UTAMA,
    STATUS_EARLY_WARNING,
    STATUS_PERTAHANKAN,
    STATUS_PEMANTAUAN,
]

# Pemetaan label lama di analysis_ready.csv → label baru
LEGACY_STATUS_MAP = {
    "Tingkatkan segera": STATUS_PRIORITAS_UTAMA,
    "Persiapkan ekspansi": STATUS_EARLY_WARNING,
    "Pertahankan dan pantau": STATUS_PERTAHANKAN,
    "Pemantauan rutin": STATUS_PEMANTAUAN,
    STATUS_PRIORITAS_UTAMA: STATUS_PRIORITAS_UTAMA,
    STATUS_EARLY_WARNING: STATUS_EARLY_WARNING,
    STATUS_PERTAHANKAN: STATUS_PERTAHANKAN,
    STATUS_PEMANTAUAN: STATUS_PEMANTAUAN,
}

DECISION_RECOMMENDATIONS = {
    STATUS_PRIORITAS_UTAMA: (
        "Prioritaskan verifikasi lapangan dan peningkatan cakupan MBG."
    ),
    STATUS_EARLY_WARNING: (
        "Siapkan validasi lapangan, kapasitas layanan, dan rencana ekspansi bertahap."
    ),
    STATUS_PERTAHANKAN: (
        "Pertahankan intervensi dan monitor agar perbaikan berlanjut."
    ),
    STATUS_PEMANTAUAN: (
        "Lakukan pemantauan berkala. Belum menjadi prioritas ekspansi dibanding "
        "wilayah dengan risiko nasional lebih tinggi."
    ),
}

DECISION_ACTIONS = {
    STATUS_PRIORITAS_UTAMA: "Verifikasi & tingkatkan",
    STATUS_EARLY_WARNING: "Siapkan ekspansi",
    STATUS_PERTAHANKAN: "Pertahankan program",
    STATUS_PEMANTAUAN: "Monitor rutin",
}

STATUS_COLORS = {
    STATUS_PRIORITAS_UTAMA: "#991B1B",  # merah tua
    STATUS_EARLY_WARNING: "#EA580C",  # oranye
    STATUS_PERTAHANKAN: "#1D4ED8",  # biru
    STATUS_PEMANTAUAN: "#15803D",  # hijau
    "Data tidak lengkap": "#94A3B8",  # abu-abu
    "Tanpa data": "#94A3B8",
    "Di luar filter": "#E2E8F0",
}

STATUS_ICONS = {
    STATUS_PRIORITAS_UTAMA: "🔴",
    STATUS_EARLY_WARNING: "🟠",
    STATUS_PERTAHANKAN: "🔵",
    STATUS_PEMANTAUAN: "🟢",
}

STATUS_TITLE_WHY = {
    STATUS_PRIORITAS_UTAMA: "Mengapa wilayah ini menjadi prioritas?",
    STATUS_EARLY_WARNING: "Mengapa wilayah ini perlu diantisipasi?",
    STATUS_PERTAHANKAN: "Mengapa intervensi perlu dipertahankan?",
    STATUS_PEMANTAUAN: "Mengapa wilayah ini cukup dipantau?",
}

TREND_STATUS_LABELS = {
    "memburuk_cepat": "Memburuk cepat",
    "cenderung_memburuk": "Cenderung memburuk",
    "relatif_stabil": "Relatif stabil",
    "membaik": "Membaik",
}

REFERENCE_WILAYAH_TOTAL = 514

METHODOLOGY_NOTES = {
    "indikator": (
        "Analisis memakai tiga indikator: prevalensi stunting, persentase penduduk "
        "miskin (P0), dan Indeks Ketahanan Pangan (IKP). Data peserta didik tidak "
        "dimasukkan pada versi timeline ini."
    ),
    "percentile": (
        "Risiko dihitung dengan percentile rank per indikator per tahun (0–100), "
        "bukan min-max gabungan multi-tahun."
    ),
    "ikp_invert": (
        "IKP lebih tinggi berarti ketahanan pangan lebih baik. Kerawanan pangan "
        "dihitung sebagai kebalikan percentile IKP."
    ),
    "bobot": (
        "Skor Prioritas = 47% risiko stunting + 29% risiko kemiskinan + "
        "24% risiko kerawanan pangan."
    ),
    "proyeksi": (
        f"{PROJECTION_LABEL}. Dipakai sebagai early warning / proyeksi indikatif, "
        "bukan forecast operasional jangka panjang."
    ),
    "keputusan": (
        "Status keputusan menggabungkan kuartil skor aktual dan kuartil proyeksi, "
        f"ditambah aturan early warning jika lonjakan skor ≥ {EARLY_WARNING_DELTA:.0f} poin."
    ),
    "skor": (
        "Skor 0–100 adalah prioritas relatif antarwilayah, bukan persentase kebutuhan "
        "MBG dan bukan estimasi anggaran."
    ),
}

# Backward-compat aliases used by scoring (label lama)
DECISION_STATUS = {
    "tingkatkan_segera": STATUS_PRIORITAS_UTAMA,
    "persiapkan_ekspansi": STATUS_EARLY_WARNING,
    "pertahankan_pantau": STATUS_PERTAHANKAN,
    "pemantauan_rutin": STATUS_PEMANTAUAN,
}
