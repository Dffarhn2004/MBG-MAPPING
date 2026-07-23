"""Segmentasi wilayah dengan KMeans + label interpretatif."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import CLUSTER_NAME_TEMPLATES


FEATURE_COLS = [
    "stunting_pct",
    "persen_penduduk_miskin",
    "ikp",
    "jumlah_peserta_didik",
]


def choose_k(
    X: np.ndarray,
    k_min: int = 2,
    k_max: int = 8,
    random_state: int = 42,
) -> tuple[int, dict, dict]:
    """Pilih k dengan silhouette pada rentang luas (eksploratif)."""
    scores = {}
    inertia = {}
    upper = min(k_max, len(X) - 1)
    for k in range(k_min, upper + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = model.fit_predict(X)
        scores[k] = float(silhouette_score(X, labels))
        inertia[k] = float(model.inertia_)
    best_k = max(scores, key=scores.get)
    return best_k, scores, inertia


def interpret_cluster_labels(profile: pd.DataFrame) -> dict[int, str]:
    """
    Nama cluster berdasarkan karakteristik mean indikator.
    Pakai argmax/argmin nilai asli (bukan rank terbalik).
    """
    scored = profile.copy()
    # skor kerentanan: stunting & kemiskinan tinggi, IKP rendah
    z = scored.copy()
    for col in ["stunting_pct", "persen_penduduk_miskin", "ikp", "jumlah_peserta_didik"]:
        mu, sd = z[col].mean(), z[col].std(ddof=0)
        z[col] = 0.0 if sd == 0 else (z[col] - mu) / sd

    z["risk"] = z["stunting_pct"] + z["persen_penduduk_miskin"] - z["ikp"]
    z["baik"] = -z["stunting_pct"] - z["persen_penduduk_miskin"] + z["ikp"]

    labels: dict[int, str] = {}
    used: set[int] = set()

    def take(series: pd.Series, template_idx: int, maximize: bool = True) -> None:
        remain = series.drop(index=list(used), errors="ignore")
        if remain.empty:
            return
        c = int(remain.idxmax() if maximize else remain.idxmin())
        labels[c] = CLUSTER_NAME_TEMPLATES[template_idx]
        used.add(c)

    # 1) kerentanan tertinggi
    take(z["risk"], 0, maximize=True)
    # 2) kondisi relatif terbaik
    take(z["baik"], 3, maximize=True)
    # 3) populasi siswa terbesar di sisa
    take(scored["jumlah_peserta_didik"], 1, maximize=True)
    # 4) IKP terendah di sisa
    take(scored["ikp"], 2, maximize=False)

    i = 4
    for c in scored.index:
        c = int(c)
        if c not in labels:
            labels[c] = CLUSTER_NAME_TEMPLATES[min(i, len(CLUSTER_NAME_TEMPLATES) - 1)]
            i += 1
    return labels


def run_clustering(df: pd.DataFrame, random_state: int = 42) -> tuple[pd.DataFrame, dict]:
    work = df.dropna(subset=FEATURE_COLS).copy()
    X_raw = work[FEATURE_COLS].astype(float).values
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    best_k, sil_scores, inertia = choose_k(X, random_state=random_state)
    model = KMeans(n_clusters=best_k, n_init=20, random_state=random_state)
    work = work.assign(cluster_id=model.fit_predict(X))

    profile_mean = work.groupby("cluster_id")[FEATURE_COLS].mean()
    profile_median = work.groupby("cluster_id")[FEATURE_COLS].median()
    name_map = interpret_cluster_labels(profile_mean)
    work = work.assign(cluster_label=work["cluster_id"].map(name_map))

    profile_out = profile_mean.copy()
    profile_out = profile_out.assign(
        cluster_label=profile_out.index.map(name_map),
        median_peserta_didik=profile_median["jumlah_peserta_didik"],
        n_wilayah=work.groupby("cluster_id").size(),
    )

    # z-score profil untuk visualisasi skala seragam
    z_profile = profile_mean.copy()
    for col in FEATURE_COLS:
        mu, sd = work[col].mean(), work[col].std(ddof=0)
        z_profile[col] = 0.0 if sd == 0 else (z_profile[col] - mu) / sd
    z_profile = z_profile.assign(cluster_label=z_profile.index.map(name_map))

    meta = {
        "best_k": best_k,
        "silhouette_scores": sil_scores,
        "inertia_scores": inertia,
        "best_silhouette": sil_scores[best_k],
        "cluster_names": name_map,
        "cluster_profile": profile_out,
        "cluster_profile_z": z_profile,
        "cluster_counts": work["cluster_label"].value_counts().to_dict(),
        "note": (
            "Segmentasi bersifat eksploratif. Silhouette relatif rendah menandakan "
            "karakteristik antarcluster masih tumpang tindih."
        ),
    }
    return work, meta
