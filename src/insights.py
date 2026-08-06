"""Narasi insight dan rekomendasi untuk dashboard early warning MBG."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import DECISION_RECOMMENDATIONS

FACTOR_KEYS = {
    "stunting": "contrib_stunting",
    "kemiskinan": "contrib_kemiskinan",
    "ikp_risk": "contrib_ikp",
}

FACTOR_LABELS = {
    "stunting": "stunting",
    "kemiskinan": "kemiskinan",
    "ikp_risk": "kerawanan pangan",
}

FACTOR_RECOMMENDATIONS = {
    "stunting": (
        "Perkuat intervensi gizi, pemantauan pertumbuhan, dan evaluasi kualitas menu."
    ),
    "kemiskinan": (
        "Integrasikan peningkatan MBG dengan dukungan sosial ekonomi keluarga rentan."
    ),
    "ikp_risk": (
        "Perkuat rantai pasok pangan lokal dan ketahanan bahan pangan wilayah."
    ),
    "Stunting": (
        "Perkuat intervensi gizi, pemantauan pertumbuhan, dan evaluasi kualitas menu."
    ),
    "Kemiskinan": (
        "Integrasikan peningkatan MBG dengan dukungan sosial ekonomi keluarga rentan."
    ),
    "Kerawanan pangan": (
        "Perkuat rantai pasok pangan lokal dan ketahanan bahan pangan wilayah."
    ),
}


def status_vs_national(
    value: float,
    national: float,
    *,
    higher_is_worse: bool = True,
) -> str:
    if pd.isna(value) or pd.isna(national) or national == 0:
        return "Tidak tersedia"

    if higher_is_worse:
        if value > national * 1.5:
            return "Jauh di atas rata-rata"
        if value > national:
            return "Di atas rata-rata"
        if value < national * 0.85:
            return "Di bawah rata-rata"
        return "Mendekati rata-rata"

    if value < national * 0.85:
        return "Lebih rendah"
    if value < national:
        return "Sedikit lebih rendah"
    if value > national * 1.15:
        return "Lebih tinggi"
    return "Mendekati rata-rata"


def dominant_factor(row: pd.Series) -> str:
    if "dominant_factor" in row and pd.notna(row.get("dominant_factor")):
        return str(row["dominant_factor"])
    scores = {key: float(row.get(col, 0) or 0) for key, col in FACTOR_KEYS.items()}
    key = max(scores, key=scores.get)
    return {
        "stunting": "Stunting",
        "kemiskinan": "Kemiskinan",
        "ikp_risk": "Kerawanan pangan",
    }.get(key, key)


def contribution_breakdown(row: pd.Series) -> dict[str, float]:
    return {
        "Stunting": float(row.get("contrib_stunting", 0) or 0),
        "Kemiskinan": float(row.get("contrib_kemiskinan", 0) or 0),
        "Kerawanan pangan": float(row.get("contrib_ikp", 0) or 0),
    }


def contribution_total(row: pd.Series) -> float:
    return sum(contribution_breakdown(row).values())


def recommendation_for_decision(status: str) -> str:
    return DECISION_RECOMMENDATIONS.get(
        status,
        "Sesuaikan intervensi dengan kondisi lokal dan kelengkapan data operasional.",
    )


def recommendation_for_factor(factor: str) -> str:
    return FACTOR_RECOMMENDATIONS.get(
        factor,
        "Sesuaikan intervensi dengan faktor kerentanan yang paling menonjol di wilayah.",
    )


def generate_region_insight(row: pd.Series, national: dict | None = None) -> str:
    name = str(row.get("kabupaten_kota_normalized") or row.get("kabupaten_kota") or "Wilayah ini")
    status = str(row.get("decision_status") or row.get("prioritas_kategori") or "")
    factor = dominant_factor(row)
    cur = float(row.get("current_score_2024") or row.get("priority_score") or 0)
    proj = float(row.get("projected_score_2025") or cur)
    change = proj - cur
    trend = str(row.get("trend_status") or "")
    cq = str(row.get("current_quartile") or "")
    pq = str(row.get("projected_quartile") or "")

    direction = "naik" if change >= 0 else "turun"
    abs_ch = abs(change)

    parts = [
        f"{name} berstatus **{status}**.",
        f"Skor prioritas 2024 sebesar {cur:.1f} ({cq or '—'}) dan proyeksi 2025 "
        f"{proj:.1f} ({pq or '—'}), berubah {direction} {abs_ch:.1f} poin.",
    ]
    if trend:
        parts.append(f"Tren 2022–2024: {trend}.")
    parts.append(f"Faktor dominan pada skor saat ini: {factor}.")
    if national:
        stunt = float(row.get("stunting_pct", 0) or 0)
        miskin = float(
            row.get("persen_penduduk_miskin")
            or row.get("kemiskinan_pct")
            or 0
        )
        ikp = float(row.get("ikp") or row.get("ikp_score") or 0)
        extra = []
        if stunt > float(national.get("stunting_pct", 0) or 0):
            extra.append("stunting di atas rata-rata panel")
        if miskin > float(national.get("persen_penduduk_miskin", 0) or 0):
            extra.append("kemiskinan di atas rata-rata panel")
        if ikp < float(national.get("ikp", 999) or 999):
            extra.append("IKP di bawah rata-rata panel")
        if extra:
            parts.append("Konteks: " + ", ".join(extra) + ".")
    parts.append(
        "Hasil merupakan prioritas relatif dan perlu dilengkapi data operasional "
        "sebelum keputusan anggaran."
    )
    return " ".join(parts)


def executive_insight(df: pd.DataFrame) -> str:
    if df.empty:
        return "Tidak ada wilayah yang sesuai dengan filter saat ini."
    n_urgent = int((df["decision_status"] == "Tingkatkan segera").sum())
    n_expand = int((df["decision_status"] == "Persiapkan ekspansi").sum())
    n_worse = int(
        df["score_change"].fillna(0).gt(0).sum()
        if "score_change" in df.columns
        else 0
    )
    top = df.nsmallest(1, "current_rank" if "current_rank" in df.columns else "rank").iloc[0]
    name = top.get("kabupaten_kota_normalized") or top.get("kabupaten_kota")
    return (
        f"{n_urgent} wilayah berstatus tingkatkan segera dan {n_expand} perlu "
        f"persiapan ekspansi. {n_worse} wilayah memiliki proyeksi risiko meningkat. "
        f"Prioritas tertinggi: {name}."
    )


def decision_counts(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty or "decision_status" not in df.columns:
        return {}
    vc = df["decision_status"].value_counts().to_dict()
    return {
        "tingkatkan_segera": int(vc.get("Tingkatkan segera", 0)),
        "persiapkan_ekspansi": int(vc.get("Persiapkan ekspansi", 0)),
        "pertahankan_pantau": int(vc.get("Pertahankan dan pantau", 0)),
        "pemantauan_rutin": int(vc.get("Pemantauan rutin", 0)),
        "risiko_meningkat": int(df["score_change"].fillna(0).gt(0).sum())
        if "score_change" in df.columns
        else 0,
    }
