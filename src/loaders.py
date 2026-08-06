"""Loader data dashboard + geojson."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

GEOJSON_KAB_CANDIDATES = [
    "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IDN_2.json",
    "https://cdn.jsdelivr.net/gh/Arsylam/geojson-indonesia@main/kabupaten.geojson",
    "https://raw.githubusercontent.com/Arsylam/geojson-indonesia/main/kabupaten.geojson",
]

GEOJSON_PROV_URL = (
    "https://cdn.jsdelivr.net/gh/superpikar/indonesia-geojson@master/indonesia-province-simple.json"
)

PROV_GEO_ALIASES = {
    "nanggroe aceh darussalam": "Aceh",
    "dki jakarta": "DKI Jakarta",
    "di. aceh": "Aceh",
    "daerah istimewa yogyakarta": "DI Yogyakarta",
    "diyogyakarta": "DI Yogyakarta",
    "kepulauan bangka belitung": "Kepulauan Bangka Belitung",
    "bangka belitung": "Kepulauan Bangka Belitung",
}


@st.cache_data(show_spinner=False)
def load_analysis() -> pd.DataFrame:
    path = DATA / "analysis_ready.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Belum ada {path}. Jalankan: python data/build_analysis.py"
        )
    df = pd.read_csv(path)
    if "kode_kab_kota" not in df.columns and "kode_wilayah" in df.columns:
        df["kode_kab_kota"] = df["kode_wilayah"]
    df = df.assign(
        kode_kab_kota_str=df["kode_kab_kota"].astype(int).astype(str).str.zfill(4)
    )
    if "provinsi_normalized" not in df.columns and "provinsi" in df.columns:
        df["provinsi_normalized"] = df["provinsi"]
    if "kabupaten_kota_normalized" not in df.columns and "kabupaten_kota" in df.columns:
        df["kabupaten_kota_normalized"] = df["kabupaten_kota"]
    if "rank" not in df.columns and "current_rank" in df.columns:
        df["rank"] = df["current_rank"]
    if "priority_score" not in df.columns and "current_score_2024" in df.columns:
        df["priority_score"] = df["current_score_2024"]
    return df


@st.cache_data(show_spinner=False)
def load_meta() -> dict:
    path = DATA / "analysis_meta.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_excluded() -> pd.DataFrame:
    path = DATA / "excluded_wilayah.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _detect_geo_id_field(geojson: dict, sample_codes: set[str]) -> str | None:
    features = geojson.get("features") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    for key in props:
        hits = 0
        for f in features[:120]:
            val = f.get("properties", {}).get(key)
            if val is None:
                continue
            code = str(val).split(".")[0].zfill(4)[-4:]
            if code in sample_codes:
                hits += 1
        if hits >= 5:
            return key
    for key in ("_kode4", "CC_2", "id", "kode", "KODE_KAB", "kode_kab", "Kabupaten", "BPS"):
        if key in props:
            return key
    return None


@st.cache_data(show_spinner="Memuat peta kabupaten/kota...")
def load_geojson_kab(sample_codes: tuple[str, ...]) -> tuple[dict | None, str | None]:
    cache_path = DATA / "kabupaten.geojson"
    sample_set = set(sample_codes)

    if cache_path.exists() and cache_path.stat().st_size > 10_000:
        geo = json.loads(cache_path.read_text(encoding="utf-8"))
        props0 = (geo.get("features") or [{}])[0].get("properties") or {}
        if "_kode4" in props0:
            return geo, "_kode4"
        field = _detect_geo_id_field(geo, sample_set)
        return geo, field

    for url in GEOJSON_KAB_CANDIDATES:
        try:
            r = requests.get(url, timeout=90)
            if r.status_code != 200 or len(r.content) < 10_000:
                continue
            geo = r.json()
            for f in geo.get("features", []):
                cc = f.get("properties", {}).get("CC_2")
                if cc is not None:
                    f["properties"]["_kode4"] = str(cc).split(".")[0].zfill(4)[-4:]
            field = (
                "_kode4"
                if any(
                    "_kode4" in (f.get("properties") or {})
                    for f in geo.get("features", [])[:5]
                )
                else _detect_geo_id_field(geo, sample_set)
            )
            if field:
                cache_path.write_text(
                    json.dumps(geo, separators=(",", ":")), encoding="utf-8"
                )
                return geo, field
        except Exception:
            continue
    return None, None


@st.cache_data(show_spinner=False)
def load_geojson_provinsi() -> dict | None:
    cache_path = DATA / "provinsi.geojson"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    try:
        r = requests.get(GEOJSON_PROV_URL, timeout=45)
        if r.status_code != 200:
            return None
        geo = r.json()
        cache_path.write_text(json.dumps(geo), encoding="utf-8")
        return geo
    except Exception:
        return None


def format_number(n: float, kind: str = "int") -> str:
    if pd.isna(n):
        return "-"
    if kind == "pct":
        return f"{n:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "pct2":
        return f"{n:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "score":
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "score2":
        return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "delta":
        sign = "+" if n > 0 else ""
        return f"{sign}{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "sil":
        return f"{n:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(round(n)):,}".replace(",", ".")
