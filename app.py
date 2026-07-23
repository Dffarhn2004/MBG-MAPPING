"""
Dashboard Prioritas MBG — Streamlit
Jalankan: streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    DEFAULT_WEIGHTS,
    METHODOLOGY_NOTES,
    REFERENCE_WILAYAH_TOTAL,
    WEIGHT_SCENARIOS,
)
from loaders import (  # noqa: E402
    format_number,
    load_analysis,
    load_geojson_kab,
    load_geojson_provinsi,
    load_meta,
    load_sensitivity,
    normalize_prov_geo_name,
)
from scoring import auto_reason  # noqa: E402

st.set_page_config(
    page_title="Dashboard Prioritas MBG",
    page_icon="🍚",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIORITY_COLORS = {
    "Q4 Sangat Tinggi": "#B91C1C",
    "Q3 Tinggi": "#EA580C",
    "Q2 Sedang": "#CA8A04",
    "Q1 Rendah": "#16A34A",
    "Di luar filter": "#E2E8F0",
    "Tanpa data": "#CBD5E1",
}
PRIORITY_ORDER = [
    "Q4 Sangat Tinggi",
    "Q3 Tinggi",
    "Q2 Sedang",
    "Q1 Rendah",
    "Di luar filter",
    "Tanpa data",
]
PRIORITY_FILTER_OPTS = ["Q4 Sangat Tinggi", "Q3 Tinggi", "Q2 Sedang", "Q1 Rendah"]
HIGH_PRIORITY = {"Q4 Sangat Tinggi", "Q3 Tinggi"}



def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; max-width: 1400px; }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px 16px;
        }
        .reason-box {
            background: #fff7ed;
            border-left: 4px solid #ea580c;
            padding: 0.9rem 1rem;
            border-radius: 0 8px 8px 0;
            margin: 0.5rem 0 1rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def national_means(df: pd.DataFrame) -> dict:
    return {
        "stunting_pct": float(df["stunting_pct"].mean()),
        "persen_penduduk_miskin": float(df["persen_penduduk_miskin"].mean()),
        "ikp": float(df["ikp"].mean()),
        "jumlah_peserta_didik": float(df["jumlah_peserta_didik"].mean()),
        "priority_score": float(df["priority_score"].mean()),
    }


def sidebar_nav() -> str:
    st.sidebar.title("Prioritas MBG")
    st.sidebar.caption("Makan Bergizi Gratis — analisis kab/kota")
    page = st.sidebar.radio(
        "Navigasi",
        [
            "1. Ringkasan Nasional",
            "2. Peta Prioritas MBG",
            "3. Ranking Wilayah",
            "4. Profil Kabupaten/Kota",
            "5. Hubungan Antarindikator",
            "6. Segmentasi Cluster",
            "7. Komponen Skor Prioritas",
            "8. Sensitivity Analysis",
        ],
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        f"**Bobot default**  \n"
        f"Stunting {DEFAULT_WEIGHTS['stunting']:.0%} · "
        f"Kemiskinan {DEFAULT_WEIGHTS['kemiskinan']:.0%} · "
        f"IKP {DEFAULT_WEIGHTS['ikp']:.0%} (dibalik) · "
        f"Peserta didik {DEFAULT_WEIGHTS['peserta_didik']:.0%}"
    )
    st.sidebar.caption(METHODOLOGY_NOTES["ikp_invert"])
    return page


def filter_panel(df: pd.DataFrame, key_prefix: str = "f") -> pd.DataFrame:
    c1, c2, c3, c4, c5 = st.columns(5)
    provs = ["Semua"] + sorted(df["provinsi_normalized"].dropna().unique().tolist())
    cats = ["Semua"] + PRIORITY_FILTER_OPTS
    clusters = ["Semua"] + sorted(df["cluster_label"].dropna().unique().tolist())
    ikp_groups = ["Semua"] + sorted(df["kelompok_ikp"].dropna().astype(int).astype(str).unique().tolist())

    with c1:
        prov = st.selectbox("Provinsi", provs, key=f"{key_prefix}_prov")
    with c2:
        cat = st.selectbox("Prioritas", cats, key=f"{key_prefix}_cat")
    with c3:
        clus = st.selectbox("Cluster", clusters, key=f"{key_prefix}_clus")
    with c4:
        ikp_g = st.selectbox("Kelompok IKP", ikp_groups, key=f"{key_prefix}_ikp")
    with c5:
        st_min, st_max = float(df["stunting_pct"].min()), float(df["stunting_pct"].max())
        st_range = st.slider(
            "Rentang stunting (%)",
            min_value=float(np.floor(st_min)),
            max_value=float(np.ceil(st_max)),
            value=(float(np.floor(st_min)), float(np.ceil(st_max))),
            key=f"{key_prefix}_st",
        )

    out = df.copy()
    if prov != "Semua":
        out = out[out["provinsi_normalized"] == prov]
    if cat != "Semua":
        out = out[out["prioritas_kategori"] == cat]
    if clus != "Semua":
        out = out[out["cluster_label"] == clus]
    if ikp_g != "Semua":
        out = out[out["kelompok_ikp"].astype(int).astype(str) == ikp_g]
    out = out[(out["stunting_pct"] >= st_range[0]) & (out["stunting_pct"] <= st_range[1])]
    return out


# ---------- Pages ----------

def page_ringkasan(df: pd.DataFrame, meta: dict) -> None:
    st.header("Ringkasan Nasional")
    st.caption(
        "Gambaran cepat kebutuhan peningkatan MBG berdasarkan data IKP, kemiskinan, "
        "stunting, dan total peserta didik (kasus lengkap empat indikator)."
    )

    n = len(df)
    cov = meta.get("coverage", {})
    n_ref = cov.get("n_referensi_ikp", REFERENCE_WILAYAH_TOTAL)
    n_excl = cov.get("n_tidak_masuk", n_ref - n)
    coverage_pct = cov.get("coverage_pct", round(100 * n / n_ref, 1))

    high = df[df["prioritas_kategori"].isin(HIGH_PRIORITY)]
    n_high = len(high)
    siswa_high = high["jumlah_peserta_didik"].sum()
    means = national_means(df)
    top = df.nsmallest(1, "rank").iloc[0]

    c0, c1, c2, c3 = st.columns(4)
    c0.metric("Wilayah referensi (IKP)", format_number(n_ref))
    c1.metric("Wilayah dianalisis", format_number(n))
    c2.metric("Tidak masuk analisis", format_number(n_excl))
    c3.metric("Coverage", f"{coverage_pct}%".replace(".", ","))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Kuartil tinggi+ (Q3–Q4)", format_number(n_high))
    k2.metric("Peserta didik di Q3–Q4", format_number(siswa_high, "juta"))
    k3.metric("Rata-rata stunting", format_number(means["stunting_pct"], "pct"))
    k4.metric("Rata-rata kemiskinan", format_number(means["persen_penduduk_miskin"], "pct"))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Rata-rata IKP", format_number(means["ikp"], "score"))
    k6.metric("Rata-rata skor prioritas", format_number(means["priority_score"], "score"))
    k7.metric(
        "Skor tertinggi (relatif)",
        format_number(top["priority_score"], "score"),
        delta=f"percentile {top['pct_priority']:.0f}",
    )
    k8.metric(
        "Prioritas relatif tertinggi",
        f"{top['kabupaten_kota_normalized']}",
        delta=top["provinsi_normalized"],
    )

    st.info(
        f"Di antara **{n} kab/kota berdata lengkap**, "
        f"**{top['kabupaten_kota_normalized']}** ({top['provinsi_normalized']}) "
        f"memperoleh skor prioritas relatif tertinggi "
        f"({top['priority_score']:.1f} / skala 0–100). "
        f"Kategori memakai **kuartil skor** (posisi relatif), bukan standar kebijakan. "
        f"{METHODOLOGY_NOTES['skor']}"
    )

    # ---- Overview nasional (bubble) ----
    st.subheader("Overview kondisi nasional")
    st.caption(
        "Setiap gelembung = satu kab/kota. Ukuran ≈ jumlah peserta didik. "
        "Garis putus-putus = rata-rata nasional."
    )
    view = st.radio(
        "Sudut pandang",
        [
            "Stunting × Kemiskinan",
            "Kerentanan × Kebutuhan layanan",
            "Stunting × IKP",
        ],
        horizontal=True,
        key="ringkas_bubble_view",
    )

    bubble = df.copy()
    # label hanya Top 8 agar tidak ramai
    top_ids = set(df.nsmallest(8, "rank")["kode_kab_kota"])
    bubble["label_titik"] = bubble.apply(
        lambda r: r["kabupaten_kota_normalized"] if r["kode_kab_kota"] in top_ids else "",
        axis=1,
    )

    if view == "Stunting × Kemiskinan":
        x_col, y_col = "persen_penduduk_miskin", "stunting_pct"
        x_line, y_line = means["persen_penduduk_miskin"], means["stunting_pct"]
        x_title, y_title = "Kemiskinan (%)", "Stunting (%)"
        # kuadran
        q_hi_hi = int(
            ((bubble[x_col] >= x_line) & (bubble[y_col] >= y_line)).sum()
        )
        q_lo_lo = int(
            ((bubble[x_col] < x_line) & (bubble[y_col] < y_line)).sum()
        )
        insight = (
            f"**{q_hi_hi}/{n}** wilayah berada di kuadran kerentanan ganda "
            f"(stunting & kemiskinan ≥ rata-rata). "
            f"**{q_lo_lo}/{n}** relatif lebih baik pada kedua indikator. "
            "Gelembung besar di kuadran kanan-atas = banyak siswa di wilayah berisiko tinggi."
        )
    elif view == "Kerentanan × Kebutuhan layanan":
        x_col, y_col = "vulnerability_score", "service_need_score"
        x_line, y_line = float(bubble[x_col].mean()), float(bubble[y_col].mean())
        x_title, y_title = "Vulnerability score", "Service need (peserta didik ternormalisasi)"
        q_hi_hi = int(((bubble[x_col] >= x_line) & (bubble[y_col] >= y_line)).sum())
        insight = (
            f"**{q_hi_hi}/{n}** wilayah punya kerentanan tinggi sekaligus kebutuhan layanan besar. "
            "Kuadran kanan-atas = kandidat utama peningkatan MBG (risiko + cakupan siswa)."
        )
    else:
        x_col, y_col = "ikp", "stunting_pct"
        x_line, y_line = means["ikp"], means["stunting_pct"]
        x_title, y_title = "IKP (lebih tinggi = lebih baik)", "Stunting (%)"
        q_risk = int(((bubble[x_col] < x_line) & (bubble[y_col] >= y_line)).sum())
        insight = (
            f"**{q_risk}/{n}** wilayah punya IKP di bawah rata-rata sekaligus stunting di atas rata-rata — "
            "kombinasi ketahanan pangan lemah dan beban gizi tinggi."
        )

    fig_b = px.scatter(
        bubble,
        x=x_col,
        y=y_col,
        size="jumlah_peserta_didik",
        color="prioritas_kategori",
        color_discrete_map=PRIORITY_COLORS,
        category_orders={"prioritas_kategori": PRIORITY_FILTER_OPTS},
        hover_name="kabupaten_kota_normalized",
        text="label_titik",
        size_max=48,
        hover_data={
            "provinsi_normalized": True,
            "priority_score": ":.1f",
            "ikp": ":.1f",
            "jumlah_peserta_didik": ":,.0f",
            "label_titik": False,
        },
        labels={
            x_col: x_title,
            y_col: y_title,
            "prioritas_kategori": "Kuartil",
            "jumlah_peserta_didik": "Peserta didik",
        },
        title="Peta sebaran nasional — ke mana konsentrasi masalah?",
    )
    fig_b.add_vline(x=x_line, line_dash="dash", line_color="#64748b", annotation_text="rata-rata X")
    fig_b.add_hline(y=y_line, line_dash="dash", line_color="#64748b", annotation_text="rata-rata Y")
    fig_b.update_traces(textposition="top center", textfont_size=10)
    fig_b.update_layout(height=520, legend_title="Kuartil", margin=dict(t=50, b=10))
    st.plotly_chart(fig_b, use_container_width=True)
    st.markdown(insight)

    # ringkas arah nasional
    east = df[
        df["provinsi_normalized"].str.contains(
            "Papua|Nusa Tenggara|Maluku|Sulawesi", case=False, na=False
        )
    ]
    share_east_q4 = (
        len(east[east["prioritas_kategori"] == "Q4 Sangat Tinggi"])
        / max(len(df[df["prioritas_kategori"] == "Q4 Sangat Tinggi"]), 1)
        * 100
    )
    st.success(
        f"**Arah singkat:** fokus Q4 relatif terkonsentrasi di Indonesia timur "
        f"(~{share_east_q4:.0f}% dari wilayah Q4 berasal dari Papua/NTT/Maluku/Sulawesi). "
        f"Rata-rata nasional: stunting {means['stunting_pct']:.1f}%, "
        f"kemiskinan {means['persen_penduduk_miskin']:.1f}%, IKP {means['ikp']:.1f}."
    )

    left, right = st.columns([1.4, 1])
    with left:
        top10 = df.nsmallest(10, "rank").sort_values("priority_score", ascending=True)
        fig = px.bar(
            top10,
            x="priority_score",
            y="kabupaten_kota_normalized",
            orientation="h",
            color="prioritas_kategori",
            color_discrete_map=PRIORITY_COLORS,
            category_orders={"prioritas_kategori": PRIORITY_ORDER},
            hover_data={
                "provinsi_normalized": True,
                "stunting_pct": ":.1f",
                "persen_penduduk_miskin": ":.1f",
                "ikp": ":.1f",
                "jumlah_peserta_didik": ":,.0f",
                "priority_score": ":.1f",
                "contrib_stunting": ":.1f",
                "contrib_kemiskinan": ":.1f",
                "contrib_ikp": ":.1f",
                "contrib_peserta": ":.1f",
            },
            labels={
                "priority_score": "Skor Prioritas (relatif)",
                "kabupaten_kota_normalized": "Kabupaten/Kota",
                "prioritas_kategori": "Kuartil",
            },
            title=f"Top 10 prioritas relatif (dari {n} wilayah berdata lengkap)",
        )
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        cat_count = (
            df["prioritas_kategori"]
            .value_counts()
            .reindex(PRIORITY_ORDER)
            .fillna(0)
            .reset_index()
        )
        cat_count.columns = ["kuartil", "jumlah"]
        fig2 = px.pie(
            cat_count,
            names="kuartil",
            values="jumlah",
            color="kuartil",
            color_discrete_map=PRIORITY_COLORS,
            title="Distribusi kuartil skor prioritas",
            hole=0.45,
        )
        fig2.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(METHODOLOGY_NOTES["kuartil"])

    with st.expander("Cakupan data & penyebab eksklusi"):
        st.markdown(
            f"- Referensi IKP: **{n_ref}** kab/kota  \n"
            f"- Dianalisis (4 indikator lengkap): **{n}**  \n"
            f"- Tidak masuk: **{n_excl}** ({100 - coverage_pct:.1f}%)  \n"
            f"- Stunting tidak tersedia: **{cov.get('n_missing_stunting', '–')}**  \n"
            f"- Kemiskinan tidak tersedia: **{cov.get('n_missing_kemiskinan', '–')}**  \n"
            f"- Peserta didik tidak tersedia: **{cov.get('n_missing_peserta', '–')}**"
        )
        st.caption(METHODOLOGY_NOTES["peserta_didik"])
        excl = Path(ROOT / "data" / "excluded_wilayah.csv")
        if excl.exists():
            st.dataframe(pd.read_csv(excl).head(40), use_container_width=True, hide_index=True)

    # dekomposisi top wilayah
    st.subheader(f"Dekomposisi skor — {top['kabupaten_kota_normalized']}")
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Priority score", f"{top['priority_score']:.1f}")
    d2.metric("Kontribusi stunting", f"{top['contrib_stunting']:.1f}")
    d3.metric("Kontribusi kemiskinan", f"{top['contrib_kemiskinan']:.1f}")
    d4.metric("Kontribusi kerawanan IKP", f"{top['contrib_ikp']:.1f}")
    d5.metric("Kontribusi peserta didik", f"{top['contrib_peserta']:.1f}")
    st.caption(
        f"Wilayah prioritas relatif tertinggi terkonsentrasi di skor gabungan. "
        f"Cluster k={meta['cluster']['best_k']} "
        f"(silhouette {meta['cluster']['best_silhouette']:.3f}) — "
        f"{meta['cluster'].get('note', 'segmentasi eksploratif.')}"
    )


# Mapping nama provinsi dashboard → NAME_1 di GeoJSON GADM
PROV_TO_GADM = {
    "Aceh": "Aceh",
    "Bali": "Bali",
    "Banten": "Banten",
    "Bengkulu": "Bengkulu",
    "DI Yogyakarta": "Yogyakarta",
    "DKI Jakarta": "JakartaRaya",
    "Gorontalo": "Gorontalo",
    "Jambi": "Jambi",
    "Jawa Barat": "JawaBarat",
    "Jawa Tengah": "JawaTengah",
    "Jawa Timur": "JawaTimur",
    "Kalimantan Barat": "KalimantanBarat",
    "Kalimantan Selatan": "KalimantanSelatan",
    "Kalimantan Tengah": "KalimantanTengah",
    "Kalimantan Timur": "KalimantanTimur",
    "Kalimantan Utara": "KalimantanUtara",
    "Kepulauan Bangka Belitung": "BangkaBelitung",
    "Kepulauan Riau": "KepulauanRiau",
    "Lampung": "Lampung",
    "Maluku": "Maluku",
    "Maluku Utara": "MalukuUtara",
    "Nusa Tenggara Barat": "NusaTenggaraBarat",
    "Nusa Tenggara Timur": "NusaTenggaraTimur",
    "Papua": "Papua",
    "Papua Barat": "PapuaBarat",
    "Riau": "Riau",
    "Sulawesi Barat": "SulawesiBarat",
    "Sulawesi Selatan": "SulawesiSelatan",
    "Sulawesi Tengah": "SulawesiTengah",
    "Sulawesi Tenggara": "SulawesiTenggara",
    "Sulawesi Utara": "SulawesiUtara",
    "Sumatera Barat": "SumateraBarat",
    "Sumatera Selatan": "SumateraSelatan",
    "Sumatera Utara": "SumateraUtara",
}
GADM_TO_PROV = {v: k for k, v in PROV_TO_GADM.items()}


def _ensure_kode4(geo_kab: dict, id_field: str | None) -> None:
    for feat in geo_kab.get("features", []):
        props = feat.get("properties") or {}
        raw = props.get("_kode4")
        if raw is None and id_field:
            raw = props.get(id_field)
        if raw is None:
            raw = props.get("CC_2")
        if raw is not None:
            props["_kode4"] = str(raw).split(".")[0].zfill(4)[-4:]
        # mapping provinsi canonical
        gadm_prov = props.get("NAME_1")
        props["_prov_canon"] = GADM_TO_PROV.get(gadm_prov, gadm_prov)


def filter_geojson_by_province(geo_kab: dict, provinsi: str) -> dict:
    gadm = PROV_TO_GADM.get(provinsi)
    feats = [
        f
        for f in geo_kab.get("features", [])
        if f.get("properties", {}).get("NAME_1") == gadm
        or f.get("properties", {}).get("_prov_canon") == provinsi
    ]
    return {"type": "FeatureCollection", "features": feats}


def build_choropleth_frame(
    geo_kab: dict,
    analysis_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    mode: str = "kabupaten",
) -> pd.DataFrame:
    """Gabungkan poligon GeoJSON dengan data analisis."""
    rows = []
    for feat in geo_kab.get("features", []):
        props = feat.get("properties") or {}
        kode = props.get("_kode4")
        if not kode or kode in {"00NA", "None", "nan"}:
            continue
        rows.append(
            {
                "kode_kab_kota_str": str(kode).zfill(4)[-4:],
                "geo_name": props.get("NAME_2") or str(kode),
                "gadm_prov": props.get("NAME_1"),
                "provinsi_geo": props.get("_prov_canon"),
            }
        )
    base = pd.DataFrame(rows).drop_duplicates(subset=["kode_kab_kota_str"], keep="first")

    full = analysis_df.copy()
    full["kode_kab_kota_str"] = full["kode_kab_kota"].astype(int).astype(str).str.zfill(4)
    filt_codes = set(filtered_df["kode_kab_kota"].astype(int).astype(str).str.zfill(4))

    prov_agg = (
        full.groupby("provinsi_normalized", as_index=False)
        .agg(
            skor_provinsi=("priority_score", "mean"),
            stunting_provinsi=("stunting_pct", "mean"),
            kemiskinan_provinsi=("persen_penduduk_miskin", "mean"),
            n_kab=("kode_kab_kota", "count"),
            n_q4=("prioritas_kategori", lambda s: int((s == "Q4 Sangat Tinggi").sum())),
        )
    )

    merged = base.merge(
        full[
            [
                "kode_kab_kota_str",
                "kabupaten_kota_normalized",
                "provinsi_normalized",
                "prioritas_kategori",
                "priority_score",
                "stunting_pct",
                "persen_penduduk_miskin",
                "ikp",
                "jumlah_peserta_didik",
                "cluster_label",
            ]
        ],
        on="kode_kab_kota_str",
        how="left",
    )
    # isi provinsi dari geo jika data analisis kosong
    merged["provinsi_normalized"] = merged["provinsi_normalized"].fillna(merged["provinsi_geo"])
    merged = merged.merge(prov_agg, on="provinsi_normalized", how="left")

    if mode == "provinsi":
        # warna seragam per provinsi = rata-rata skor (tampilan nasional)
        merged["warna_nilai"] = merged["skor_provinsi"]
        merged["label"] = merged.apply(
            lambda r: (
                f"{r['provinsi_normalized']} · skor rata-rata {r['skor_provinsi']:.1f}"
                if pd.notna(r.get("skor_provinsi"))
                else f"{r.get('provinsi_geo') or r.get('gadm_prov')} (tanpa data)"
            ),
            axis=1,
        )
    else:
        def map_color(row):
            if pd.isna(row.get("prioritas_kategori")):
                return "Tanpa data"
            if row["kode_kab_kota_str"] not in filt_codes:
                return "Di luar filter"
            return row["prioritas_kategori"]

        merged["warna_peta"] = merged.apply(map_color, axis=1)
        merged["label"] = merged.apply(
            lambda r: (
                f"{r['kabupaten_kota_normalized']}, {r['provinsi_normalized']}"
                if pd.notna(r.get("kabupaten_kota_normalized"))
                else f"{r['geo_name']} (tanpa data analisis)"
            ),
            axis=1,
        )
    return merged


def page_peta(df: pd.DataFrame) -> None:
    st.header("Peta Prioritas MBG")
    st.caption(
        "Mulai dari peta **provinsi**, lalu pilih/klik provinsi untuk melihat pecahan "
        "**kabupaten/kota**."
    )

    opts = ["— Nasional (agregat provinsi) —"] + sorted(
        df["provinsi_normalized"].dropna().unique().tolist()
    )
    top_l, top_r = st.columns([3, 1])
    with top_l:
        chosen = st.selectbox("Level peta / pilih provinsi", opts, key="map_prov_select")
    with top_r:
        st.write("")
        st.write("")
        if not str(chosen).startswith("—") and st.button("◀ Nasional", use_container_width=True):
            st.session_state.map_prov_select = opts[0]
            st.rerun()

    drill_prov = None if str(chosen).startswith("—") else chosen
    base_df = df if not drill_prov else df[df["provinsi_normalized"] == drill_prov]
    filtered = filter_panel(base_df, "map")

    codes = tuple(sorted(df["kode_kab_kota"].astype(int).astype(str).str.zfill(4).unique().tolist()))
    geo_kab, id_field = load_geojson_kab(codes)

    if not geo_kab:
        st.warning("GeoJSON kabupaten tidak tersedia.")
        return

    _ensure_kode4(geo_kab, id_field)

    if not drill_prov:
        st.subheader("Level 1 — Agregat Provinsi")
        plot_df = build_choropleth_frame(geo_kab, df, filtered, mode="provinsi")
        fig = px.choropleth(
            plot_df,
            geojson=geo_kab,
            locations="kode_kab_kota_str",
            featureidkey="properties._kode4",
            color="warna_nilai",
            color_continuous_scale="YlOrRd",
            hover_name="label",
            hover_data={
                "provinsi_normalized": True,
                "skor_provinsi": ":.1f",
                "stunting_provinsi": ":.1f",
                "kemiskinan_provinsi": ":.1f",
                "n_kab": True,
                "n_q4": True,
                "kode_kab_kota_str": False,
                "warna_nilai": False,
            },
            labels={
                "warna_nilai": "Skor rata-rata provinsi",
                "provinsi_normalized": "Provinsi",
                "skor_provinsi": "Skor rata-rata",
                "stunting_provinsi": "Stunting %",
                "kemiskinan_provinsi": "Kemiskinan %",
                "n_kab": "Jumlah kab/kota teranalisis",
                "n_q4": "Jumlah Q4",
            },
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(
            height=620,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_colorbar=dict(title="Skor prov."),
        )
        st.plotly_chart(fig, use_container_width=True, key="map_nasional")
        st.caption(
            "Warna = rata-rata skor prioritas per provinsi (semua kab di provinsi yang sama "
            "berwarna seragam). Pilih provinsi di dropdown untuk melihat detail kab/kota."
        )

        # tabel ringkas provinsi + tombol cepat
        prov_tbl = (
            df.groupby("provinsi_normalized", as_index=False)
            .agg(
                skor_rata=("priority_score", "mean"),
                stunting=("stunting_pct", "mean"),
                kemiskinan=("persen_penduduk_miskin", "mean"),
                n=("kode_kab_kota", "count"),
            )
            .sort_values("skor_rata", ascending=False)
        )
        st.dataframe(
            prov_tbl.rename(
                columns={
                    "provinsi_normalized": "Provinsi",
                    "skor_rata": "Skor rata-rata",
                    "stunting": "Stunting %",
                    "kemiskinan": "Kemiskinan %",
                    "n": "Kab/kota",
                }
            ),
            use_container_width=True,
            height=280,
            hide_index=True,
        )
        quick = st.selectbox(
            "Atau klik cepat drill-down dari daftar skor tertinggi",
            ["—"] + prov_tbl["provinsi_normalized"].head(15).tolist(),
            key="map_quick_prov",
        )
        if quick != "—":
            st.session_state.map_prov_select = quick
            st.rerun()
        return

    # ---- Level 2: kabupaten dalam provinsi ----
    st.subheader(f"Level 2 — Kabupaten/Kota di {drill_prov}")
    geo_prov = filter_geojson_by_province(geo_kab, drill_prov)
    if not geo_prov["features"]:
        st.warning(
            f"Batas GeoJSON untuk {drill_prov} tidak ditemukan di file peta. "
            "Menampilkan tabel saja."
        )
    else:
        plot_df = build_choropleth_frame(geo_prov, df, filtered, mode="kabupaten")
        fig = px.choropleth(
            plot_df,
            geojson=geo_prov,
            locations="kode_kab_kota_str",
            featureidkey="properties._kode4",
            color="warna_peta",
            color_discrete_map=PRIORITY_COLORS,
            category_orders={"warna_peta": PRIORITY_ORDER},
            hover_name="label",
            hover_data={
                "priority_score": ":.1f",
                "stunting_pct": ":.1f",
                "persen_penduduk_miskin": ":.1f",
                "ikp": ":.1f",
                "jumlah_peserta_didik": ":,.0f",
                "cluster_label": True,
                "kode_kab_kota_str": False,
                "warna_peta": True,
            },
            labels={
                "warna_peta": "Kuartil prioritas",
                "priority_score": "Skor",
                "stunting_pct": "Stunting %",
                "persen_penduduk_miskin": "Kemiskinan %",
                "ikp": "IKP",
                "jumlah_peserta_didik": "Peserta didik",
                "cluster_label": "Cluster",
            },
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=0), legend_title="Kuartil")
        st.plotly_chart(fig, use_container_width=True, key=f"map_kab_{drill_prov}")
        st.caption(
            f"Detail kab/kota di **{drill_prov}**. Abu-abu = tanpa data lengkap. "
            f"Filter aktif: {len(filtered)} wilayah."
        )

    st.subheader(f"Daftar wilayah — {drill_prov}")
    show = filtered if len(filtered) else df[df["provinsi_normalized"] == drill_prov]
    st.dataframe(
        show.sort_values("rank")[
            [
                "rank",
                "kabupaten_kota_normalized",
                "provinsi_normalized",
                "prioritas_kategori",
                "priority_score",
                "stunting_pct",
                "persen_penduduk_miskin",
                "ikp",
                "jumlah_peserta_didik",
                "cluster_label",
            ]
        ].rename(
            columns={
                "rank": "Ranking",
                "kabupaten_kota_normalized": "Kabupaten/Kota",
                "provinsi_normalized": "Provinsi",
                "prioritas_kategori": "Prioritas",
                "priority_score": "Skor",
                "stunting_pct": "Stunting (%)",
                "persen_penduduk_miskin": "Kemiskinan (%)",
                "ikp": "IKP",
                "jumlah_peserta_didik": "Peserta Didik",
                "cluster_label": "Cluster",
            }
        ),
        use_container_width=True,
        height=320,
    )


def page_ranking(df: pd.DataFrame) -> None:
    st.header("Ranking Wilayah Prioritas")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Cari wilayah / provinsi", "")
    with c2:
        prov = st.selectbox(
            "Filter provinsi",
            ["Semua"] + sorted(df["provinsi_normalized"].unique().tolist()),
            key="rank_prov",
        )
    with c3:
        only_top10 = st.checkbox("Highlight Top 10 saja", value=False)

    view = df.copy()
    if prov != "Semua":
        view = view[view["provinsi_normalized"] == prov]
    if q.strip():
        qq = q.strip().lower()
        view = view[
            view["kabupaten_kota_normalized"].str.lower().str.contains(qq, na=False)
            | view["provinsi_normalized"].str.lower().str.contains(qq, na=False)
        ]
    if only_top10:
        view = view.nsmallest(10, "rank")

    table = view.sort_values("rank")[
        [
            "rank",
            "kabupaten_kota_normalized",
            "provinsi_normalized",
            "priority_score",
            "stunting_pct",
            "persen_penduduk_miskin",
            "ikp",
            "jumlah_peserta_didik",
            "prioritas_kategori",
            "rekomendasi",
            "cluster_label",
        ]
    ].rename(
        columns={
            "rank": "Ranking",
            "kabupaten_kota_normalized": "Kabupaten/Kota",
            "provinsi_normalized": "Provinsi",
            "priority_score": "Skor Prioritas",
            "stunting_pct": "Stunting",
            "persen_penduduk_miskin": "Kemiskinan",
            "ikp": "IKP",
            "jumlah_peserta_didik": "Peserta Didik",
            "prioritas_kategori": "Prioritas",
            "rekomendasi": "Rekomendasi",
            "cluster_label": "Cluster",
        }
    )

    st.dataframe(table, use_container_width=True, height=520)
    st.download_button(
        "Unduh CSV hasil ranking",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="ranking_prioritas_mbg.csv",
        mime="text/csv",
    )


def page_profil(df: pd.DataFrame) -> None:
    st.header("Profil Detail Kabupaten/Kota")
    means = national_means(df)

    options = (
        df.assign(
            opt=df["kabupaten_kota_normalized"] + " — " + df["provinsi_normalized"]
        )
        .sort_values("rank")["opt"]
        .tolist()
    )
    choice = st.selectbox("Pilih wilayah", options)
    row = df[
        (df["kabupaten_kota_normalized"] + " — " + df["provinsi_normalized"]) == choice
    ].iloc[0]

    st.subheader(f"{row['kabupaten_kota_normalized']}")
    st.caption(
        f"{row['provinsi_normalized']} · {row['tipe_wilayah']} · "
        f"Ranking #{int(row['rank'])} · {row['prioritas_kategori']} · {row['rekomendasi']}"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Skor Prioritas", format_number(row["priority_score"], "score"))
    m2.metric("Vulnerability", format_number(row["vulnerability_score"], "score"))
    m3.metric("Service Need", format_number(row["service_need_score"], "score"))
    m4.metric("Peserta Didik", format_number(row["jumlah_peserta_didik"]))

    reason = auto_reason(row, means)
    st.markdown(f'<div class="reason-box">{reason}</div>', unsafe_allow_html=True)

    compare = pd.DataFrame(
        {
            "Indikator": ["Stunting (%)", "Kemiskinan (%)", "IKP", "Peserta didik"],
            "Wilayah": [
                row["stunting_pct"],
                row["persen_penduduk_miskin"],
                row["ikp"],
                row["jumlah_peserta_didik"],
            ],
            "Nasional": [
                means["stunting_pct"],
                means["persen_penduduk_miskin"],
                means["ikp"],
                means["jumlah_peserta_didik"],
            ],
        }
    )

    left, right = st.columns(2)
    with left:
        # normalisasi visual terpisah per indikator → gunakan % dari nasional
        viz = compare.copy()
        # untuk chart, skala peserta ke ribuan agar terbaca
        viz.loc[viz["Indikator"] == "Peserta didik", "Wilayah"] = (
            viz.loc[viz["Indikator"] == "Peserta didik", "Wilayah"] / 1000
        )
        viz.loc[viz["Indikator"] == "Peserta didik", "Nasional"] = (
            viz.loc[viz["Indikator"] == "Peserta didik", "Nasional"] / 1000
        )
        viz.loc[viz["Indikator"] == "Peserta didik", "Indikator"] = "Peserta didik (ribu)"
        long = viz.melt(id_vars="Indikator", var_name="Sumber", value_name="Nilai")
        fig = px.bar(
            long,
            x="Indikator",
            y="Nilai",
            color="Sumber",
            barmode="group",
            title="Indikator wilayah vs rata-rata nasional",
            color_discrete_map={"Wilayah": "#ea580c", "Nasional": "#64748b"},
        )
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        radar = go.Figure()
        radar.add_trace(
            go.Scatterpolar(
                r=[
                    row["pct_stunting"],
                    row["pct_kemiskinan"],
                    100 - row["pct_ikp"],  # invert: IKP rendah = lebih rentan
                    row["pct_peserta"],
                    row["pct_priority"],
                ],
                theta=["Stunting", "Kemiskinan", "Kerentanan IKP", "Peserta didik", "Prioritas"],
                fill="toself",
                name="Percentile",
            )
        )
        radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="Percentile rank wilayah (0–100)",
            height=380,
            margin=dict(t=50, b=20),
        )
        st.plotly_chart(radar, use_container_width=True)

    st.markdown(
        f"""
| Indikator | Wilayah | Nasional | Percentile |
|---|---:|---:|---:|
| Stunting | {row['stunting_pct']:.1f}% | {means['stunting_pct']:.1f}% | {row['pct_stunting']:.0f} |
| Kemiskinan | {row['persen_penduduk_miskin']:.1f}% | {means['persen_penduduk_miskin']:.1f}% | {row['pct_kemiskinan']:.0f} |
| IKP | {row['ikp']:.1f} | {means['ikp']:.1f} | {row['pct_ikp']:.0f} |
| Peserta didik | {int(row['jumlah_peserta_didik']):,} | {int(means['jumlah_peserta_didik']):,} | {row['pct_peserta']:.0f} |
| Priority score | {row['priority_score']:.1f} | {means['priority_score']:.1f} | {row['pct_priority']:.0f} |
""".replace(",", ".")
    )


def page_hubungan(df: pd.DataFrame) -> None:
    st.header("Analisis Hubungan Antarindikator")
    st.caption(
        "Menjelaskan korelasi antar faktor terkait kebutuhan MBG — "
        "bukan klaim sebab-akibat."
    )
    means = national_means(df)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(
            df,
            x="persen_penduduk_miskin",
            y="stunting_pct",
            color="prioritas_kategori",
            color_discrete_map=PRIORITY_COLORS,
            category_orders={"prioritas_kategori": PRIORITY_ORDER},
            hover_name="kabupaten_kota_normalized",
            trendline="ols",
            labels={
                "persen_penduduk_miskin": "Kemiskinan (%)",
                "stunting_pct": "Stunting (%)",
            },
            title="Hubungan stunting vs kemiskinan",
        )
        fig.add_vline(x=means["persen_penduduk_miskin"], line_dash="dash", line_color="#64748b")
        fig.add_hline(y=means["stunting_pct"], line_dash="dash", line_color="#64748b")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Garis putus-putus = rata-rata nasional. "
            "Kuadran kanan-atas: kerentanan ganda (stunting & kemiskinan tinggi)."
        )
    with c2:
        fig = px.scatter(
            df,
            x="ikp",
            y="stunting_pct",
            color="prioritas_kategori",
            color_discrete_map=PRIORITY_COLORS,
            category_orders={"prioritas_kategori": PRIORITY_ORDER},
            hover_name="kabupaten_kota_normalized",
            trendline="ols",
            labels={"ikp": "Skor IKP", "stunting_pct": "Stunting (%)"},
            title="Hubungan stunting vs IKP",
        )
        fig.add_vline(x=means["ikp"], line_dash="dash", line_color="#64748b")
        fig.add_hline(y=means["stunting_pct"], line_dash="dash", line_color="#64748b")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig = px.scatter(
            df,
            x="jumlah_peserta_didik",
            y="priority_score",
            color="cluster_label",
            hover_name="kabupaten_kota_normalized",
            trendline="ols",
            labels={
                "jumlah_peserta_didik": "Jumlah peserta didik (total)",
                "priority_score": "Skor prioritas relatif",
            },
            title="Skor prioritas vs jumlah peserta didik",
        )
        fig.update_layout(height=400, legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        fig = px.box(
            df,
            x="kelompok_ikp",
            y="stunting_pct",
            color="kelompok_ikp",
            labels={"kelompok_ikp": "Kelompok IKP", "stunting_pct": "Stunting (%)"},
            title="Sebaran stunting berdasarkan kategori IKP",
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    corr = df[
        ["stunting_pct", "persen_penduduk_miskin", "ikp", "jumlah_peserta_didik", "priority_score"]
    ].corr(method="pearson")
    corr = corr.rename(
        index={
            "stunting_pct": "Stunting",
            "persen_penduduk_miskin": "Kemiskinan",
            "ikp": "IKP",
            "jumlah_peserta_didik": "Peserta didik",
            "priority_score": "Skor prioritas",
        },
        columns={
            "stunting_pct": "Stunting",
            "persen_penduduk_miskin": "Kemiskinan",
            "ikp": "IKP",
            "jumlah_peserta_didik": "Peserta didik",
            "priority_score": "Skor prioritas",
        },
    )
    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title="Heatmap korelasi Pearson",
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    r_sk = float(corr.loc["Stunting", "Kemiskinan"])
    r_si = float(corr.loc["Stunting", "IKP"])
    r_sp = float(corr.loc["Skor prioritas", "Peserta didik"])
    st.markdown(
        f"""
**Insight (korelasi, bukan sebab-akibat)**
- Stunting ↔ kemiskinan: **r = {r_sk:.2f}**
- Stunting ↔ IKP: **r = {r_si:.2f}** (IKP tinggi cenderung berhubungan dengan stunting lebih rendah)
- Skor prioritas ↔ peserta didik: **r = {r_sp:.2f}** — banyak siswa tidak otomatis berarti prioritas tertinggi
"""
    )


def page_cluster(df: pd.DataFrame, meta: dict) -> None:
    st.header("Segmentasi / Cluster Wilayah")
    cl = meta["cluster"]
    a, b, c = st.columns(3)
    a.metric("Jumlah cluster terbaik (silhouette)", cl["best_k"])
    b.metric("Silhouette score", f"{cl['best_silhouette']:.3f}")
    c.metric("Wilayah terklaster", len(df))

    st.warning(cl.get("note", "Segmentasi bersifat eksploratif."))

    profile = pd.DataFrame(cl["cluster_profile"])
    if "cluster_label" not in profile.columns and "cluster_id" in profile.columns:
        profile = profile.assign(
            cluster_label=profile["cluster_id"].astype(str).map(
                {str(k): v for k, v in cl["cluster_names"].items()}
            )
        )

    st.subheader("Profil cluster (mean + median peserta didik)")
    show_cols = [
        c
        for c in [
            "cluster_label",
            "n_wilayah",
            "stunting_pct",
            "persen_penduduk_miskin",
            "ikp",
            "jumlah_peserta_didik",
            "median_peserta_didik",
        ]
        if c in profile.columns
    ]
    st.dataframe(
        profile[show_cols].rename(
            columns={
                "cluster_label": "Cluster",
                "n_wilayah": "Jumlah wilayah",
                "stunting_pct": "Stunting (mean)",
                "persen_penduduk_miskin": "Kemiskinan (mean)",
                "ikp": "IKP (mean)",
                "jumlah_peserta_didik": "Peserta didik (mean)",
                "median_peserta_didik": "Peserta didik (median)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    zprof = pd.DataFrame(cl.get("cluster_profile_z") or [])
    if not zprof.empty:
        id_col = "cluster_label" if "cluster_label" in zprof.columns else "cluster_id"
        long = zprof.melt(
            id_vars=[id_col],
            value_vars=["stunting_pct", "persen_penduduk_miskin", "ikp", "jumlah_peserta_didik"],
            var_name="indikator",
            value_name="zscore",
        )
        long["indikator"] = long["indikator"].map(
            {
                "stunting_pct": "Stunting",
                "persen_penduduk_miskin": "Kemiskinan",
                "ikp": "IKP",
                "jumlah_peserta_didik": "Peserta didik",
            }
        )
        fig = px.bar(
            long,
            x=id_col,
            y="zscore",
            color="indikator",
            barmode="group",
            title="Profil indikator terstandardisasi (z-score) per cluster",
            labels={id_col: "Cluster", "zscore": "Z-score"},
        )
        fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8")
        fig.update_layout(height=420, xaxis_tickangle=-15)
        st.plotly_chart(fig, use_container_width=True)

    means = national_means(df)
    fig = px.scatter(
        df,
        x="persen_penduduk_miskin",
        y="stunting_pct",
        color="cluster_label",
        size="jumlah_peserta_didik",
        hover_name="kabupaten_kota_normalized",
        title="Scatter cluster (ukuran = peserta didik)",
        labels={
            "persen_penduduk_miskin": "Kemiskinan (%)",
            "stunting_pct": "Stunting (%)",
            "cluster_label": "Cluster",
        },
    )
    fig.add_vline(x=means["persen_penduduk_miskin"], line_dash="dash", line_color="#64748b")
    fig.add_hline(y=means["stunting_pct"], line_dash="dash", line_color="#64748b")
    fig.update_layout(height=480, legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, use_container_width=True)

    s1, s2 = st.columns(2)
    with s1:
        sil = pd.DataFrame(
            [{"k": int(k), "silhouette": v} for k, v in cl["silhouette_scores"].items()]
        ).sort_values("k")
        fig = px.line(
            sil,
            x="k",
            y="silhouette",
            markers=True,
            title="Silhouette score untuk pemilihan k",
        )
        fig.add_vline(x=cl["best_k"], line_dash="dash", line_color="#ea580c")
        st.plotly_chart(fig, use_container_width=True)
    with s2:
        if cl.get("inertia_scores"):
            ine = pd.DataFrame(
                [{"k": int(k), "inertia": v} for k, v in cl["inertia_scores"].items()]
            ).sort_values("k")
            fig = px.line(
                ine,
                x="k",
                y="inertia",
                markers=True,
                title="Elbow curve (within-cluster sum of squares)",
            )
            fig.add_vline(x=cl["best_k"], line_dash="dash", line_color="#ea580c")
            st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"k={cl['best_k']} dipilih karena silhouette tertinggi pada rentang yang diuji. "
        f"Nilai {cl['best_silhouette']:.3f} menunjukkan pemisahan ada tetapi tidak tajam — "
        "cluster dipakai untuk memahami tipe kebutuhan, bukan standar resmi."
    )


def page_komponen(df: pd.DataFrame) -> None:
    st.header("Komponen Skor Prioritas")
    st.markdown(
        f"""
**Vulnerability Score** dibentuk dari stunting, kemiskinan, dan IKP (**dibalik** setelah normalisasi).  
**Service Need Score** dibentuk dari **total** jumlah peserta didik (bukan data residu).  

**Priority Score** = kombinasi berbobot keduanya.

> {METHODOLOGY_NOTES["ikp_invert"]}
"""
    )

    wdf = pd.DataFrame(
        {
            "Komponen": ["Stunting", "Kemiskinan", "Ketahanan pangan (IKP)", "Jumlah peserta didik"],
            "Bobot": [
                DEFAULT_WEIGHTS["stunting"],
                DEFAULT_WEIGHTS["kemiskinan"],
                DEFAULT_WEIGHTS["ikp"],
                DEFAULT_WEIGHTS["peserta_didik"],
            ],
            "Kelompok": ["Vulnerability", "Vulnerability", "Vulnerability", "Service Need"],
        }
    )
    fig = px.bar(
        wdf,
        x="Bobot",
        y="Komponen",
        color="Kelompok",
        orientation="h",
        text=wdf["Bobot"].map(lambda x: f"{x:.0%}"),
        title="Bobot default (uji lewat Sensitivity Analysis — bukan final absolut)",
    )
    fig.update_layout(height=320, xaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

    sorted_df = df.sort_values("rank")
    pilihan = st.selectbox(
        "Contoh dekomposisi skor wilayah",
        (sorted_df["kabupaten_kota_normalized"] + " — " + sorted_df["provinsi_normalized"]).tolist(),
    )
    row = df[
        (df["kabupaten_kota_normalized"] + " — " + df["provinsi_normalized"]) == pilihan
    ].iloc[0]

    decomp = pd.DataFrame(
        {
            "Komponen": ["Stunting", "Kemiskinan", "IKP", "Peserta didik"],
            "Kontribusi": [
                row["contrib_stunting"],
                row["contrib_kemiskinan"],
                row["contrib_ikp"],
                row["contrib_peserta"],
            ],
        }
    )
    fig = px.bar(
        decomp,
        x="Komponen",
        y="Kontribusi",
        title=f"Score decomposition — {row['kabupaten_kota_normalized']}",
        text=decomp["Kontribusi"].map(lambda x: f"{x:.1f}"),
        color="Komponen",
    )
    fig.update_layout(height=360, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    top = df.nsmallest(15, "rank")
    stacked = top.melt(
        id_vars=["kabupaten_kota_normalized"],
        value_vars=["contrib_stunting", "contrib_kemiskinan", "contrib_ikp", "contrib_peserta"],
        var_name="komponen",
        value_name="kontribusi",
    )
    stacked["komponen"] = stacked["komponen"].map(
        {
            "contrib_stunting": "Stunting",
            "contrib_kemiskinan": "Kemiskinan",
            "contrib_ikp": "IKP",
            "contrib_peserta": "Peserta didik",
        }
    )
    fig = px.bar(
        stacked,
        x="kabupaten_kota_normalized",
        y="kontribusi",
        color="komponen",
        title="Stacked contribution — Top 15 prioritas",
        labels={"kabupaten_kota_normalized": "Wilayah", "kontribusi": "Kontribusi skor"},
    )
    fig.update_layout(height=420, xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)

    # radar satu wilayah
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=[
                row["n_stunting"],
                row["n_kemiskinan"],
                row["n_ikp"],
                row["n_peserta"],
            ],
            theta=["Stunting", "Kemiskinan", "IKP (invert)", "Peserta didik"],
            fill="toself",
            name=row["kabupaten_kota_normalized"],
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Radar skor ternormalisasi wilayah terpilih",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def page_sensitivity(df: pd.DataFrame) -> None:
    st.header("Sensitivity Analysis")
    st.caption(
        "Membandingkan ranking pada beberapa skenario bobot untuk menilai kestabilan rekomendasi."
    )

    sens = load_sensitivity()
    scen_df = pd.DataFrame(
        [
            {
                "Skenario": name,
                "Kerentanan": f"{w['stunting']+w['kemiskinan']+w['ikp']:.0%}",
                "Peserta Didik": f"{w['peserta_didik']:.0%}",
                "Detail": (
                    f"S {w['stunting']:.0%} · K {w['kemiskinan']:.0%} · "
                    f"IKP {w['ikp']:.0%} · PD {w['peserta_didik']:.0%}"
                ),
            }
            for name, w in WEIGHT_SCENARIOS.items()
        ]
    )
    st.dataframe(scen_df, use_container_width=True, hide_index=True)

    # wilayah yang selalu top 10
    top_flags = (
        sens.groupby("kode_kab_kota")
        .agg(
            kabupaten=("kabupaten_kota_normalized", "first"),
            provinsi=("provinsi_normalized", "first"),
            n_top10=("in_top10", "sum"),
            mean_rank=("rank", "mean"),
            std_rank=("rank", "std"),
        )
        .reset_index()
    )
    always = top_flags[top_flags["n_top10"] == len(WEIGHT_SCENARIOS)].sort_values("mean_rank")
    st.subheader("Wilayah yang selalu masuk Top 10")
    if always.empty:
        st.write("Tidak ada wilayah yang konsisten di Top 10 pada semua skenario.")
    else:
        st.dataframe(
            always[["kabupaten", "provinsi", "mean_rank", "std_rank"]].rename(
                columns={
                    "kabupaten": "Kabupaten/Kota",
                    "provinsi": "Provinsi",
                    "mean_rank": "Rata-rata ranking",
                    "std_rank": "Std ranking",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    # rank change chart for top stable + volatile
    focus_ids = (
        top_flags.sort_values(["n_top10", "mean_rank"], ascending=[False, True])
        .head(12)["kode_kab_kota"]
        .tolist()
    )
    focus = sens[sens["kode_kab_kota"].isin(focus_ids)]
    fig = px.line(
        focus,
        x="skenario",
        y="rank",
        color="kabupaten_kota_normalized",
        markers=True,
        title="Perubahan ranking antar skenario (wilayah fokus)",
        labels={"rank": "Ranking (1 = tertinggi)", "skenario": "Skenario"},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=480, legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tingkat kestabilan rekomendasi")
    top_flags["kestabilan"] = np.where(
        top_flags["std_rank"].fillna(0) <= 5,
        "Stabil",
        np.where(top_flags["std_rank"] <= 15, "Cukup stabil", "Sensitif terhadap bobot"),
    )
    stab = top_flags["kestabilan"].value_counts().rename_axis("Kategori").reset_index(name="Jumlah")
    fig = px.pie(stab, names="Kategori", values="Jumlah", hole=0.4, title="Distribusi kestabilan ranking")
    st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Unduh hasil sensitivity (CSV)",
        data=sens.to_csv(index=False).encode("utf-8-sig"),
        file_name="sensitivity_ranks.csv",
        mime="text/csv",
    )


def main() -> None:
    inject_css()
    try:
        df = load_analysis()
        meta = load_meta()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    page = sidebar_nav()
    if page.startswith("1"):
        page_ringkasan(df, meta)
    elif page.startswith("2"):
        page_peta(df)
    elif page.startswith("3"):
        page_ranking(df)
    elif page.startswith("4"):
        page_profil(df)
    elif page.startswith("5"):
        page_hubungan(df)
    elif page.startswith("6"):
        page_cluster(df, meta)
    elif page.startswith("7"):
        page_komponen(df)
    else:
        page_sensitivity(df)


if __name__ == "__main__":
    main()
