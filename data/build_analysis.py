"""Bangun analysis_ready dari panel balanced multi-tahun."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from config import (  # noqa: E402
    ANALYSIS_YEARS,
    CURRENT_YEAR,
    DEFAULT_WEIGHTS,
    METHODOLOGY_NOTES,
    PROJECTION_YEAR,
    REFERENCE_WILAYAH_TOTAL,
)
from scoring import compute_full_analysis, validate_linear_forecast  # noqa: E402

CLEAN_DIR = ROOT.parent / "program-cleaning" / "output"
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# kolom utama yang diekspor (plus indikator pendukung)
EXPORT_COLS = [
    "kode_wilayah",
    "kode_kab_kota",
    "kode_prov",
    "provinsi",
    "provinsi_normalized",
    "kabupaten_kota",
    "kabupaten_kota_normalized",
    "tipe_wilayah",
    "score_2022",
    "score_2023",
    "score_2024",
    "current_score_2024",
    "projected_score_2025",
    "score_change",
    "current_rank",
    "projected_rank",
    "rank_change",
    "current_quartile",
    "projected_quartile",
    "trend_status",
    "trend_risk_score",
    "delta_stunting",
    "delta_poverty",
    "delta_ikp_risk",
    "decision_status",
    "early_warning",
    "dominant_factor",
    "recommendation",
    "stunting_pct",
    "kemiskinan_pct",
    "persen_penduduk_miskin",
    "ikp",
    "stunting_pct_2022",
    "stunting_pct_2023",
    "stunting_pct_2024",
    "stunting_pct_2025",
    "kemiskinan_pct_2022",
    "kemiskinan_pct_2023",
    "kemiskinan_pct_2024",
    "kemiskinan_pct_2025",
    "ikp_score_2022",
    "ikp_score_2023",
    "ikp_score_2024",
    "ikp_score_2025",
    "stunting_risk_2024",
    "poverty_risk_2024",
    "food_risk_2024",
    "contrib_stunting",
    "contrib_kemiskinan",
    "contrib_ikp",
    "priority_score",
    "rank",
    "prioritas_kategori",
    "rekomendasi",
    "pct_priority",
]


def load_panel() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    bal_path = CLEAN_DIR / "panel_balanced.csv"
    long_path = CLEAN_DIR / "panel_kabkota_long.csv"
    audit_path = CLEAN_DIR / "panel_audit.json"
    if not bal_path.exists():
        raise FileNotFoundError(
            f"Belum ada {bal_path}. Jalankan: python program-cleaning/run_cleaning.py"
        )
    balanced = pd.read_csv(bal_path)
    audit = {}
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    long_panel = pd.read_csv(long_path) if long_path.exists() else balanced
    return balanced, audit, long_panel


def main() -> None:
    balanced, audit, long_panel = load_panel()
    print(
        f"Balanced panel: {balanced['kode_wilayah'].nunique()} wilayah, "
        f"{len(balanced)} baris, tahun={sorted(balanced['tahun'].unique())}"
    )

    scored = compute_full_analysis(balanced, DEFAULT_WEIGHTS)
    print(f"Decision table: {len(scored)} wilayah")

    # pilih kolom export yang ada
    cols = [c for c in EXPORT_COLS if c in scored.columns]
    out = scored[cols].sort_values("current_rank").reset_index(drop=True)
    out_csv = OUT_DIR / "analysis_ready.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved {out_csv} ({len(out)} rows)")

    # long scores untuk timeline chart
    scored_long_path = OUT_DIR / "panel_scores_long.csv"
    from scoring import add_risk_scores  # local import after path setup

    long_scored = add_risk_scores(balanced, DEFAULT_WEIGHTS)
    long_scored.to_csv(scored_long_path, index=False, encoding="utf-8-sig")
    print(f"Saved {scored_long_path}")

    # excluded / partial
    excl_path = OUT_DIR / "excluded_wilayah.csv"
    partial_src = CLEAN_DIR / "panel_partial_wilayah.csv"
    if partial_src.exists():
        pd.read_csv(partial_src).to_csv(excl_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(audit.get("partial_wilayah", [])).to_csv(
            excl_path, index=False, encoding="utf-8-sig"
        )

    val = validate_linear_forecast(balanced)
    print(f"Validasi linear: n={val['n']} MAE={val.get('mae')} RMSE={val.get('rmse')}")

    top = out.iloc[0]
    counts = out["decision_status"].value_counts().to_dict()

    meta = {
        "title": "Pemetaan Prioritas MBG 2024 dan Proyeksi Risiko 2025",
        "subtitle": "Analisis prioritas dan early warning berdasarkan data 2022–2024",
        "years": list(ANALYSIS_YEARS),
        "current_year": CURRENT_YEAR,
        "projection_year": PROJECTION_YEAR,
        "n_wilayah": int(len(out)),
        "reference_total": REFERENCE_WILAYAH_TOTAL,
        "coverage": {
            "n_balanced": audit.get("n_balanced_panel", len(out)),
            "n_partial": audit.get("n_partial"),
            "n_wilayah_total_panel": audit.get("n_wilayah_total"),
            "coverage_pct": audit.get("coverage_pct"),
            "n_null_indicator_cells": audit.get("n_null_indicator_cells"),
        },
        "default_weights": DEFAULT_WEIGHTS,
        "methodology_notes": METHODOLOGY_NOTES,
        "decision_counts": counts,
        "projection_validation": val,
        "national_means": {
            "stunting_pct": float(out["stunting_pct"].mean()),
            "persen_penduduk_miskin": float(out["persen_penduduk_miskin"].mean()),
            "ikp": float(out["ikp"].mean()),
            "current_score_2024": float(out["current_score_2024"].mean()),
            "projected_score_2025": float(out["projected_score_2025"].mean()),
        },
        "top_wilayah": {
            "kabupaten_kota": top["kabupaten_kota"],
            "provinsi": top["provinsi"],
            "current_score_2024": float(top["current_score_2024"]),
            "projected_score_2025": float(top["projected_score_2025"]),
            "decision_status": top["decision_status"],
            "dominant_factor": top["dominant_factor"],
        },
        "sources": {
            "stunting": "SSGI / dataset stunting kabupaten-kota 2022–2024",
            "kemiskinan": "BPS — Persentase Penduduk Miskin (P0) 2022–2024",
            "pangan": "Badan Pangan Nasional — IKP Kabupaten/Kota 2022–2024",
        },
    }
    meta_path = OUT_DIR / "analysis_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {meta_path}")
    print("Decision counts:", counts)
    print(
        f"Top: {top['kabupaten_kota']} ({top['provinsi']}) "
        f"score={top['current_score_2024']:.1f} → {top['projected_score_2025']:.1f} "
        f"| {top['decision_status']}"
    )


if __name__ == "__main__":
    main()
