"""
Prioritas MBG dan Early Warning Wilayah — dashboard decision-first.
Jalankan: python -m streamlit run app.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    ACTUAL_END_YEAR,
    DEFAULT_WEIGHTS,
    DECISION_STATUS_ORDER,
    EARLY_WARNING_DELTA,
    METHODOLOGY_NOTES,
    PROJECTION_LABEL,
    PROJECTION_YEAR,
    REFERENCE_WILAYAH_TOTAL,
    STATUS_COLORS,
    STATUS_EARLY_WARNING,
    STATUS_PEMANTAUAN,
    STATUS_PERTAHANKAN,
    STATUS_PRIORITAS_UTAMA,
)
from decisions import (  # noqa: E402
    action_checklist,
    build_auto_insight,
    build_executive_narrative,
    decision_counts,
    enrich_decision_columns,
    get_decision_status,
    get_status_color,
    get_status_icon,
    sort_decision_table,
    sorted_contribution_shares,
    status_why_short,
    top_region_for_status,
    trend_card_copy,
)
from loaders import (  # noqa: E402
    format_number,
    load_analysis,
    load_excluded,
    load_geojson_kab,
    load_meta,
)

st.set_page_config(
    page_title="Prioritas MBG dan Early Warning Wilayah",
    page_icon="🍚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAP_MODES = {}  # peta tetap mode status keputusan (tidak diganti user)

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


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 1.5rem; max-width: 1400px; }
        h1 { font-size: 1.55rem !important; margin-bottom: 0.15rem !important; }
        h2, h3 { margin-top: 0.4rem !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.4rem; }
        .subhead { color: #475569; font-size: 0.95rem; margin: 0 0 0.35rem 0; }
        .disclaimer {
            color: #64748b; font-size: 0.8rem; border-left: 3px solid #cbd5e1;
            padding: 0.35rem 0.65rem; margin: 0.25rem 0 0.6rem 0; background: #f8fafc;
            border-radius: 0 6px 6px 0;
        }
        .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.65rem; margin-bottom: 0.5rem; }
        @media (max-width: 900px) { .kpi-grid { grid-template-columns: 1fr 1fr; } }
        .kpi-card {
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.75rem 0.85rem; min-height: 108px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .kpi-card .label { font-size: 0.78rem; color: #64748b; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.02em; }
        .kpi-card .value { font-size: 1.45rem; font-weight: 700; color: #0f172a;
            line-height: 1.2; margin: 0.2rem 0; word-break: break-word; }
        .kpi-card .sub { font-size: 0.78rem; color: #475569; line-height: 1.35; }
        .kpi-card.accent-red { border-top: 3px solid #991B1B; }
        .kpi-card.accent-orange { border-top: 3px solid #EA580C; }
        .kpi-card.accent-slate { border-top: 3px solid #475569; }
        .kpi-card.accent-green { border-top: 3px solid #15803D; }
        .status-chip {
            display: inline-block; padding: 0.2rem 0.55rem; border-radius: 999px;
            font-size: 0.78rem; font-weight: 600; color: #fff; white-space: nowrap;
        }
        .detail-box {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.85rem 1rem;
        }
        .detail-box h4 { margin: 0 0 0.45rem 0; font-size: 0.95rem; color: #0f172a; }
        .detail-box ul { margin: 0.25rem 0 0.6rem 1.1rem; padding: 0; color: #334155;
            font-size: 0.88rem; line-height: 1.45; }
        .detail-box .action {
            background: #fff7ed; border-left: 3px solid #ea580c; padding: 0.5rem 0.7rem;
            border-radius: 0 6px 6px 0; font-size: 0.88rem; color: #9a3412; margin: 0.4rem 0;
        }
        .ctx { font-size: 0.78rem; color: #64748b; margin-top: 0.4rem; }
        .ind-card {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.7rem 0.8rem; height: 100%;
        }
        .ind-card .name { font-size: 0.78rem; color: #64748b; font-weight: 600; }
        .ind-card .val { font-size: 1.25rem; font-weight: 700; color: #0f172a; margin: 0.15rem 0; }
        .ind-card .meta { font-size: 0.78rem; color: #475569; line-height: 1.35; }
        .ind-card.dom { border-color: #fdba74; background: #fffbeb; }
        /* —— Decision detail page —— */
        .dec-exec {
            border-radius: 12px; padding: 1.1rem 1.25rem 1rem;
            border: 1px solid #e2e8f0; background: #fff;
            box-shadow: 0 1px 3px rgba(15,23,42,0.06);
            margin-bottom: 0.75rem;
        }
        .dec-exec .badge {
            display: inline-block; padding: 0.28rem 0.75rem; border-radius: 6px;
            font-size: 0.8rem; font-weight: 700; letter-spacing: 0.04em;
            color: #fff; text-transform: uppercase; margin-bottom: 0.55rem;
        }
        .dec-exec h2 {
            margin: 0; font-size: 1.45rem !important; color: #0f172a;
            font-weight: 700; line-height: 1.2;
        }
        .dec-exec .prov { color: #64748b; font-size: 0.95rem; margin: 0.15rem 0 0.75rem; }
        .dec-exec-grid {
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem;
            margin-top: 0.35rem;
        }
        @media (max-width: 900px) {
            .dec-exec-grid { grid-template-columns: 1fr 1fr; }
        }
        .dec-exec-grid .cell .lbl {
            font-size: 0.72rem; color: #64748b; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.03em;
        }
        .dec-exec-grid .cell .val {
            font-size: 1.35rem; font-weight: 700; color: #0f172a; margin-top: 0.15rem;
        }
        .dec-exec-grid .cell .val.up { color: #991B1B; }
        .dec-exec-grid .cell .val.down { color: #15803D; }
        .dec-narrative {
            margin: 0.85rem 0 0; padding: 0.75rem 0.9rem;
            background: #f8fafc; border-radius: 8px; border-left: 3px solid #94a3b8;
            font-size: 0.92rem; color: #334155; line-height: 1.55;
        }
        .why-grid {
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.65rem;
            margin: 0.5rem 0 1rem;
        }
        @media (max-width: 900px) { .why-grid { grid-template-columns: 1fr 1fr; } }
        .why-card {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.85rem 0.9rem; min-height: 118px;
        }
        .why-card .ico { font-size: 1.1rem; margin-bottom: 0.2rem; }
        .why-card .lbl {
            font-size: 0.72rem; color: #64748b; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.03em;
        }
        .why-card .val {
            font-size: 1.2rem; font-weight: 700; color: #0f172a;
            margin: 0.25rem 0 0.15rem; line-height: 1.25;
        }
        .why-card .sub { font-size: 0.8rem; color: #475569; line-height: 1.35; }
        .action-panel {
            border-radius: 12px; padding: 1rem 1.15rem;
            border: 1px solid #fed7aa; background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
            margin: 0.4rem 0 1rem;
        }
        .action-panel.prioritas {
            border-color: #fecaca;
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        }
        .action-panel.hijau {
            border-color: #bbf7d0;
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        }
        .action-panel.biru {
            border-color: #bfdbfe;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        }
        .action-panel h4 {
            margin: 0 0 0.55rem 0; font-size: 0.95rem; color: #9a3412;
        }
        .action-panel.prioritas h4 { color: #991B1B; }
        .action-panel.hijau h4 { color: #166534; }
        .action-panel.biru h4 { color: #1e40af; }
        .action-panel ul {
            margin: 0; padding: 0; list-style: none;
        }
        .action-panel li {
            font-size: 0.95rem; font-weight: 600; color: #1c1917;
            padding: 0.35rem 0; border-bottom: 1px solid rgba(0,0,0,0.05);
        }
        .action-panel li:last-child { border-bottom: none; }
        .insight-card {
            border-radius: 12px; padding: 1rem 1.15rem;
            border: 1px solid #c7d2fe;
            background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
            margin: 0.5rem 0 0.8rem;
        }
        .insight-card h4 {
            margin: 0 0 0.4rem 0; font-size: 0.9rem; color: #3730a3;
            text-transform: uppercase; letter-spacing: 0.04em;
        }
        .insight-card p {
            margin: 0; font-size: 0.92rem; color: #312e81; line-height: 1.55;
        }
        .sec-title {
            font-size: 1.05rem; font-weight: 700; color: #0f172a;
            margin: 1.1rem 0 0.35rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def region_key(row: pd.Series | dict) -> str:
    return f"{row['kabupaten_kota_normalized']} — {row['provinsi_normalized']}"


@st.cache_data(show_spinner=False)
def prepare_df(raw: pd.DataFrame) -> pd.DataFrame:
    return enrich_decision_columns(raw)


@st.cache_data(show_spinner=False)
def national_means(df: pd.DataFrame) -> dict:
    return {
        "stunting_pct": float(df["stunting_pct"].mean()),
        "persen_penduduk_miskin": float(
            df["persen_penduduk_miskin"].mean()
            if "persen_penduduk_miskin" in df
            else df["kemiskinan_pct"].mean()
        ),
        "ikp": float(df["ikp"].mean()),
        "current_score_2024": float(df["current_score_2024"].mean()),
        "projected_score_2025": float(df["projected_score_2025"].mean()),
    }


def render_header() -> None:
    st.title("Prioritas MBG dan Early Warning Wilayah")
    st.markdown(
        '<p class="subhead">Penentuan prioritas relatif berdasarkan stunting, '
        "kemiskinan, ketahanan pangan, dan tren 2022–2024.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="disclaimer">Dashboard merupakan alat pendukung keputusan. '
        "Status bukan keputusan anggaran final dan perlu dikonfirmasi menggunakan "
        "data operasional serta verifikasi lapangan.</p>",
        unsafe_allow_html=True,
    )


ALL_CITIES_LABEL = "— Semua (multi-garis) —"
PENDING_REGION_KEY = "_pending_selected_region"


def apply_pending_region_selection() -> None:
    """
    Terapkan pilihan dari tabel / aksi lain SEBELUM selectbox
    key=selected_region di-render (hindari StreamlitAPIException).
    """
    pending = st.session_state.pop(PENDING_REGION_KEY, None)
    if pending is not None:
        st.session_state["selected_region"] = pending
        st.session_state["timeline_series"] = pending


def render_filters(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, str, str, pd.Series | None]:
    """
    Returns:
      filtered, prov, cakupan, selected_city_row | None
    """
    apply_pending_region_selection()

    c1, c2, c3 = st.columns([1, 1.3, 1.7])
    with c1:
        cakupan = st.selectbox("Cakupan", ["Nasional", "Provinsi"], key="flt_scope")
    provs = sorted(df["provinsi_normalized"].dropna().unique().tolist())
    with c2:
        if cakupan == "Provinsi":
            prov = st.selectbox("Provinsi", provs, key="flt_prov")
        else:
            st.selectbox("Provinsi", ["—"], disabled=True, key="flt_prov_off")
            prov = "Semua Provinsi"

    # reset pilih kota saat cakupan/provinsi berubah
    scope_token = f"{cakupan}|{prov}"
    if st.session_state.get("_scope_token") != scope_token:
        st.session_state["_scope_token"] = scope_token
        st.session_state["selected_region"] = ALL_CITIES_LABEL
        st.session_state["timeline_series"] = None
        st.session_state.pop(PENDING_REGION_KEY, None)

    filtered = df if prov == "Semua Provinsi" else df[df["provinsi_normalized"] == prov]

    city_options = (
        filtered.assign(opt=filtered.apply(region_key, axis=1))
        .sort_values(["status_rank", "current_rank"])["opt"]
        .tolist()
        if not filtered.empty
        else []
    )
    options = [ALL_CITIES_LABEL] + city_options
    if st.session_state.get("selected_region") not in options:
        st.session_state["selected_region"] = ALL_CITIES_LABEL

    with c3:
        choice = st.selectbox(
            "Kabupaten/kota (opsional)",
            options,
            key="selected_region",
            help="Kosongkan (Semua) untuk melihat banyak garis. "
            "Pilih satu kabupaten/kota untuk fokus detail.",
        )

    city_row: pd.Series | None = None
    if choice and choice != ALL_CITIES_LABEL and not filtered.empty:
        match = filtered[filtered.apply(region_key, axis=1) == choice]
        if not match.empty:
            city_row = match.iloc[0]

    return filtered, prov, cakupan, city_row


def _kpi_html(label: str, value: str, sub: str, accent: str) -> str:
    return (
        f'<div class="kpi-card accent-{accent}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="sub">{sub}</div></div>'
    )


def render_kpi(filtered: pd.DataFrame, scope_label: str) -> None:
    n = len(filtered)
    counts = decision_counts(filtered)
    n_prior = counts[STATUS_PRIORITAS_UTAMA]
    n_ew = counts[STATUS_EARLY_WARNING]
    n_up = counts["risiko_meningkat"]

    # Prioritas utama
    top_p = top_region_for_status(filtered, STATUS_PRIORITAS_UTAMA)
    if n_prior == 0:
        sub_p = "Tidak ada wilayah Q4 yang diproyeksikan tetap Q4"
        val_p = "0 wilayah"
    elif n_prior == 1 and top_p is not None:
        val_p = "1 wilayah"
        sub_p = f"{top_p['kabupaten_kota_normalized']} — peringkat #{int(top_p['current_rank'])}"
    else:
        val_p = f"{n_prior} wilayah"
        if top_p is not None:
            sub_p = f"Contoh: {top_p['kabupaten_kota_normalized']} (peringkat #{int(top_p['current_rank'])})"
        else:
            sub_p = f"Cakupan {scope_label}"

    # Early warning
    top_e = top_region_for_status(filtered, STATUS_EARLY_WARNING)
    if n_ew == 0:
        val_e = "0 wilayah"
        sub_e = "Tidak ada wilayah early warning pada filter ini"
    elif n_ew == 1 and top_e is not None:
        val_e = "1 wilayah"
        sub_e = f"{top_e['kabupaten_kota_normalized']} diproyeksikan mengalami kenaikan risiko"
    else:
        val_e = f"{n_ew} wilayah"
        if top_e is not None:
            sub_e = f"Contoh: {top_e['kabupaten_kota_normalized']} (+{float(top_e['score_change']):.1f})"
        else:
            sub_e = "Perlu diantisipasi sebelum masuk Q4"

    # Risiko meningkat
    val_r = f"{n_up} dari {n} wilayah"
    sub_r = "Berdasarkan perubahan skor proyeksi indikatif"

    # Coverage — filtered view is balanced by construction
    val_c = f"{n} wilayah"
    if scope_label == "Nasional":
        sub_c = f"Balanced panel data lengkap 2022–{ACTUAL_END_YEAR}"
    else:
        sub_c = f"Data lengkap 2022–{ACTUAL_END_YEAR} di {scope_label}"

    html = (
        '<div class="kpi-grid">'
        + _kpi_html("Prioritas utama", val_p, sub_p, "red")
        + _kpi_html("Early warning", val_e, sub_e, "orange")
        + _kpi_html("Risiko meningkat", val_r, sub_r, "slate")
        + _kpi_html("Coverage data", val_c, sub_c, "green")
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _ensure_kode4(geo_kab: dict, id_field: str | None) -> None:
    for feat in geo_kab.get("features", []):
        props = feat.get("properties") or {}
        raw = props.get("_kode4")
        if raw is None and id_field:
            raw = props.get(id_field)
        if raw is None:
            raw = props.get("CC_2")
        if raw is not None:
            # simpan kode geo apa adanya (biasanya 4 digit BPS GADM)
            props["_kode4"] = str(raw).split(".")[0].strip()
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


def _map_token(text: str) -> str:
    """Normalisasi nama untuk fallback join peta (hapus spasi/tanda)."""
    s = str(text or "").lower().strip()
    s = re.sub(r"[^a-z0-9]", "", s)
    # buang prefix administratif
    for pref in ("kabupaten", "kabkota", "kota", "kab"):
        if s.startswith(pref) and len(s) > len(pref) + 2:
            s = s[len(pref) :]
            break
    # alias nama umum IKP ↔ GADM
    aliases = {
        "biaknamfor": "biaknumfor",
        "kutaikertanegara": "kutaikartanegara",
        "makasar": "makassar",
        "kotamobago": "kotamobagu",
        "kuantansengingi": "kuantansingingi",
        "limapuluhkoto": "limapuluhkota",
        "selayar": "kepulauanselayar",
        "waringinbarat": "kotawaringinbarat",
        "waringintimur": "kotawaringintimur",
        "penukalabablematangilir": "penukalabablematangilir",
        "kepulauansiautagulandangbiaro": "siatagulandangbiaro",
        "siatagulandangbiaro": "siatagulandangbiaro",
        "kepulauantanimbar": "malukutenggarabarat",
        "malukutenggarabarat": "malukutenggarabarat",
        "baru": "tanahbumbu",  # kadang salah; skip if risky
        "mempawah": "pontianak",  # pemekaran: hatihati
        "pakpakbharat": "pakpakbharat",
        "pegununganarfak": "pegununganarfak",
    }
    # jangan map "baru" too aggressive — remove risky aliases
    aliases.pop("baru", None)
    aliases.pop("mempawah", None)
    return aliases.get(s, s)


def _map_join_key(prov: str, kab: str) -> str:
    p = _map_token(prov)
    # samakan label provinsi
    prov_alias = {
        "diy": "diyogyakarta",
        "d.i.yogyakarta": "diyogyakarta",
        "kepriau": "kepulauanriau",
        "kepbangkabelitung": "kepulauanbangkabelitung",
        "bangkabelitung": "kepulauanbangkabelitung",
        "jakartaraya": "dkijakarta",
        "nanggroeacehdarussalam": "aceh",
    }
    p = prov_alias.get(p, p)
    return f"{p}|{_map_token(kab)}"


def build_map_frame(
    geo_kab: dict,
    analysis_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Gabungkan geometri peta dengan data analisis.

    Catatan: kode BPS IKP (mis. Supiori 9119) sering beda dari kode GADM
    (Supiori 9427). Join utama by kode, fallback by provinsi+nama kab/kota.
    """
    rows = []
    for feat in geo_kab.get("features", []):
        props = feat.get("properties") or {}
        kode = props.get("_kode4")
        if not kode or kode in {"00NA", "None", "nan"}:
            continue
        kode_s = str(kode).split(".")[0].strip()
        prov_geo = props.get("_prov_canon") or props.get("NAME_1") or ""
        geo_name = props.get("NAME_2") or str(kode_s)
        rows.append(
            {
                # lokasi choropleth = kode di geojson
                "kode_kab_kota_str": kode_s,
                "geo_name": geo_name,
                "provinsi_geo": prov_geo,
                "join_name_key": _map_join_key(prov_geo, geo_name),
            }
        )
    base = pd.DataFrame(rows).drop_duplicates(subset=["kode_kab_kota_str"], keep="first")

    full = analysis_df.copy()
    full = full.assign(
        kode_an=full["kode_kab_kota"].astype(int).astype(str),
        join_name_key=[
            _map_join_key(p, k)
            for p, k in zip(
                full["provinsi_normalized"], full["kabupaten_kota_normalized"]
            )
        ],
    )

    value_cols = [
        "kabupaten_kota_normalized",
        "provinsi_normalized",
        "status_keputusan",
        "current_score_2024",
        "projected_score_2025",
        "score_change",
        "current_rank",
        "dominant_factor",
        "stunting_pct",
        "persen_penduduk_miskin",
        "ikp",
        "trend_status",
        "kode_an",
    ]
    value_cols = [c for c in value_cols if c in full.columns or c == "kode_an"]

    by_code = full[["kode_an"] + [c for c in value_cols if c != "kode_an"]].drop_duplicates(
        "kode_an", keep="first"
    )
    by_name = full[
        ["join_name_key"] + [c for c in value_cols if c != "kode_an"]
    ].drop_duplicates("join_name_key", keep="first")

    # join kode dulu, lalu isi sisa dengan nama
    m_code = base.merge(
        by_code,
        left_on="kode_kab_kota_str",
        right_on="kode_an",
        how="left",
    )
    m_name = base.merge(by_name, on="join_name_key", how="left", suffixes=("", "_nm"))

    merged = base.copy()
    for c in value_cols:
        left = m_code[c] if c in m_code.columns else pd.Series(pd.NA, index=base.index)
        right = m_name[c] if c in m_name.columns else pd.Series(pd.NA, index=base.index)
        # align index setelah merge (baris base berurutan sama)
        left = left.reset_index(drop=True)
        right = right.reset_index(drop=True)
        merged[c] = left.combine_first(right)

    merged = merged.assign(
        provinsi_normalized=merged["provinsi_normalized"].fillna(merged["provinsi_geo"])
    ) if "provinsi_normalized" in merged.columns else merged.assign(
        provinsi_normalized=merged["provinsi_geo"]
    )

    # anggota filter aktif: by kode analisis ATAU name-key
    filt = filtered_df.copy()
    filt_codes = set(filt["kode_kab_kota"].astype(int).astype(str))
    filt_names = {
        _map_join_key(p, k)
        for p, k in zip(filt["provinsi_normalized"], filt["kabupaten_kota_normalized"])
    }

    def color_row(r):
        if pd.isna(r.get("status_keputusan")):
            return "Data tidak lengkap"
        kode_an = r.get("kode_an")
        kode_an_s = "" if pd.isna(kode_an) else str(kode_an)
        join_k = r.get("join_name_key")
        join_k_s = "" if pd.isna(join_k) else str(join_k)
        geo_k = r.get("kode_kab_kota_str")
        geo_k_s = "" if pd.isna(geo_k) else str(geo_k)
        in_filter = (
            (bool(kode_an_s) and kode_an_s in filt_codes)
            or (bool(join_k_s) and join_k_s in filt_names)
            or (bool(geo_k_s) and geo_k_s in filt_codes)
        )
        if not in_filter:
            return "Di luar filter"
        return r["status_keputusan"]

    merged = merged.assign(
        warna_peta=merged.apply(color_row, axis=1),
        tooltip_skor_aktual=merged["current_score_2024"].map(
            lambda v: f"{v:.1f}" if pd.notna(v) else "—"
        ),
        tooltip_proyeksi=merged["projected_score_2025"].map(
            lambda v: f"{v:.1f}" if pd.notna(v) else "—"
        ),
        tooltip_perubahan=merged["score_change"].map(
            lambda v: f"{v:+.1f}" if pd.notna(v) else "—"
        ),
        tooltip_peringkat=merged["current_rank"].map(
            lambda v: f"#{int(v)}" if pd.notna(v) else "—"
        ),
        tooltip_faktor=merged["dominant_factor"].fillna("—"),
    )
    merged = merged.assign(
        label=merged.apply(
            lambda r: (
                f"{r['kabupaten_kota_normalized']}, {r['provinsi_normalized']}"
                if pd.notna(r.get("kabupaten_kota_normalized"))
                else f"{r['geo_name']} (data tidak lengkap)"
            ),
            axis=1,
        )
    )
    return merged


def render_map(
    df_all: pd.DataFrame,
    filtered: pd.DataFrame,
    prov: str,
) -> None:
    """Peta full-width: selalu menampilkan status keputusan (bukan skor)."""
    scope = "Nasional" if prov == "Semua Provinsi" else prov
    title = f"Status Keputusan MBG — {scope}"

    codes = tuple(
        sorted(
            df_all["kode_kab_kota"].astype(int).astype(str).str.zfill(4).unique().tolist()
        )
    )
    geo_kab, id_field = load_geojson_kab(codes)
    if not geo_kab:
        st.warning("Geometri kabupaten tidak tersedia.")
        return

    _ensure_kode4(geo_kab, id_field)
    if prov != "Semua Provinsi":
        geo_use = filter_geojson_by_province(geo_kab, prov)
        if not geo_use["features"]:
            geo_use = geo_kab
    else:
        geo_use = geo_kab

    plot_df = build_map_frame(geo_use, df_all, filtered)

    fig = px.choropleth(
        plot_df,
        geojson=geo_use,
        locations="kode_kab_kota_str",
        featureidkey="properties._kode4",
        color="warna_peta",
        color_discrete_map=STATUS_COLORS,
        category_orders={
            "warna_peta": DECISION_STATUS_ORDER
            + ["Data tidak lengkap", "Di luar filter"]
        },
        hover_name="label",
        hover_data={
            "warna_peta": True,
            "tooltip_skor_aktual": True,
            "tooltip_proyeksi": True,
            "tooltip_perubahan": True,
            "tooltip_peringkat": True,
            "tooltip_faktor": True,
            "kode_kab_kota_str": False,
            "provinsi_normalized": False,
            "current_rank": False,
            "current_score_2024": False,
            "projected_score_2025": False,
            "score_change": False,
            "status_keputusan": False,
            "dominant_factor": False,
            "stunting_pct": False,
            "persen_penduduk_miskin": False,
            "ikp": False,
            "trend_status": False,
            "geo_name": False,
            "provinsi_geo": False,
        },
        labels={
            "warna_peta": "Status keputusan",
            "tooltip_skor_aktual": "Skor aktual",
            "tooltip_proyeksi": "Proyeksi",
            "tooltip_perubahan": "Perubahan skor",
            "tooltip_peringkat": "Peringkat",
            "tooltip_faktor": "Faktor dominan",
        },
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        height=560 if prov == "Semua Provinsi" else 480,
        margin=dict(l=0, r=0, t=48, b=8),
        title=dict(text=title, font=dict(size=15)),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.02,
            xanchor="center",
            x=0.5,
            title_text="Status keputusan",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, key="map_main")
    st.caption(
        "Merah tua = prioritas utama · Oranye = early warning · "
        "Biru = pertahankan intervensi · Hijau = pemantauan rutin · "
        "Abu-abu = data tidak lengkap. "
        "Arahkan kursor untuk skor aktual, proyeksi, perubahan, peringkat, dan faktor dominan."
    )


def render_decision_table(
    filtered: pd.DataFrame,
    prov: str,
) -> pd.Series | None:
    if filtered.empty:
        return None

    # Urut default: peringkat 1 → N (prioritas tertinggi dulu)
    ordered = filtered.sort_values(
        ["current_rank", "current_score_2024"],
        ascending=[True, False],
    ).reset_index(drop=True)

    # Tampilkan SEMUA wilayah di filter agar sort header ke bawah
    # menampilkan wilayah relatif paling "aman" (#N), bukan potongan top-30
    top = ordered.copy()
    n_show = len(top)

    if prov == "Semua Provinsi":
        scope_note = (
            f"Nasional — urut peringkat skor prioritas "
            f"(#1 = prioritas/risiko tertinggi · #{n_show} = relatif paling aman di panel). "
            f"Menampilkan seluruh {n_show} wilayah balanced panel. "
            "Gunakan sort header kolom untuk urut terbalik."
        )
        cols = [
            "current_rank",
            "kabupaten_kota_normalized",
            "provinsi_normalized",
            "current_score_2024",
            "projected_score_2025",
            "score_change",
            "status_keputusan",
            "tindakan",
        ]
        rename = {
            "current_rank": "Peringkat",
            "kabupaten_kota_normalized": "Kabupaten/kota",
            "provinsi_normalized": "Provinsi",
            "current_score_2024": "Skor aktual",
            "projected_score_2025": "Proyeksi",
            "score_change": "Perubahan",
            "status_keputusan": "Status keputusan",
            "tindakan": "Tindakan",
        }
    else:
        top = top.assign(no_daftar=range(1, len(top) + 1))
        scope_note = (
            f"{prov} — seluruh {n_show} kab/kota di panel (urut skor tertinggi dulu). "
            "Kolom Peringkat nasional = posisi di panel nasional. "
            "Sort header untuk melihat wilayah relatif lebih aman di bawah."
        )
        cols = [
            "no_daftar",
            "current_rank",
            "kabupaten_kota_normalized",
            "current_score_2024",
            "projected_score_2025",
            "score_change",
            "status_keputusan",
            "tindakan",
        ]
        rename = {
            "no_daftar": "No.",
            "current_rank": "Peringkat nasional",
            "kabupaten_kota_normalized": "Kabupaten/kota",
            "current_score_2024": "Skor aktual",
            "projected_score_2025": "Proyeksi",
            "score_change": "Perubahan",
            "status_keputusan": "Status keputusan",
            "tindakan": "Tindakan",
        }

    st.markdown(f"**Daftar Prioritas Kabupaten/Kota**  \n_{scope_note}_")

    display = top[cols].rename(columns=rename)

    col_config = {
        "No.": st.column_config.NumberColumn(format="%d", width="small"),
        "Peringkat": st.column_config.NumberColumn(format="%d", width="small"),
        "Peringkat nasional": st.column_config.NumberColumn(format="%d", width="small"),
        "Skor aktual": st.column_config.NumberColumn(format="%.1f", width="small"),
        "Proyeksi": st.column_config.NumberColumn(format="%.1f", width="small"),
        "Perubahan": st.column_config.NumberColumn(format="%+.1f", width="small"),
        "Status keputusan": st.column_config.TextColumn(width="medium"),
        "Tindakan": st.column_config.TextColumn(width="medium"),
        "Kabupaten/kota": st.column_config.TextColumn(width="medium"),
        "Provinsi": st.column_config.TextColumn(width="medium"),
    }

    # tinggi tetap dengan scroll internal agar 300+ baris tetap nyaman
    table_height = min(520, 56 + 28 * min(n_show, 16))

    event = st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=table_height,
        column_config=col_config,
        on_select="rerun",
        selection_mode="single-row",
        key="decision_table",
    )

    selected_rows = []
    if event and hasattr(event, "selection"):
        selected_rows = event.selection.rows if event.selection else []
    if selected_rows:
        idx = selected_rows[0]
        if 0 <= idx < len(top):
            sel = top.iloc[idx]
            key = region_key(sel)
            # hindari loop re-render jika pilihan sama
            if st.session_state.get("selected_region") != key:
                st.session_state[PENDING_REGION_KEY] = key
                st.session_state["timeline_series"] = key
                st.rerun()
            return sel
    return None


def _score_path(row_like: pd.Series | dict) -> tuple[list[int], list[float]]:
    years = [2022, 2023, ACTUAL_END_YEAR, PROJECTION_YEAR]
    scores = [
        float(row_like.get("score_2022", float("nan"))),
        float(row_like.get("score_2023", float("nan"))),
        float(row_like.get("score_2024", float("nan"))),
        float(row_like.get("projected_score_2025", float("nan"))),
    ]
    return years, scores


def aggregate_provinces(df: pd.DataFrame) -> pd.DataFrame:
    """Rata-rata skor per provinsi untuk mode timeline nasional."""
    g = (
        df.groupby("provinsi_normalized", as_index=False)
        .agg(
            score_2022=("score_2022", "mean"),
            score_2023=("score_2023", "mean"),
            score_2024=("score_2024", "mean"),
            projected_score_2025=("projected_score_2025", "mean"),
            current_score_2024=("current_score_2024", "mean"),
            score_change=("score_change", "mean"),
            n_wilayah=("kode_wilayah", "count"),
            n_prioritas=(
                "status_keputusan",
                lambda s: int((s == STATUS_PRIORITAS_UTAMA).sum()),
            ),
            n_early=(
                "status_keputusan",
                lambda s: int((s == STATUS_EARLY_WARNING).sum()),
            ),
            best_rank=("current_rank", "min"),
        )
        .sort_values("current_score_2024", ascending=False)
    )
    g["series_id"] = g["provinsi_normalized"]
    g["series_label"] = g["provinsi_normalized"]
    g["level"] = "provinsi"
    return g


def kab_series_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["series_id"] = out.apply(region_key, axis=1)
    out["series_label"] = out["kabupaten_kota_normalized"]
    out["level"] = "kabkota"
    return out.sort_values(
        ["status_rank", "current_rank"], ascending=[True, True]
    )


def _province_trend_label(score_change: float) -> str:
    """
    label tren keputusan: arah angka skor + arti bagi pejabat.

    Skor prioritas ↑ = risiko relatif naik (buruk).
    Skor prioritas ↓ = risiko relatif turun = kondisi membaik.
    """
    d = float(score_change) if pd.notna(score_change) else 0.0
    if d >= 3:
        return "Risiko naik tajam"
    if d > 0.5:
        return "Risiko naik"
    if d <= -3:
        return "Risiko turun tajam (membaik)"
    if d < -0.5:
        return "Risiko turun (membaik)"
    return "Relatif stabil"


def _province_status_label(n_prior: int, n_early: int, n_total: int) -> str:
    if n_prior >= max(1, n_total // 4):
        return "Banyak prioritas utama"
    if n_prior > 0 and n_early > 0:
        return "Campuran prioritas & early warning"
    if n_prior > 0:
        return "Ada prioritas utama"
    if n_early > 0:
        return "Ada early warning"
    return "Pemantauan rutin"


def render_year_bars(
    row_like: pd.Series | dict,
    *,
    title: str,
    chart_key: str,
) -> None:
    """Bar skor per tahun untuk satu wilayah/agregat — mudah dibaca pejabat."""
    years, scores = _score_path(row_like)
    labels = ["2022", "2023", str(ACTUAL_END_YEAR), f"{PROJECTION_YEAR}*"]
    colors = ["#64748B", "#475569", "#991B1B", "#EA580C"]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=scores,
            marker_color=colors,
            text=[f"{v:.1f}" if pd.notna(v) else "—" for v in scores],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Skor prioritas: %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Tahun",
        yaxis_title="Skor prioritas",
        yaxis=dict(rangemode="tozero"),
        height=320,
        margin=dict(l=40, r=20, t=48, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)
    st.caption(
        f"* {PROJECTION_YEAR} = proyeksi indikatif. {PROJECTION_LABEL}."
    )


def _plotly_clicked_id(event) -> tuple[str | None, str | None]:
    """
    Ambil (id/label, token) dari klik st.plotly_chart(on_select=...).
    token dipakai agar seleksi lama tidak menimpa pilihan user (mis. clear dropdown).
    """
    if event is None:
        return None, None
    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection")
    if selection is None:
        return None, None
    points = getattr(selection, "points", None)
    if points is None and isinstance(selection, dict):
        points = selection.get("points")
    if not points:
        return None, None
    p0 = points[0]
    if hasattr(p0, "to_dict"):
        p0 = p0.to_dict()
    elif not isinstance(p0, dict):
        try:
            p0 = dict(p0)
        except Exception:
            p0 = {}

    clicked: str | None = None
    cd = p0.get("customdata")
    if cd is not None:
        if isinstance(cd, (list, tuple)) and len(cd) >= 3:
            clicked = str(cd[2])
        elif isinstance(cd, (list, tuple)) and len(cd) >= 1:
            clicked = str(cd[-1])
        else:
            clicked = str(cd)
    elif p0.get("y") is not None:
        clicked = str(p0["y"])
    elif p0.get("label") is not None:
        clicked = str(p0["label"])

    if not clicked:
        return None, None

    curve = p0.get("curve_number", p0.get("curveNumber", 0))
    pidx = p0.get("point_index", p0.get("pointNumber", p0.get("point_number", 0)))
    token = f"{curve}:{pidx}:{clicked}"
    return clicked, token


def render_change_side_by_side(
    series_df: pd.DataFrame,
    *,
    n: int = 10,
    label_col: str = "series_label",
    id_col: str = "series_id",
    unit_label: str = "Provinsi",
    key_prefix: str = "ew_nas",
) -> str | None:
    """
    Dua panel: risiko meningkat vs membaik.
    Return series_id hanya saat klik *baru* (bukan seleksi yang menempel).
    """
    work = series_df.copy()
    if id_col not in work.columns:
        work[id_col] = work[label_col]
    up = work[work["score_change"] > 0].nlargest(n, "score_change")
    down = work[work["score_change"] < 0].nsmallest(n, "score_change")
    height = max(360, 36 * max(len(up), len(down), 1) + 80)
    clicked: str | None = None
    tok_key = f"_ew_click_token_{key_prefix}"

    def _bar_fig(frame: pd.DataFrame, color: str) -> go.Figure:
        ids = frame[id_col].astype(str)
        custom = list(
            zip(
                frame["current_score_2024"].astype(float),
                frame["projected_score_2025"].astype(float),
                ids,
            )
        )
        fig = go.Figure(
            go.Bar(
                x=frame["score_change"],
                y=frame[label_col].astype(str),
                orientation="h",
                marker_color=color,
                text=frame["score_change"].map(lambda v: f"{v:+.1f}"),
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{y}</b><br>Perubahan: %{x:+.1f}"
                    "<br>Skor aktual: %{customdata[0]:.1f}"
                    "<br>Proyeksi: %{customdata[1]:.1f}"
                    "<br><i>Klik untuk buka detail</i><extra></extra>"
                ),
                customdata=custom,
            )
        )
        fig.update_layout(
            height=height,
            margin=dict(l=8, r=56, t=8, b=24),
            xaxis_title="Δ skor (proyeksi − aktual)",
            yaxis_title="",
            xaxis=dict(zeroline=True, zerolinecolor="#94A3B8"),
            clickmode="event+select",
        )
        return fig

    def _consume(event, side: str) -> None:
        nonlocal clicked
        hit, token = _plotly_clicked_id(event)
        if not hit or not token:
            return
        full_tok = f"{side}:{token}"
        if st.session_state.get(tok_key) == full_tok:
            return  # seleksi lama, jangan paksa ulang
        st.session_state[tok_key] = full_tok
        clicked = hit

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f"#### ↑ {unit_label} paling meningkat")
        st.caption("Klik batang untuk membuka detail")
        if up.empty:
            st.info(f"Tidak ada {unit_label.lower()} dengan perubahan positif.")
        else:
            u = up.sort_values("score_change", ascending=True)
            event_up = st.plotly_chart(
                _bar_fig(u, "#991B1B"),
                use_container_width=True,
                key=f"{key_prefix}_up",
                on_select="rerun",
                selection_mode="points",
            )
            _consume(event_up, "up")

    with c2:
        st.markdown(f"#### ↓ {unit_label} paling membaik")
        st.caption("Klik batang untuk membuka detail")
        if down.empty:
            st.info(f"Tidak ada {unit_label.lower()} dengan perubahan negatif.")
        else:
            d = down.sort_values("score_change", ascending=False)
            event_down = st.plotly_chart(
                _bar_fig(d, "#15803D"),
                use_container_width=True,
                key=f"{key_prefix}_down",
                on_select="rerun",
                selection_mode="points",
            )
            _consume(event_down, "down")

    return clicked


def render_province_summary(prov_name: str, df_all: pd.DataFrame, national: dict) -> None:
    """Detail satu provinsi: bar skor per tahun + ringkasan tindakan."""
    sub = df_all[df_all["provinsi_normalized"] == prov_name]
    if sub.empty:
        st.info("Data provinsi tidak tersedia.")
        return

    series_row = aggregate_provinces(sub).iloc[0]
    counts = decision_counts(sub)
    means = {
        "score": float(sub["current_score_2024"].mean()),
        "proj": float(sub["projected_score_2025"].mean()),
        "change": float(sub["score_change"].mean()),
    }
    top = sort_decision_table(sub).head(5)

    st.markdown(f"### {prov_name}")
    st.caption(
        f"{len(sub)} kab/kota di panel · tren {_province_trend_label(means['change'])} · "
        f"rata-rata skor {means['score']:.1f} → proyeksi {means['proj']:.1f} "
        f"({means['change']:+.1f})"
    )

    c1, c2 = st.columns([1.1, 1], gap="medium")
    with c1:
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", prov_name)
        render_year_bars(
            series_row,
            title=f"Skor prioritas rata-rata — {prov_name}",
            chart_key=f"year_bars_{safe}",
        )
    with c2:
        k1, k2 = st.columns(2)
        k1.metric("Prioritas utama", counts[STATUS_PRIORITAS_UTAMA])
        k2.metric("Early warning", counts[STATUS_EARLY_WARNING])
        k3, k4 = st.columns(2)
        k3.metric("Pertahankan", counts[STATUS_PERTAHANKAN])
        k4.metric("Pemantauan rutin", counts[STATUS_PEMANTAUAN])
        st.markdown(
            f"""
            <div class="detail-box" style="margin-top:0.6rem">
              <h4>Status agregat</h4>
              <p style="margin:0;font-weight:600;color:#0f172a">
                {_province_status_label(
                    counts[STATUS_PRIORITAS_UTAMA],
                    counts[STATUS_EARLY_WARNING],
                    len(sub),
                )}
              </p>
              <p class="ctx" style="margin-top:0.5rem">
                Agregat dari rata-rata kab/kota di balanced panel — bukan skor resmi
                satuan provinsi. Drill ke <strong>Cakupan → Provinsi</strong>
                untuk daftar kab/kota.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Detail kab/kota prioritas di provinsi ini"):
        st.dataframe(
            top[
                [
                    "current_rank",
                    "kabupaten_kota_normalized",
                    "current_score_2024",
                    "projected_score_2025",
                    "score_change",
                    "status_keputusan",
                    "tindakan",
                ]
            ].rename(
                columns={
                    "current_rank": "Peringkat",
                    "kabupaten_kota_normalized": "Kabupaten/kota",
                    "current_score_2024": "Skor aktual",
                    "projected_score_2025": "Proyeksi",
                    "score_change": "Perubahan",
                    "status_keputusan": "Status",
                    "tindakan": "Tindakan",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Stunting rata-rata {sub['stunting_pct'].mean():.1f}% · "
            f"kemiskinan {sub['persen_penduduk_miskin'].mean():.1f}% · "
            f"IKP {sub['ikp'].mean():.1f} "
            f"(nasional stunting {national['stunting_pct']:.1f}%, "
            f"kemiskinan {national['persen_penduduk_miskin']:.1f}%, "
            f"IKP {national['ikp']:.1f})."
        )


def render_national_province_overview(
    df_all: pd.DataFrame,
    national: dict,
) -> None:
    """Overview nasional: who up / who down + tabel ringkas + detail bar saat dipilih."""
    series_df = aggregate_provinces(df_all)
    series_df = series_df.assign(
        tren=series_df["score_change"].map(_province_trend_label),
        status_ringkas=[
            _province_status_label(int(p), int(e), int(n))
            for p, e, n in zip(
                series_df["n_prioritas"],
                series_df["n_early"],
                series_df["n_wilayah"],
            )
        ],
    )

    st.markdown("### Early warning antarprovinsi")
    st.caption(
        "Klik batang untuk membuka detail provinsi. "
        f"Perubahan = skor proyeksi indikatif {PROJECTION_YEAR} − skor aktual {ACTUAL_END_YEAR}."
    )

    clicked = render_change_side_by_side(
        series_df, n=10, unit_label="Provinsi", key_prefix="ew_nas"
    )
    labels_set = set(series_df["series_label"].astype(str))
    # Apply chart click before selectbox (hindari StreamlitAPIException)
    if clicked and str(clicked) in labels_set:
        st.session_state["timeline_series"] = str(clicked)
        st.session_state["timeline_pick_prov"] = str(clicked)

    st.markdown("#### Ringkasan provinsi")
    st.caption(
        "Kolom tren mengacu pada skor prioritas (risiko relatif): "
        "**Risiko naik** = skor proyeksi lebih tinggi; "
        "**Risiko turun (membaik)** = skor proyeksi lebih rendah. "
        "Angka skor & detail di expander / pilih provinsi."
    )

    simple = series_df[
        [
            "series_label",
            "n_prioritas",
            "n_early",
            "tren",
            "status_ringkas",
            "score_change",
            "current_score_2024",
        ]
    ].sort_values(
        ["n_prioritas", "n_early", "score_change"],
        ascending=[False, False, False],
    )

    st.dataframe(
        simple[
            ["series_label", "n_prioritas", "n_early", "tren", "status_ringkas"]
        ].rename(
            columns={
                "series_label": "Provinsi",
                "n_prioritas": "Prioritas utama",
                "n_early": "Early warning",
                "tren": "Trend",
                "status_ringkas": "Status",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "Prioritas utama": st.column_config.NumberColumn(format="%d", width="small"),
            "Early warning": st.column_config.NumberColumn(format="%d", width="small"),
            "Trend": st.column_config.TextColumn(width="medium"),
            "Status": st.column_config.TextColumn(width="large"),
        },
    )

    with st.expander("Lihat skor, proyeksi, dan N kab/kota (detail angka)"):
        detail = series_df[
            [
                "series_label",
                "n_wilayah",
                "current_score_2024",
                "projected_score_2025",
                "score_change",
                "n_prioritas",
                "n_early",
                "best_rank",
                "tren",
            ]
        ].sort_values("current_score_2024", ascending=False)
        st.dataframe(
            detail.rename(
                columns={
                    "series_label": "Provinsi",
                    "n_wilayah": "N kab/kota",
                    "current_score_2024": "Skor aktual",
                    "projected_score_2025": "Proyeksi",
                    "score_change": "Perubahan",
                    "n_prioritas": "Prioritas utama",
                    "n_early": "Early warning",
                    "best_rank": "Peringkat kab #1",
                    "tren": "Trend",
                }
            ),
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={
                "Skor aktual": st.column_config.NumberColumn(format="%.1f"),
                "Proyeksi": st.column_config.NumberColumn(format="%.1f"),
                "Perubahan": st.column_config.NumberColumn(format="%+.1f"),
            },
        )

    labels = series_df.sort_values(
        ["n_prioritas", "score_change"], ascending=[False, False]
    )["series_label"].tolist()
    none_opt = "— Pilih provinsi (atau klik batang di atas) —"
    pick_opts = [none_opt] + labels
    current = st.session_state.get("timeline_series")
    # Jika klik chart set id, pastikan match label
    if current not in labels and current is not None:
        # series_id == label for province
        current = current if current in labels else none_opt
    default = current if current in labels else none_opt
    if default not in pick_opts:
        default = none_opt
    chosen = st.selectbox(
        "Detail provinsi",
        pick_opts,
        index=pick_opts.index(default),
        key="timeline_pick_prov",
    )
    highlight = None if chosen == none_opt else chosen
    st.session_state["timeline_series"] = highlight

    if highlight:
        st.markdown("---")
        render_province_summary(highlight, df_all, national)
    else:
        st.info(
            "Klik batang di grafik atas, atau pilih provinsi di sini "
            "untuk melihat skor per tahun."
        )


def render_single_timeline(row: pd.Series) -> None:
    """Line chart skor: solid aktual, putus proyeksi, zona risiko background."""
    years, scores = _score_path(row)
    # Zona score-kuartil sederhana (0–100)
    zones = [
        (0, 25, "rgba(21, 128, 61, 0.10)", "Rendah"),
        (25, 50, "rgba(202, 138, 4, 0.12)", "Sedang"),
        (50, 75, "rgba(234, 88, 12, 0.12)", "Tinggi"),
        (75, 105, "rgba(153, 27, 27, 0.12)", "Kritis"),
    ]
    fig = go.Figure()
    for y0, y1, fill, _ in zones:
        fig.add_hrect(
            y0=y0,
            y1=y1,
            fillcolor=fill,
            line_width=0,
            layer="below",
        )

    # Aktual solid
    fig.add_trace(
        go.Scatter(
            x=years[:3],
            y=scores[:3],
            mode="lines+markers",
            name="Aktual",
            line=dict(color="#0f172a", width=3),
            marker=dict(size=9, color="#0f172a"),
            hovertemplate="Tahun %{x}<br>Skor: %{y:.1f}<extra></extra>",
        )
    )
    # Highlight titik tahun terakhir aktual
    fig.add_trace(
        go.Scatter(
            x=[years[2]],
            y=[scores[2]],
            mode="markers",
            name=str(ACTUAL_END_YEAR),
            showlegend=False,
            marker=dict(
                size=16,
                color="#991B1B",
                line=dict(width=2, color="#fff"),
            ),
            hovertemplate=f"<b>{ACTUAL_END_YEAR}</b><br>Skor aktual: %{{y:.1f}}<extra></extra>",
        )
    )
    # Proyeksi putus
    fig.add_trace(
        go.Scatter(
            x=[years[2], years[3]],
            y=[scores[2], scores[3]],
            mode="lines+markers",
            name="Proyeksi",
            line=dict(color="#EA580C", width=2.5, dash="dash"),
            marker=dict(size=10, symbol="diamond", color="#EA580C"),
            hovertemplate="Tahun %{x}<br>Skor: %{y:.1f}<extra></extra>",
        )
    )

    y_vals = [v for v in scores if pd.notna(v)]
    y_max = max(y_vals + [80]) * 1.08 if y_vals else 100
    y_min = max(0, min(y_vals + [0]) - 5) if y_vals else 0

    fig.update_layout(
        xaxis=dict(
            title="",
            tickmode="array",
            tickvals=years,
            ticktext=["2022", "2023", str(ACTUAL_END_YEAR), f"{PROJECTION_YEAR}*"],
            range=[2021.7, PROJECTION_YEAR + 0.3],
        ),
        yaxis=dict(
            title="Skor Prioritas",
            range=[y_min, min(105, y_max)],
            zeroline=False,
        ),
        height=360,
        margin=dict(l=48, r=20, t=16, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        plot_bgcolor="rgba(255,255,255,0)",
        paper_bgcolor="rgba(255,255,255,0)",
    )
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", str(row.get("kabupaten_kota_normalized", "x")))
    st.plotly_chart(fig, use_container_width=True, key=f"timeline_line_{safe}")
    st.caption(
        f"Zona: hijau rendah · kuning sedang · oranye tinggi · merah kritis. "
        f"* {PROJECTION_LABEL}."
    )


def render_contribution_hbar(row: pd.Series, chart_key: str) -> None:
    shares = sorted_contribution_shares(row)
    labels = [s["factor"] for s in shares]
    # display Kerawanan pangan as IKP for brevity
    labels = ["IKP" if x == "Kerawanan pangan" else x for x in labels]
    shares_pct = [s["share"] for s in shares]
    colors = []
    for lab in labels:
        if lab == "Stunting":
            colors.append("#991B1B")
        elif lab == "Kemiskinan":
            colors.append("#EA580C")
        else:
            colors.append("#0F766E")

    fig = go.Figure(
        go.Bar(
            x=shares_pct,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{p:.0f}%" for p in shares_pct],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Kontribusi: %{x:.0f}%<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(title="Bagian skor (%)", range=[0, max(shares_pct + [10]) * 1.25]),
        yaxis=dict(title="", autorange="reversed"),
        height=260,
        margin=dict(l=10, r=48, t=8, b=32),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def render_peer_table(row: pd.Series, peers: pd.DataFrame) -> None:
    """Posisi kab terpilih di antara kab/kota se-provinsi."""
    if peers is None or peers.empty:
        return
    name = str(row["kabupaten_kota_normalized"])
    prov = str(row["provinsi_normalized"])
    work = peers.copy()
    if "status_keputusan" not in work.columns:
        work = enrich_decision_columns(work)
    work = work.sort_values("current_rank", ascending=True).reset_index(drop=True)
    work = work.assign(
        ranking_nas=work["current_rank"].map(lambda r: f"#{int(r)}"),
        perubahan=work["score_change"].map(lambda v: f"{v:+.1f}"),
        _is_sel=work["kabupaten_kota_normalized"].astype(str) == name,
    )

    st.markdown(
        f'<p class="sec-title">Posisi {name} di Provinsi {prov}</p>',
        unsafe_allow_html=True,
    )
    display = work[
        ["kabupaten_kota_normalized", "status_keputusan", "ranking_nas", "perubahan"]
    ].rename(
        columns={
            "kabupaten_kota_normalized": "Kabupaten",
            "status_keputusan": "Status",
            "ranking_nas": "Ranking",
            "perubahan": "Perubahan",
        }
    )

    # Highlight via Streamlit: put selected first? Better show all sorted by rank
    # and use pandas Styler if supported
    try:
        def _hl(r):
            if r["Kabupaten"] == name:
                return ["background-color: #ffedd5; font-weight: 600"] * len(r)
            return [""] * len(r)

        styled = display.style.apply(_hl, axis=1)
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(320, 48 + 32 * len(display)),
        )
    except Exception:
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=min(320, 48 + 32 * len(display)),
        )
    st.caption("Baris oranye = wilayah yang sedang dipilih. Ranking = peringkat nasional.")


def render_city_decision_page(
    row: pd.Series,
    df_all: pd.DataFrame,
    national: dict,
) -> None:
    """
    Halaman keputusan kab/kota — alur atas→bawah:
    ringkasan → mengapa → aksi → timeline → penyebab → peers → insight.
    """
    del national  # national means reserved for future narrative hooks
    status = get_decision_status(row)
    icon = get_status_icon(status)
    color = get_status_color(status)
    name = str(row["kabupaten_kota_normalized"])
    prov = str(row["provinsi_normalized"])
    rank = int(row.get("current_rank") or row.get("rank") or 0)
    score = float(row["current_score_2024"])
    change = float(row["score_change"])
    factor = str(row.get("dominant_factor") or "—")
    if factor == "Kerawanan pangan":
        factor_show = "IKP / kerawanan pangan"
    else:
        factor_show = factor

    peers = df_all[df_all["provinsi_normalized"] == prov].copy()
    if not peers.empty:
        peers = peers.assign(
            prov_rank=peers["current_score_2024"].rank(ascending=False, method="min")
        )
        pr_match = peers[peers["kabupaten_kota_normalized"] == name]
        prov_rank = int(pr_match["prov_rank"].iloc[0]) if not pr_match.empty else 0
        n_prov = len(peers)
    else:
        prov_rank, n_prov = 0, 0

    change_cls = "up" if change > 0.5 else ("down" if change < -0.5 else "")
    change_txt = f"{'▲' if change > 0 else ('▼' if change < 0 else '●')} {change:+.1f} poin"
    change_txt = change_txt.replace(".", ",")

    # —— SECTION 1: Executive ——
    st.markdown(
        f"""
        <div class="dec-exec">
          <div class="badge" style="background:{color}">{icon} {status.upper()}</div>
          <h2>{name}</h2>
          <div class="prov">{prov}</div>
          <div class="dec-exec-grid">
            <div class="cell">
              <div class="lbl">Ranking nasional</div>
              <div class="val">#{rank}</div>
            </div>
            <div class="cell">
              <div class="lbl">Skor prioritas</div>
              <div class="val">{score:.1f}</div>
            </div>
            <div class="cell">
              <div class="lbl">Perubahan (proyeksi)</div>
              <div class="val {change_cls}">{change_txt}</div>
            </div>
            <div class="cell">
              <div class="lbl">Status</div>
              <div class="val" style="font-size:1.05rem;color:{color}">{status}</div>
            </div>
          </div>
          <p class="dec-narrative">{build_executive_narrative(row)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # —— SECTION 2: Why cards ——
    st.markdown(
        '<p class="sec-title">Mengapa wilayah ini diprioritaskan?</p>',
        unsafe_allow_html=True,
    )
    tren_val, tren_sub = trend_card_copy(row)
    rank_sub = (
        f"#{prov_rank} di {prov}" if prov_rank else "Peringkat provinsi tidak tersedia"
    )
    if n_prov:
        rank_sub = f"#{prov_rank} dari {n_prov} di {prov}"

    st.markdown(
        f"""
        <div class="why-grid">
          <div class="why-card">
            <div class="ico">📈</div>
            <div class="lbl">Tren</div>
            <div class="val">{tren_val}</div>
            <div class="sub">{tren_sub}</div>
          </div>
          <div class="why-card">
            <div class="ico">📍</div>
            <div class="lbl">Ranking</div>
            <div class="val">#{rank} Nasional</div>
            <div class="sub">{rank_sub}</div>
          </div>
          <div class="why-card">
            <div class="ico">⚠</div>
            <div class="lbl">Faktor dominan</div>
            <div class="val" style="font-size:1.05rem">{factor_show}</div>
            <div class="sub">Memberikan kontribusi terbesar terhadap skor.</div>
          </div>
          <div class="why-card">
            <div class="ico">📊</div>
            <div class="lbl">Status</div>
            <div class="val" style="font-size:1.05rem;color:{color}">{status}</div>
            <div class="sub">{status_why_short(row)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # —— SECTION 3: Actions ——
    panel_cls = "action-panel"
    if status == STATUS_PRIORITAS_UTAMA:
        panel_cls += " prioritas"
    elif status == STATUS_PEMANTAUAN:
        panel_cls += " hijau"
    elif status == STATUS_PERTAHANKAN:
        panel_cls += " biru"

    items = "".join(f"<li>{a}</li>" for a in action_checklist(row))
    st.markdown(
        f"""
        <p class="sec-title">Rekomendasi tindakan</p>
        <div class="{panel_cls}">
          <h4>Rekomendasi</h4>
          <ul>{items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # —— SECTION 4: Timeline ——
    st.markdown(
        '<p class="sec-title">Timeline skor prioritas</p>',
        unsafe_allow_html=True,
    )
    render_single_timeline(row)

    # —— SECTION 5: Contribution ——
    st.markdown(
        '<p class="sec-title">Apa penyebab skor ini?</p>',
        unsafe_allow_html=True,
    )
    st.caption("Kontribusi faktor — diurutkan dari yang terbesar.")
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    render_contribution_hbar(row, chart_key=f"contrib_h_{safe}")
    w = DEFAULT_WEIGHTS
    st.caption(
        f"Bobot model: stunting {w['stunting']:.0%} · kemiskinan {w['kemiskinan']:.0%} · "
        f"kerawanan pangan {w['ikp']:.0%}."
    )

    # —— SECTION 6: Peers ——
    if not peers.empty:
        render_peer_table(row, peers)

    # —— SECTION 7: Insight ——
    insight = build_auto_insight(row, peers if not peers.empty else None)
    st.markdown(
        f"""
        <div class="insight-card">
          <h4>Insight</h4>
          <p>{insight}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Status dihitung relatif terhadap balanced panel kab/kota. "
        "Bukan keputusan anggaran final — perlu verifikasi lapangan."
    )


def render_timeline_section(
    df_all: pd.DataFrame,
    filtered: pd.DataFrame,
    cakupan: str,
    prov: str,
    city_row: pd.Series | None,
    national: dict,
) -> None:
    """
    Mode visual:
    - Kota dipilih: halaman keputusan (7 section)
    - Nasional: early warning ± + tabel ringkas
    - Provinsi: bar perubahan kab + pilih detail
    """
    if city_row is not None:
        render_city_decision_page(city_row, df_all, national)
        return

    if cakupan == "Nasional" or prov == "Semua Provinsi":
        render_national_province_overview(df_all, national)
        return

    st.markdown("### Early warning kab/kota di provinsi")
    st.caption(
        "Klik batang untuk membuka detail di bawah — peta & peringkat tetap terlihat. "
        "Klik batang lain untuk mengganti wilayah."
    )
    series_df = kab_series_frame(filtered)
    safe_prov = re.sub(r"[^a-zA-Z0-9]+", "_", prov)
    clicked = render_change_side_by_side(
        series_df,
        n=min(10, len(series_df)),
        unit_label="Kab/kota",
        key_prefix=f"ew_prov_{safe_prov}",
    )

    labels = series_df["series_label"].tolist()
    ids = series_df["series_id"].tolist()
    label_to_id = dict(zip(labels, ids))
    id_to_label = dict(zip(ids, labels))
    id_set = set(ids)

    # Klik bar → detail di bawah saja (jangan sentuh filter selected_region)
    if clicked:
        if clicked in id_set:
            rid = clicked
        elif clicked in label_to_id:
            rid = label_to_id[clicked]
        else:
            rid = None
        if rid:
            st.session_state["timeline_series"] = rid
            lab = id_to_label.get(rid)
            if lab is not None:
                # set sebelum selectbox di-render
                st.session_state["timeline_pick"] = lab

    none_opt = "— Pilih kab/kota (atau klik batang di atas) —"
    pick_opts = [none_opt] + labels
    current = st.session_state.get("timeline_series")
    if current in id_to_label:
        default_label = id_to_label[current]
    elif current in label_to_id:
        default_label = current
    else:
        default_label = none_opt
    if default_label not in pick_opts:
        default_label = none_opt

    chosen_label = st.selectbox(
        "Detail kab/kota",
        pick_opts,
        index=pick_opts.index(default_label),
        key="timeline_pick",
    )
    highlight_id = None if chosen_label == none_opt else label_to_id[chosen_label]
    st.session_state["timeline_series"] = highlight_id

    if highlight_id is None:
        st.info("Klik batang di grafik atas, atau pilih kab/kota di sini.")
        return

    st.markdown("---")
    match = filtered[filtered.apply(region_key, axis=1) == highlight_id]
    if match.empty:
        st.warning("Wilayah tidak ditemukan pada filter aktif.")
        return
    render_city_decision_page(match.iloc[0], df_all, national)


def render_methodology(df: pd.DataFrame, meta: dict) -> None:
    with st.expander("Metodologi dan keterbatasan"):
        st.markdown(
            f"**Periode data:** 2022–{ACTUAL_END_YEAR}  \n"
            f"**Proyeksi:** {PROJECTION_LABEL}  \n"
            f"**Wilayah balanced panel:** {meta.get('n_wilayah', len(df))} "
            f"(referensi IKP ≈ {meta.get('reference_total', REFERENCE_WILAYAH_TOTAL)})"
        )
        sources = meta.get("sources") or {
            "stunting": "SSGI / dataset stunting kab-kota",
            "kemiskinan": "BPS — Penduduk Miskin (P0)",
            "pangan": "Badan Pangan Nasional — IKP",
        }
        st.markdown("**Sumber data**")
        for k, v in sources.items():
            st.markdown(f"- {k.title()}: {v}")

        st.markdown("**Formula bobot (tidak diubah di refactor UI)**")
        w = meta.get("default_weights") or DEFAULT_WEIGHTS
        st.markdown(
            f"Skor Prioritas = {w.get('stunting', 0.47):.0%} × risiko stunting + "
            f"{w.get('kemiskinan', 0.29):.0%} × risiko kemiskinan + "
            f"{w.get('ikp', 0.24):.0%} × risiko kerawanan pangan  \n"
            "Risiko = percentile rank per tahun. IKP dibalik (high IKP = low risk)."
        )

        st.markdown("**Status keputusan (prioritas relatif)**")
        st.markdown(
            f"""
| Status | Kriteria ringkas | Tindakan |
| --- | --- | --- |
| Prioritas utama | Q4 aktual ∩ Q4 proyeksi | Verifikasi & tingkatkan |
| Early warning | Proyeksi Q4 atau lonjakan ≥ {EARLY_WARNING_DELTA:.0f} | Siapkan ekspansi |
| Pertahankan intervensi | Q4 aktual, proyeksi turun | Pertahankan program |
| Pemantauan rutin | Selain itu | Monitor rutin |
"""
        )

        val = meta.get("projection_validation") or {}
        if val.get("mae") is not None:
            st.markdown(
                f"**Validasi proyeksi indikatif:** MAE {val['mae']:.2f} · "
                f"RMSE {val['rmse']:.2f} (n={val.get('n', '—')})"
            )

        notes = meta.get("methodology_notes") or METHODOLOGY_NOTES
        for key, text in notes.items():
            st.markdown(f"**{key.replace('_', ' ').title()}.** {text}")

        st.markdown("**Keterbatasan**")
        st.markdown(
            f"""
- Hanya balanced panel (sembilan nilai lengkap) yang dianalisis.
- Proyeksi {PROJECTION_YEAR} adalah early warning, bukan prediksi pasti.
- Skor relatif tidak menggantikan data cakupan layanan atau verifikasi lapangan.
- Status bukan keputusan anggaran resmi.
"""
        )

        excl = load_excluded()
        if not excl.empty:
            st.markdown("**Wilayah tidak masuk / partial**")
            st.dataframe(excl.head(80), use_container_width=True, hide_index=True)


def main() -> None:
    inject_css()
    try:
        raw = load_analysis()
        meta = load_meta()
        df = prepare_df(raw)
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    render_header()
    filtered, prov, cakupan, city_row = render_filters(df)
    scope_label = "Nasional" if prov == "Semua Provinsi" else prov

    if filtered.empty:
        st.info("Tidak ada wilayah pada filter ini.")
        render_methodology(df, meta)
        return

    national = national_means(df)

    # Hanya filter atas (Kabupaten/kota) yang mengunci mode "detail penuh"
    # (sembunyikan peta & peringkat). Klik bar chart TIDAK mengubah filter.
    choice = st.session_state.get("selected_region")
    if choice and choice != ALL_CITIES_LABEL:
        match = filtered[filtered.apply(region_key, axis=1) == choice]
        city_row = match.iloc[0] if not match.empty else None
    else:
        city_row = None

    if city_row is None:
        render_kpi(filtered, scope_label)
        render_map(df, filtered, prov)
        render_decision_table(filtered, prov)
        st.markdown("---")
    else:
        st.caption(
            f"Mode detail · {city_row['kabupaten_kota_normalized']}, "
            f"{city_row['provinsi_normalized']} — "
            "pilih *Semua* di filter kabupaten/kota untuk kembali ke peta & peringkat."
        )

    render_timeline_section(
        df_all=df,
        filtered=filtered,
        cakupan=cakupan,
        prov=prov,
        city_row=city_row,
        national=national,
    )

    render_methodology(df, meta)


if __name__ == "__main__":
    main()
