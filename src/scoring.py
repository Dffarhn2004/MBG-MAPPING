"""Scoring prioritas MBG: current, trend, proyeksi, dan status keputusan."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    ANALYSIS_YEARS,
    CURRENT_YEAR,
    DECISION_RECOMMENDATIONS,
    DECISION_STATUS,
    DEFAULT_WEIGHTS,
    EARLY_WARNING_DELTA,
    PROJECTION_YEAR,
    TREND_STATUS_LABELS,
)


def _norm_weights(weights: dict | None = None) -> dict[str, float]:
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def percentile_rank_0_100(series: pd.Series) -> pd.Series:
    """Percentile rank 0–100 (average method). Seragam jika semua nilai sama."""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(np.nan, index=s.index, dtype=float)
    if s.nunique(dropna=True) <= 1:
        return pd.Series(50.0, index=s.index, dtype=float).where(s.notna(), np.nan)
    return s.rank(pct=True, method="average") * 100.0


def add_risk_scores(
    panel: pd.DataFrame,
    weights: dict | None = None,
    year_col: str = "tahun",
) -> pd.DataFrame:
    """Tambah percentile risk per tahun + priority score pada panel long."""
    w = _norm_weights(weights)
    parts = []
    for year, g in panel.groupby(year_col, sort=True):
        stunting_risk = percentile_rank_0_100(g["stunting_pct"])
        poverty_risk = percentile_rank_0_100(g["kemiskinan_pct"])
        ikp_rank = percentile_rank_0_100(g["ikp_score"])
        food_risk = 100.0 - ikp_rank
        priority_score = (
            w["stunting"] * stunting_risk
            + w["kemiskinan"] * poverty_risk
            + w["ikp"] * food_risk
        )
        parts.append(
            g.assign(
                stunting_risk=stunting_risk,
                poverty_risk=poverty_risk,
                food_risk=food_risk,
                priority_score=priority_score,
                contrib_stunting=w["stunting"] * stunting_risk,
                contrib_kemiskinan=w["kemiskinan"] * poverty_risk,
                contrib_ikp=w["ikp"] * food_risk,
            )
        )
    return pd.concat(parts, ignore_index=True)


def _linear_predict_next(years: np.ndarray, values: np.ndarray, next_year: int) -> float:
    """Prediksi linear sederhana; fallback last value jika slope tidak stabil."""
    mask = np.isfinite(values) & np.isfinite(years)
    ys = years[mask].astype(float)
    vs = values[mask].astype(float)
    if len(vs) == 0:
        return float("nan")
    if len(vs) == 1:
        return float(vs[0])
    if np.unique(ys).size < 2:
        return float(vs[-1])
    try:
        slope, intercept = np.polyfit(ys, vs, 1)
        return float(slope * next_year + intercept)
    except (np.linalg.LinAlgError, ValueError):
        return float(vs[-1])


def pivot_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """Wide table per wilayah: indikator × tahun."""
    base = (
        panel.sort_values("tahun")
        .groupby("kode_wilayah", as_index=False)
        .agg(
            kode_prov=("kode_prov", "last"),
            provinsi=("provinsi", "last"),
            kabupaten_kota=("kabupaten_kota", "last"),
            tipe_wilayah=("tipe_wilayah", "last"),
        )
    )
    for year in ANALYSIS_YEARS:
        sub = panel[panel["tahun"] == year][
            [
                "kode_wilayah",
                "stunting_pct",
                "kemiskinan_pct",
                "ikp_score",
                "stunting_risk",
                "poverty_risk",
                "food_risk",
                "priority_score",
                "contrib_stunting",
                "contrib_kemiskinan",
                "contrib_ikp",
            ]
        ].copy()
        rename = {
            c: f"{c}_{year}"
            for c in sub.columns
            if c != "kode_wilayah"
        }
        sub = sub.rename(columns=rename)
        base = base.merge(sub, on="kode_wilayah", how="left")
    return base


def add_trend(wide: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Delta 2024−2022 + trend risk (percentile di ruang delta)."""
    w = _norm_weights(weights)
    df = wide.copy()
    y0, y1 = ANALYSIS_YEARS[0], ANALYSIS_YEARS[-1]

    df["delta_stunting"] = df[f"stunting_pct_{y1}"] - df[f"stunting_pct_{y0}"]
    df["delta_poverty"] = df[f"kemiskinan_pct_{y1}"] - df[f"kemiskinan_pct_{y0}"]
    # IKP turun → risiko naik: ikp_2022 − ikp_2024
    df["delta_ikp_risk"] = df[f"ikp_score_{y0}"] - df[f"ikp_score_{y1}"]

    # rank delta: kenaikan indikator buruk = risk tinggi
    trend_s = percentile_rank_0_100(df["delta_stunting"])
    trend_p = percentile_rank_0_100(df["delta_poverty"])
    trend_f = percentile_rank_0_100(df["delta_ikp_risk"])
    df["trend_risk_score"] = (
        w["stunting"] * trend_s + w["kemiskinan"] * trend_p + w["ikp"] * trend_f
    )

    # label tren berdasarkan kuartil trend risk & arah skor
    try:
        q = pd.qcut(
            df["trend_risk_score"],
            4,
            labels=["membaik", "relatif_stabil", "cenderung_memburuk", "memburuk_cepat"],
        )
        df["trend_status"] = q.astype(str).map(
            lambda k: TREND_STATUS_LABELS.get(k, k)
        )
    except ValueError:
        df["trend_status"] = TREND_STATUS_LABELS["relatif_stabil"]

    return df


def add_projection(wide: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Proyeksi linear indikator 2025 + projected priority score."""
    w = _norm_weights(weights)
    df = wide.copy()
    years = np.array(ANALYSIS_YEARS, dtype=float)

    pred_s, pred_p, pred_i = [], [], []
    for _, row in df.iterrows():
        sv = np.array([row[f"stunting_pct_{y}"] for y in ANALYSIS_YEARS], dtype=float)
        pv = np.array([row[f"kemiskinan_pct_{y}"] for y in ANALYSIS_YEARS], dtype=float)
        iv = np.array([row[f"ikp_score_{y}"] for y in ANALYSIS_YEARS], dtype=float)
        pred_s.append(_linear_predict_next(years, sv, PROJECTION_YEAR))
        pred_p.append(_linear_predict_next(years, pv, PROJECTION_YEAR))
        pred_i.append(_linear_predict_next(years, iv, PROJECTION_YEAR))

    df[f"stunting_pct_{PROJECTION_YEAR}"] = pred_s
    df[f"kemiskinan_pct_{PROJECTION_YEAR}"] = pred_p
    df[f"ikp_score_{PROJECTION_YEAR}"] = pred_i

    # clip prediksi ke rentang masuk akal
    df[f"stunting_pct_{PROJECTION_YEAR}"] = df[f"stunting_pct_{PROJECTION_YEAR}"].clip(0, 100)
    df[f"kemiskinan_pct_{PROJECTION_YEAR}"] = df[f"kemiskinan_pct_{PROJECTION_YEAR}"].clip(
        0, 100
    )
    df[f"ikp_score_{PROJECTION_YEAR}"] = df[f"ikp_score_{PROJECTION_YEAR}"].clip(0, 100)

    df["stunting_risk_2025"] = percentile_rank_0_100(df[f"stunting_pct_{PROJECTION_YEAR}"])
    df["poverty_risk_2025"] = percentile_rank_0_100(df[f"kemiskinan_pct_{PROJECTION_YEAR}"])
    ikp_rank = percentile_rank_0_100(df[f"ikp_score_{PROJECTION_YEAR}"])
    df["food_risk_2025"] = 100.0 - ikp_rank
    df["projected_score_2025"] = (
        w["stunting"] * df["stunting_risk_2025"]
        + w["kemiskinan"] * df["poverty_risk_2025"]
        + w["ikp"] * df["food_risk_2025"]
    )
    return df


def _quartile_labels(score: pd.Series) -> pd.Series:
    """Q1 rendah … Q4 tinggi (risiko/prioritas)."""
    try:
        return pd.qcut(
            score,
            4,
            labels=["Q1", "Q2", "Q3", "Q4"],
        ).astype(str)
    except ValueError:
        return pd.cut(
            score,
            bins=[-np.inf, 25, 50, 75, np.inf],
            labels=["Q1", "Q2", "Q3", "Q4"],
        ).astype(str)


def assign_decision_status(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["current_quartile"] = _quartile_labels(out["current_score_2024"])
    out["projected_quartile"] = _quartile_labels(out["projected_score_2025"])
    out["score_change"] = out["projected_score_2025"] - out["current_score_2024"]

    def decide(row) -> str:
        cur_q4 = row["current_quartile"] == "Q4"
        proj_q4 = row["projected_quartile"] == "Q4"
        if cur_q4 and proj_q4:
            return DECISION_STATUS["tingkatkan_segera"]
        if (not cur_q4) and proj_q4:
            return DECISION_STATUS["persiapkan_ekspansi"]
        if cur_q4 and (not proj_q4):
            return DECISION_STATUS["pertahankan_pantau"]
        # early warning: lonjakan tajam meski belum Q4
        if row["score_change"] >= EARLY_WARNING_DELTA:
            return DECISION_STATUS["persiapkan_ekspansi"]
        return DECISION_STATUS["pemantauan_rutin"]

    out["decision_status"] = out.apply(decide, axis=1)
    out["early_warning"] = (
        (out["score_change"] >= EARLY_WARNING_DELTA)
        | (out["decision_status"] == DECISION_STATUS["persiapkan_ekspansi"])
    )
    out["recommendation"] = out["decision_status"].map(DECISION_RECOMMENDATIONS)
    return out


def dominant_factor_from_contrib(row: pd.Series) -> str:
    scores = {
        "Stunting": float(row.get("contrib_stunting_2024", 0) or 0),
        "Kemiskinan": float(row.get("contrib_kemiskinan_2024", 0) or 0),
        "Kerawanan pangan": float(row.get("contrib_ikp_2024", 0) or 0),
    }
    return max(scores, key=scores.get)


def finalize_decision_table(wide: pd.DataFrame) -> pd.DataFrame:
    """Siapkan kolom final untuk dashboard."""
    df = wide.copy()
    df["current_score_2024"] = df[f"priority_score_{CURRENT_YEAR}"]
    df["score_2022"] = df["priority_score_2022"]
    df["score_2023"] = df["priority_score_2023"]
    df["score_2024"] = df["priority_score_2024"]

    df = assign_decision_status(df)

    df["current_rank"] = (
        df["current_score_2024"].rank(ascending=False, method="min").astype(int)
    )
    df["projected_rank"] = (
        df["projected_score_2025"].rank(ascending=False, method="min").astype(int)
    )
    df["rank_change"] = df["current_rank"] - df["projected_rank"]  # + = naik prioritas

    df["dominant_factor"] = df.apply(dominant_factor_from_contrib, axis=1)

    # alias untuk loader/geo
    df["kode_kab_kota"] = df["kode_wilayah"].astype(int)
    df["provinsi_normalized"] = df["provinsi"]
    df["kabupaten_kota_normalized"] = df["kabupaten_kota"]
    df["stunting_pct"] = df[f"stunting_pct_{CURRENT_YEAR}"]
    df["persen_penduduk_miskin"] = df[f"kemiskinan_pct_{CURRENT_YEAR}"]
    df["kemiskinan_pct"] = df[f"kemiskinan_pct_{CURRENT_YEAR}"]
    df["ikp"] = df[f"ikp_score_{CURRENT_YEAR}"]
    df["priority_score"] = df["current_score_2024"]
    df["rank"] = df["current_rank"]
    df["prioritas_kategori"] = df["decision_status"]  # kompat UI lama
    df["rekomendasi"] = df["recommendation"]
    df["contrib_stunting"] = df["contrib_stunting_2024"]
    df["contrib_kemiskinan"] = df["contrib_kemiskinan_2024"]
    df["contrib_ikp"] = df["contrib_ikp_2024"]
    df["pct_priority"] = percentile_rank_0_100(df["current_score_2024"])

    return df


def compute_full_analysis(
    panel_balanced: pd.DataFrame, weights: dict | None = None
) -> pd.DataFrame:
    """Pipeline lengkap: risk → wide → trend → proyeksi → status."""
    scored_long = add_risk_scores(panel_balanced, weights)
    wide = pivot_indicators(scored_long)
    wide = add_trend(wide, weights)
    wide = add_projection(wide, weights)
    return finalize_decision_table(wide)


def validate_linear_forecast(panel_balanced: pd.DataFrame) -> dict:
    """
    Validasi sederhana: prediksi t+1 dari 2 titik sebelumnya vs aktual.
    2022→2023 dan 2022–2023→2024 (linear 2/3 titik).
    """
    years = list(ANALYSIS_YEARS)
    errors = []
    for kode, g in panel_balanced.groupby("kode_wilayah"):
        g = g.sort_values("tahun")
        if set(g["tahun"].astype(int)) < set(years):
            continue
        for target in (2023, 2024):
            hist = g[g["tahun"] < target]
            if len(hist) < 1:
                continue
            actual_row = g[g["tahun"] == target]
            if actual_row.empty:
                continue
            ys = hist["tahun"].to_numpy(dtype=float)
            for col in ("stunting_pct", "kemiskinan_pct", "ikp_score"):
                pred = _linear_predict_next(
                    ys, hist[col].to_numpy(dtype=float), target
                )
                act = float(actual_row.iloc[0][col])
                if np.isfinite(pred) and np.isfinite(act):
                    errors.append(abs(pred - act))
    if not errors:
        return {"n": 0, "mae": None, "rmse": None}
    arr = np.array(errors, dtype=float)
    return {
        "n": int(len(arr)),
        "mae": float(np.mean(arr)),
        "rmse": float(np.sqrt(np.mean(arr**2))),
        "note": (
            "Validasi pada prediksi linear indikator t+1 (stunting, kemiskinan, IKP) "
            "bukan langsung pada priority score."
        ),
    }


# kompatibilitas build lama
def compute_scores(df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    """Jika input sudah flat current-year, hitung ulang risk seperti dulu (percentile)."""
    w = _norm_weights(weights)
    out = df.copy()
    stunt_col = "stunting_pct" if "stunting_pct" in out else "stunting"
    miskin_col = (
        "persen_penduduk_miskin"
        if "persen_penduduk_miskin" in out
        else "kemiskinan_pct"
    )
    ikp_col = "ikp" if "ikp" in out else "ikp_score"
    out["stunting_risk"] = percentile_rank_0_100(out[stunt_col])
    out["poverty_risk"] = percentile_rank_0_100(out[miskin_col])
    out["food_risk"] = 100.0 - percentile_rank_0_100(out[ikp_col])
    out["priority_score"] = (
        w["stunting"] * out["stunting_risk"]
        + w["kemiskinan"] * out["poverty_risk"]
        + w["ikp"] * out["food_risk"]
    )
    out["contrib_stunting"] = w["stunting"] * out["stunting_risk"]
    out["contrib_kemiskinan"] = w["kemiskinan"] * out["poverty_risk"]
    out["contrib_ikp"] = w["ikp"] * out["food_risk"]
    out["rank"] = out["priority_score"].rank(ascending=False, method="min").astype(int)
    return out
