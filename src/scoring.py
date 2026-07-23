"""Fungsi scoring prioritas MBG."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import DEFAULT_WEIGHTS, PRIORITY_QUARTILE_LABELS


def minmax(series: pd.Series, invert: bool = False) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        out = pd.Series(np.zeros(len(s)), index=s.index, dtype=float)
    else:
        out = (s - lo) / (hi - lo)
    if invert:
        out = 1.0 - out
    return out.clip(0, 1) * 100.0


def compute_scores(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Hitung vulnerability, service need, dan priority score (0–100)."""
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}

    n_stunting = minmax(df["stunting_pct"], invert=False)
    n_kemiskinan = minmax(df["persen_penduduk_miskin"], invert=False)
    # IKP dibalik: rendah → kerentanan tinggi
    n_ikp = minmax(df["ikp"], invert=True)
    n_peserta = minmax(df["jumlah_peserta_didik"], invert=False)

    vuln_w = w["stunting"] + w["kemiskinan"] + w["ikp"]
    vulnerability_score = (
        n_stunting * (w["stunting"] / vuln_w)
        + n_kemiskinan * (w["kemiskinan"] / vuln_w)
        + n_ikp * (w["ikp"] / vuln_w)
    )
    service_need_score = n_peserta
    priority_score = (
        n_stunting * w["stunting"]
        + n_kemiskinan * w["kemiskinan"]
        + n_ikp * w["ikp"]
        + n_peserta * w["peserta_didik"]
    )
    contrib_stunting = n_stunting * w["stunting"]
    contrib_kemiskinan = n_kemiskinan * w["kemiskinan"]
    contrib_ikp = n_ikp * w["ikp"]
    contrib_peserta = n_peserta * w["peserta_didik"]
    rank = priority_score.rank(ascending=False, method="min").astype(int)

    # Kuartil: Q4 = skor tertinggi = prioritas relatif sangat tinggi
    try:
        prioritas_kategori = pd.qcut(
            priority_score,
            4,
            labels=["Q1 Rendah", "Q2 Sedang", "Q3 Tinggi", "Q4 Sangat Tinggi"],
        ).astype(str)
    except ValueError:
        prioritas_kategori = pd.cut(
            priority_score,
            bins=[-np.inf, 25, 50, 75, np.inf],
            labels=["Q1 Rendah", "Q2 Sedang", "Q3 Tinggi", "Q4 Sangat Tinggi"],
        ).astype(str)

    out = df.assign(
        n_stunting=n_stunting,
        n_kemiskinan=n_kemiskinan,
        n_ikp=n_ikp,
        n_peserta=n_peserta,
        vulnerability_score=vulnerability_score,
        service_need_score=service_need_score,
        priority_score=priority_score,
        contrib_stunting=contrib_stunting,
        contrib_kemiskinan=contrib_kemiskinan,
        contrib_ikp=contrib_ikp,
        contrib_peserta=contrib_peserta,
        rank=rank,
        prioritas_kategori=prioritas_kategori,
        rekomendasi=prioritas_kategori.map(PRIORITY_QUARTILE_LABELS),
        pct_stunting=df["stunting_pct"].rank(pct=True) * 100,
        pct_kemiskinan=df["persen_penduduk_miskin"].rank(pct=True) * 100,
        pct_ikp=df["ikp"].rank(pct=True) * 100,
        pct_peserta=df["jumlah_peserta_didik"].rank(pct=True) * 100,
        pct_priority=priority_score.rank(pct=True) * 100,
    )
    return out


def auto_reason(row: pd.Series, national: dict) -> str:
    """Alasan otomatis kenapa wilayah masuk prioritas tertentu."""
    reasons = []
    if row["stunting_pct"] > national["stunting_pct"]:
        reasons.append("prevalensi stunting berada di atas rata-rata nasional")
    if row["persen_penduduk_miskin"] > national["persen_penduduk_miskin"]:
        reasons.append("persentase kemiskinan berada di atas rata-rata nasional")
    if row["ikp"] < national["ikp"]:
        reasons.append("skor ketahanan pangan (IKP) relatif rendah")
    if row["jumlah_peserta_didik"] > national["jumlah_peserta_didik"]:
        reasons.append("jumlah peserta didik relatif besar (kebutuhan layanan tinggi)")

    kategori = row.get("prioritas_kategori", "prioritas")
    if not reasons:
        return (
            f"Wilayah ini masuk kategori {kategori} dengan kombinasi indikator "
            "yang relatif seimbang terhadap rata-rata nasional (dalam himpunan "
            "wilayah berdata lengkap)."
        )

    if len(reasons) == 1:
        joined = reasons[0]
    else:
        joined = ", ".join(reasons[:-1]) + f", sedangkan {reasons[-1]}"

    return (
        f"Wilayah ini memperoleh prioritas {kategori} karena {joined}. "
        f"Skor prioritas bersifat relatif (normalisasi antarwilayah), bukan "
        f"persentase kebutuhan absolut."
    )
