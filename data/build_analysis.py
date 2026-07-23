"""Bangun dataset analisis siap dashboard dari output cleaning."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from clustering import run_clustering  # noqa: E402
from config import (  # noqa: E402
    DEFAULT_WEIGHTS,
    METHODOLOGY_NOTES,
    REFERENCE_WILAYAH_TOTAL,
    WEIGHT_SCENARIOS,
)
from scoring import compute_scores  # noqa: E402

CLEAN_DIR = ROOT.parent / "program-cleaning" / "output"
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_clean() -> dict[str, pd.DataFrame]:
    return {
        "ikp": pd.read_csv(CLEAN_DIR / "ikp_clean.csv"),
        "kemiskinan": pd.read_csv(CLEAN_DIR / "kemiskinan_clean.csv"),
        "peserta": pd.read_csv(CLEAN_DIR / "peserta_didik_clean.csv"),
        "stunting": pd.read_csv(CLEAN_DIR / "stunting_clean.csv"),
    }


def coverage_report(frames: dict[str, pd.DataFrame]) -> dict:
    """Hitung penyebab wilayah tidak masuk analisis lengkap."""
    ikp = frames["ikp"]
    keys = set(ikp["kode_kab_kota"].astype(int))
    has_kem = set(frames["kemiskinan"]["kode_kab_kota"].astype(int))
    has_pes = set(frames["peserta"]["kode_kab_kota"].astype(int))
    has_stu = set(frames["stunting"]["kode_kab_kota"].astype(int))
    complete = keys & has_kem & has_pes & has_stu

    missing_stunting = sorted(keys - has_stu)
    missing_kemiskinan = sorted(keys - has_kem)
    missing_peserta = sorted(keys - has_pes)
    excluded = sorted(keys - complete)

    name_map = (
        ikp.assign(kode_kab_kota=ikp["kode_kab_kota"].astype(int))
        .set_index("kode_kab_kota")["kabupaten_kota_normalized"]
        .to_dict()
    )

    reasons = []
    for kode in excluded:
        r = []
        if kode not in has_stu:
            r.append("stunting tidak tersedia")
        if kode not in has_kem:
            r.append("kemiskinan tidak tersedia")
        if kode not in has_pes:
            r.append("peserta didik tidak tersedia")
        reasons.append(
            {
                "kode_kab_kota": kode,
                "kabupaten_kota_normalized": name_map.get(kode, ""),
                "alasan": "; ".join(r) if r else "indikator tidak lengkap",
            }
        )

    return {
        "n_referensi_ikp": int(len(keys)),
        "n_dianalisis": int(len(complete)),
        "n_tidak_masuk": int(len(excluded)),
        "coverage_pct": round(100 * len(complete) / len(keys), 1) if keys else 0,
        "n_missing_stunting": len(missing_stunting),
        "n_missing_kemiskinan": len(missing_kemiskinan),
        "n_missing_peserta": len(missing_peserta),
        "excluded_sample": reasons[:30],
        "excluded_all": reasons,
    }


def merge_complete(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ikp = frames["ikp"][
        [
            "kode_prov",
            "kode_kab_kota",
            "provinsi_normalized",
            "kabupaten_kota_normalized",
            "tipe_wilayah",
            "tahun",
            "ikp",
            "kelompok_ikp",
        ]
    ].rename(columns={"tahun": "tahun_ikp"})

    kem = frames["kemiskinan"][["kode_kab_kota", "persen_penduduk_miskin", "tahun"]].rename(
        columns={"tahun": "tahun_kemiskinan"}
    )
    pes = frames["peserta"][["kode_kab_kota", "jumlah_peserta_didik"]]
    stu = frames["stunting"][
        ["kode_kab_kota", "stunting_pct", "severely_stunting_pct", "normal_pct", "n_sampel"]
    ].drop_duplicates(subset=["kode_kab_kota"], keep="first")

    df = (
        ikp.merge(kem, on="kode_kab_kota", how="inner")
        .merge(pes, on="kode_kab_kota", how="inner")
        .merge(stu, on="kode_kab_kota", how="inner")
    )
    df = df.drop_duplicates(subset=["kode_kab_kota"], keep="first")
    df = df.assign(
        kode_kab_kota_str=df["kode_kab_kota"].astype(int).astype(str).str.zfill(4)
    )
    return df.reset_index(drop=True)


def sensitivity_table(base: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, weights in WEIGHT_SCENARIOS.items():
        scored = compute_scores(base, weights)
        top10 = set(scored.nsmallest(10, "rank")["kode_kab_kota"].astype(int).tolist())
        for _, r in scored.iterrows():
            rows.append(
                {
                    "skenario": name,
                    "kode_kab_kota": int(r["kode_kab_kota"]),
                    "kabupaten_kota_normalized": r["kabupaten_kota_normalized"],
                    "provinsi_normalized": r["provinsi_normalized"],
                    "priority_score": r["priority_score"],
                    "rank": int(r["rank"]),
                    "in_top10": int(r["kode_kab_kota"]) in top10,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    frames = load_clean()
    cov = coverage_report(frames)
    base = merge_complete(frames)
    print(f"Complete cases (4 indikator): {len(base)}")
    print(
        f"Coverage: {cov['n_dianalisis']}/{cov['n_referensi_ikp']} "
        f"({cov['coverage_pct']}%), missing stunting={cov['n_missing_stunting']}"
    )

    scored = compute_scores(base, DEFAULT_WEIGHTS)
    clustered, cluster_meta = run_clustering(scored)

    for col in scored.columns:
        if col not in clustered.columns:
            clustered = clustered.assign(**{col: scored[col].values})

    out_csv = OUT_DIR / "analysis_ready.csv"
    clustered.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved {out_csv} ({len(clustered)} rows)")

    sens = sensitivity_table(base)
    sens_path = OUT_DIR / "sensitivity_ranks.csv"
    sens.to_csv(sens_path, index=False, encoding="utf-8-sig")

    excl_path = OUT_DIR / "excluded_wilayah.csv"
    pd.DataFrame(cov["excluded_all"]).to_csv(excl_path, index=False, encoding="utf-8-sig")

    top = clustered.nsmallest(1, "rank").iloc[0]
    meta = {
        "n_wilayah": int(len(clustered)),
        "reference_total": REFERENCE_WILAYAH_TOTAL,
        "coverage": {
            k: v
            for k, v in cov.items()
            if k != "excluded_all"
        },
        "default_weights": DEFAULT_WEIGHTS,
        "weight_scenarios": WEIGHT_SCENARIOS,
        "methodology_notes": METHODOLOGY_NOTES,
        "cluster": {
            "best_k": cluster_meta["best_k"],
            "best_silhouette": cluster_meta["best_silhouette"],
            "silhouette_scores": {
                str(k): v for k, v in cluster_meta["silhouette_scores"].items()
            },
            "inertia_scores": {
                str(k): v for k, v in cluster_meta["inertia_scores"].items()
            },
            "cluster_names": {
                str(k): v for k, v in cluster_meta["cluster_names"].items()
            },
            "cluster_counts": cluster_meta["cluster_counts"],
            "cluster_profile": cluster_meta["cluster_profile"]
            .reset_index()
            .to_dict(orient="records"),
            "cluster_profile_z": cluster_meta["cluster_profile_z"]
            .reset_index()
            .to_dict(orient="records"),
            "note": cluster_meta["note"],
        },
        "national_means": {
            "stunting_pct": float(clustered["stunting_pct"].mean()),
            "persen_penduduk_miskin": float(clustered["persen_penduduk_miskin"].mean()),
            "ikp": float(clustered["ikp"].mean()),
            "jumlah_peserta_didik": float(clustered["jumlah_peserta_didik"].mean()),
            "priority_score": float(clustered["priority_score"].mean()),
        },
        "top_wilayah": {
            "kabupaten_kota_normalized": top["kabupaten_kota_normalized"],
            "provinsi_normalized": top["provinsi_normalized"],
            "priority_score": float(top["priority_score"]),
            "pct_priority": float(top["pct_priority"]),
            "contrib_stunting": float(top["contrib_stunting"]),
            "contrib_kemiskinan": float(top["contrib_kemiskinan"]),
            "contrib_ikp": float(top["contrib_ikp"]),
            "contrib_peserta": float(top["contrib_peserta"]),
        },
        "peserta_didik_national_sum": int(frames["peserta"]["jumlah_peserta_didik"].sum()),
    }
    meta_path = OUT_DIR / "analysis_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {meta_path}")
    print(
        f"Cluster k={meta['cluster']['best_k']} "
        f"silhouette={meta['cluster']['best_silhouette']:.3f}"
    )
    # sanity label vs profile
    for row in meta["cluster"]["cluster_profile"]:
        print(
            f"  [{row.get('cluster_id')}] {row.get('cluster_label')}: "
            f"stunt={row['stunting_pct']:.1f} miskin={row['persen_penduduk_miskin']:.1f} "
            f"ikp={row['ikp']:.1f} siswa_mean={row['jumlah_peserta_didik']:.0f} "
            f"siswa_med={row.get('median_peserta_didik', 0):.0f}"
        )


if __name__ == "__main__":
    main()
