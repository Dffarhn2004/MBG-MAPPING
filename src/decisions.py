"""Fungsi status keputusan & salinan untuk dashboard decision-first.

Tidak mengubah formula skor di scoring.py — hanya interpretasi & penyajian.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import (
    DECISION_ACTIONS,
    DECISION_RECOMMENDATIONS,
    DECISION_STATUS_ORDER,
    EARLY_WARNING_DELTA,
    LEGACY_STATUS_MAP,
    STATUS_COLORS,
    STATUS_EARLY_WARNING,
    STATUS_ICONS,
    STATUS_PEMANTAUAN,
    STATUS_PERTAHANKAN,
    STATUS_PRIORITAS_UTAMA,
    STATUS_TITLE_WHY,
)


def _num(row: pd.Series | dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and pd.notna(row[k]):
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    return default


def _str(row: pd.Series | dict, *keys: str, default: str = "") -> str:
    for k in keys:
        if k in row and pd.notna(row[k]):
            return str(row[k])
    return default


def get_decision_status(row: pd.Series | dict) -> str:
    """
    Tentukan status keputusan dari kuartil + early warning.

    Logika selaras dengan scoring.assign_decision_status (tanpa ubah formula skor).
    """
    # Prefer hitung ulang dari kuartil agar konsisten dengan label baru
    cq = _str(row, "current_quartile")
    pq = _str(row, "projected_quartile")
    change = _num(row, "score_change")

    if cq and pq:
        cur_q4 = cq == "Q4"
        proj_q4 = pq == "Q4"
        if cur_q4 and proj_q4:
            return STATUS_PRIORITAS_UTAMA
        if (not cur_q4) and proj_q4:
            return STATUS_EARLY_WARNING
        if cur_q4 and (not proj_q4):
            return STATUS_PERTAHANKAN
        if change >= EARLY_WARNING_DELTA:
            return STATUS_EARLY_WARNING
        return STATUS_PEMANTAUAN

    # fallback: map label dari pipeline
    raw = _str(row, "decision_status", "prioritas_kategori")
    return LEGACY_STATUS_MAP.get(raw, STATUS_PEMANTAUAN)


def get_status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "#64748B")


def get_status_icon(status: str) -> str:
    return STATUS_ICONS.get(status, "⚪")


def get_action_label(status: str) -> str:
    return DECISION_ACTIONS.get(status, "Monitor rutin")


def get_recommendation(row: pd.Series | dict) -> str:
    status = get_decision_status(row)
    return DECISION_RECOMMENDATIONS.get(
        status,
        "Sesuaikan tindak lanjut dengan kondisi lokal dan verifikasi lapangan.",
    )


def get_decision_reason(row: pd.Series | dict) -> list[str]:
    """Poin ringkas alasan status (bullet)."""
    status = get_decision_status(row)
    cur = _num(row, "current_score_2024", "priority_score")
    proj = _num(row, "projected_score_2025", default=cur)
    change = _num(row, "score_change", default=proj - cur)
    cq = _str(row, "current_quartile", default="—")
    pq = _str(row, "projected_quartile", default="—")
    factor = _str(row, "dominant_factor", default="—")
    rank = int(_num(row, "current_rank", "rank", default=0))
    trend = _str(row, "trend_status", default="—")

    bullets = [
        f"Skor aktual: {cur:.1f} ({cq})",
        f"Proyeksi indikatif: {proj:.1f} ({pq})",
        f"Perubahan: {change:+.1f} poin",
        f"Faktor dominan: {factor}",
        f"Peringkat #{rank} nasional" if rank else "Peringkat nasional tidak tersedia",
    ]
    if trend and trend != "—":
        bullets.append(f"Tren 2022–2024: {trend}")

    if status == STATUS_PRIORITAS_UTAMA:
        bullets.insert(
            0,
            "Masuk kuartil tertinggi (Q4) pada skor aktual dan proyeksi indikatif.",
        )
    elif status == STATUS_EARLY_WARNING:
        if pq == "Q4" and cq != "Q4":
            bullets.insert(
                0,
                "Belum Q4 saat ini, tetapi proyeksi indikatif masuk Q4.",
            )
        elif change >= EARLY_WARNING_DELTA:
            bullets.insert(
                0,
                f"Lonjakan skor ≥ {EARLY_WARNING_DELTA:.0f} poin (early warning).",
            )
        else:
            bullets.insert(0, "Menunjukkan tanda kenaikan risiko yang perlu diantisipasi.")
    elif status == STATUS_PERTAHANKAN:
        bullets.insert(
            0,
            "Masih prioritas tinggi (Q4) saat ini, tetapi proyeksi indikasi membaik.",
        )
    else:
        bullets.insert(
            0,
            "Skor aktual dan proyeksi relatif di bawah wilayah berisiko nasional tertinggi.",
        )
    return bullets


def get_detail_title(status: str) -> str:
    return STATUS_TITLE_WHY.get(status, "Dasar penetapan status")


def status_sort_key(status: str) -> int:
    try:
        return DECISION_STATUS_ORDER.index(status)
    except ValueError:
        return 99


def enrich_decision_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah kolom tampilan status, tindakan, warna (tanpa ubah skor)."""
    out = df.copy()
    statuses = out.apply(get_decision_status, axis=1)
    out = out.assign(
        status_keputusan=statuses,
        tindakan=statuses.map(get_action_label),
        status_color=statuses.map(get_status_color),
        status_icon=statuses.map(get_status_icon),
        status_rank=statuses.map(status_sort_key),
    )
    return out


def decision_counts(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            STATUS_PRIORITAS_UTAMA: 0,
            STATUS_EARLY_WARNING: 0,
            STATUS_PERTAHANKAN: 0,
            STATUS_PEMANTAUAN: 0,
            "risiko_meningkat": 0,
        }
    work = df.copy()
    if "status_keputusan" not in work.columns:
        work["status_keputusan"] = work.apply(get_decision_status, axis=1)
    vc = work["status_keputusan"].value_counts()
    change_col = "score_change" if "score_change" in work.columns else None
    n_up = int(work[change_col].fillna(0).gt(0).sum()) if change_col else 0
    return {
        STATUS_PRIORITAS_UTAMA: int(vc.get(STATUS_PRIORITAS_UTAMA, 0)),
        STATUS_EARLY_WARNING: int(vc.get(STATUS_EARLY_WARNING, 0)),
        STATUS_PERTAHANKAN: int(vc.get(STATUS_PERTAHANKAN, 0)),
        STATUS_PEMANTAUAN: int(vc.get(STATUS_PEMANTAUAN, 0)),
        "risiko_meningkat": n_up,
    }


def top_region_for_status(df: pd.DataFrame, status: str) -> pd.Series | None:
    if df.empty or "status_keputusan" not in df.columns:
        return None
    sub = df[df["status_keputusan"] == status]
    if sub.empty:
        return None
    return sub.sort_values(
        ["projected_score_2025", "score_change", "current_rank"],
        ascending=[False, False, True],
    ).iloc[0]


def sort_decision_table(df: pd.DataFrame) -> pd.DataFrame:
    """Urut: tingkat status → proyeksi tertinggi → perubahan tertinggi."""
    work = df.copy()
    if "status_keputusan" not in work.columns:
        work = enrich_decision_columns(work)
    return work.sort_values(
        ["status_rank", "projected_score_2025", "score_change"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def vs_national(value: float, national: float, *, higher_is_worse: bool = True) -> str:
    if pd.isna(value) or pd.isna(national):
        return "Tidak tersedia"
    if higher_is_worse:
        if value > national * 1.05:
            return "Di atas rata-rata nasional"
        if value < national * 0.95:
            return "Di bawah rata-rata nasional"
        return "Mendekati rata-rata nasional"
    # IKP: higher is better
    if value < national * 0.95:
        return "Di bawah rata-rata nasional"
    if value > national * 1.05:
        return "Di atas rata-rata nasional"
    return "Mendekati rata-rata nasional"


def indicator_delta_label(delta: float, *, higher_is_worse: bool = True) -> str:
    if pd.isna(delta):
        return "Perubahan tidak tersedia"
    arrow = "↑" if delta > 0.05 else ("↓" if delta < -0.05 else "→")
    if abs(delta) < 0.05:
        return f"{arrow} stabil sejak 2022"
    direction_note = ""
    if higher_is_worse:
        direction_note = " (risiko naik)" if delta > 0 else " (membaik)"
    else:
        direction_note = " (membaik)" if delta > 0 else " (risiko naik)"
    return f"{arrow} {abs(delta):.1f} poin sejak 2022{direction_note}"


def contribution_breakdown(row: pd.Series | dict) -> dict[str, float]:
    return {
        "Stunting": _num(row, "contrib_stunting"),
        "Kemiskinan": _num(row, "contrib_kemiskinan"),
        "Kerawanan pangan": _num(row, "contrib_ikp"),
    }


def sorted_contribution_shares(row: pd.Series | dict) -> list[dict[str, float | str]]:
    """Kontribusi terurut: value absolut + share %."""
    bd = contribution_breakdown(row)
    total = sum(max(v, 0.0) for v in bd.values()) or 1.0
    items = sorted(bd.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {
            "factor": name,
            "value": float(val),
            "share": 100.0 * max(float(val), 0.0) / total,
        }
        for name, val in items
    ]


def _fmt_id(n: float, *, signed: bool = False, digits: int = 1) -> str:
    """Angka format Indonesia: koma desimal."""
    if pd.isna(n):
        return "—"
    s = f"{n:+.{digits}f}" if signed else f"{n:.{digits}f}"
    return s.replace(".", ",")


def _indicator_phrase(delta: float, name: str, *, higher_worse: bool = True) -> str:
    if pd.isna(delta):
        return f"{name} tidak tersedia lengkap"
    if abs(delta) < 0.3:
        return f"{name} relatif stabil"
    if higher_worse:
        if delta > 0:
            return f"{name} meningkat"
        return f"{name} membaik"
    if delta > 0:
        return f"{name} membaik"
    return f"{name} melemah"


def build_executive_narrative(row: pd.Series | dict) -> str:
    """Paragraf natural: mengapa wilayah ini menjadi perhatian."""
    name = _str(row, "kabupaten_kota_normalized", default="Wilayah ini")
    change = _num(row, "score_change")
    status = get_decision_status(row)
    factor_raw = _str(row, "dominant_factor", default="")
    if factor_raw.lower() in {"kerawanan pangan", "ikp", "pangan"}:
        factor_label = "kerawanan pangan (IKP)"
    elif factor_raw:
        factor_label = factor_raw.lower()
    else:
        factor_label = "indikator gizi dan sosial-ekonomi"

    d_st = _num(row, "delta_stunting", default=float("nan"))
    d_km = _num(row, "delta_poverty", default=float("nan"))
    d_ikp_risk = _num(row, "delta_ikp_risk", default=float("nan"))
    d_ikp_display = -d_ikp_risk if pd.notna(d_ikp_risk) else float("nan")

    phrases = {
        "Stunting": _indicator_phrase(d_st, "prevalensi stunting", higher_worse=True),
        "Kemiskinan": _indicator_phrase(d_km, "kemiskinan", higher_worse=True),
        "Kerawanan pangan": _indicator_phrase(d_ikp_display, "IKP", higher_worse=False),
    }
    others = [v for k, v in phrases.items() if k != factor_raw]

    if abs(change) < 0.5:
        head = (
            f"{name} memiliki skor prioritas yang relatif stabil "
            f"(perubahan {_fmt_id(change, signed=True)} poin terhadap skor aktual)."
        )
    elif change > 0:
        head = (
            f"{name} mengalami kenaikan skor prioritas sebesar "
            f"{_fmt_id(abs(change))} poin pada proyeksi dibanding skor aktual. "
            f"Faktor terbesar yang mendorong kenaikan adalah {factor_label}"
        )
        if others:
            head += f", sementara {others[0]}"
            if len(others) > 1:
                head += f" dan {others[1]}"
        head += "."
    else:
        head = (
            f"{name} menunjukkan penurunan skor prioritas sebesar "
            f"{_fmt_id(abs(change))} poin pada proyeksi dibanding skor aktual — "
            f"risiko relatif tampak mereda. Penekan utama skor tetap {factor_label}"
        )
        if others:
            head += f"; {others[0]}"
            if len(others) > 1:
                head += f" dan {others[1]}"
        head += "."

    if status == STATUS_PRIORITAS_UTAMA:
        tail = (
            " Berdasarkan posisi kuartil tertinggi, wilayah ini direkomendasikan "
            "sebagai Prioritas utama: verifikasi lapangan dan penguatan cakupan "
            "MBG perlu diprioritaskan."
        )
    elif status == STATUS_EARLY_WARNING:
        tail = (
            " Berdasarkan tren tiga tahun dan proyeksi, wilayah ini direkomendasikan "
            "sebagai Early warning sehingga perlu dipersiapkan intervensi apabila "
            "tren berlanjut."
        )
    elif status == STATUS_PERTAHANKAN:
        tail = (
            " Status Pertahankan intervensi: risiko masih tinggi saat ini, tetapi "
            "proyeksi membaik — jaga program yang berjalan."
        )
    else:
        tail = (
            " Status Pemantauan rutin: risiko relatif lebih rendah dibanding "
            "prioritas nasional, pantau berkala agar tidak terlewat bila tren berubah."
        )

    return (head + " " + tail).replace("  ", " ").strip()


def action_checklist(row: pd.Series | dict) -> list[str]:
    """Maksimal 4 aksi konkret untuk panel rekomendasi."""
    status = get_decision_status(row)
    factor = _str(row, "dominant_factor", default="")
    change = _num(row, "score_change")

    base: dict[str, list[str]] = {
        STATUS_PRIORITAS_UTAMA: [
            "Validasi lapangan prioritas tinggi",
            "Perkuat cakupan dan kualitas MBG",
            "Koordinasi lintas OPD terkait",
        ],
        STATUS_EARLY_WARNING: [
            "Validasi lapangan",
            "Monitoring triwulan",
            "Persiapkan kapasitas MBG",
        ],
        STATUS_PERTAHANKAN: [
            "Pertahankan program yang berjalan",
            "Monitoring berkala kualitas layanan",
            "Jaga keberlanjutan cakupan MBG",
        ],
        STATUS_PEMANTAUAN: [
            "Pemantauan berkala (periode rutin)",
            "Tinjau bila ada lonjakan indikator",
            "Bandingkan dengan kab/kota tetangga",
        ],
    }
    items = list(base.get(status, base[STATUS_PEMANTAUAN]))

    factor_action = {
        "Stunting": "Pantau indikator stunting & gizi balita",
        "Kemiskinan": "Pantau indikator kemiskinan",
        "Kerawanan pangan": "Pantau ketahanan pangan (IKP)",
    }
    fa = factor_action.get(factor)
    if fa and fa not in items:
        items.append(fa)
    elif change >= EARLY_WARNING_DELTA and "Siapkan rencana antisipasi tren" not in items:
        items.append("Siapkan rencana antisipasi tren")

    return [f"✓ {t}" for t in items[:4]]


def trend_card_copy(row: pd.Series | dict) -> tuple[str, str]:
    """(headline_value, subtitle)."""
    change = _num(row, "score_change")
    s22 = _num(row, "score_2022", default=float("nan"))
    s24 = _num(row, "current_score_2024", "score_2024", default=float("nan"))
    if pd.notna(s22) and pd.notna(s24):
        since = s24 - s22
        if abs(since) < 0.5:
            sub = "Relatif stabil sejak 2022"
        elif since > 0:
            sub = "Meningkat sejak 2022"
        else:
            sub = "Menurun sejak 2022"
    else:
        sub = _str(row, "trend_status", default="Tren 3 tahun")
    return (f"{change:+.1f} poin".replace(".", ","), sub)


def status_why_short(row: pd.Series | dict) -> str:
    status = get_decision_status(row)
    change = _num(row, "score_change")
    if status == STATUS_PRIORITAS_UTAMA:
        return "Prioritas relatif tertinggi nasional."
    if status == STATUS_EARLY_WARNING:
        if change >= EARLY_WARNING_DELTA:
            return "Belum Prioritas utama namun tren meningkat."
        return "Belum Prioritas utama, proyeksi mengarah naik."
    if status == STATUS_PERTAHANKAN:
        return "Masih berisiko tinggi, proyeksi membaik."
    return "Risiko relatif lebih rendah dibanding prioritas."


def region_key_simple(row: pd.Series | dict) -> str:
    return (
        f"{_str(row, 'kabupaten_kota_normalized')} — "
        f"{_str(row, 'provinsi_normalized')}"
    )


def build_auto_insight(
    row: pd.Series | dict,
    peers: pd.DataFrame | None = None,
) -> str:
    """Satu paragraf insight kontekstual (provinsi bila peers tersedia)."""
    name = _str(row, "kabupaten_kota_normalized", default="Wilayah ini")
    status = get_decision_status(row)
    change = _num(row, "score_change")
    rank = int(_num(row, "current_rank", "rank", default=0))
    score = _num(row, "current_score_2024")
    prov = _str(row, "provinsi_normalized", default="provinsi ini")

    if rank and score < 60:
        base = (
            f"Walaupun skor {_fmt_id(score)} menempatkan {name} di peringkat "
            f"#{rank} (belum di jajaran prioritas tertinggi nasional)"
        )
    elif rank:
        base = (
            f"Dengan skor {_fmt_id(score)}, {name} berada di peringkat "
            f"#{rank} nasional"
        )
    else:
        base = f"Skor {_fmt_id(score)} pada {name}"

    peer_bit = ""
    if peers is not None and not peers.empty and "score_change" in peers.columns:
        up = peers.nlargest(1, "score_change")
        if not up.empty:
            top_name = str(up.iloc[0]["kabupaten_kota_normalized"])
            top_ch = float(up.iloc[0]["score_change"])
            own_key = region_key_simple(row)
            top_key = region_key_simple(up.iloc[0])
            if change > 0.5 and own_key == top_key:
                peer_bit = (
                    f", peningkatan sebesar {_fmt_id(abs(change))} poin merupakan "
                    f"yang terbesar di Provinsi {prov}"
                )
            elif change > 0.5 and top_ch > change + 0.1:
                peer_bit = (
                    f". Di {prov}, kenaikan terbesar saat ini dicatat "
                    f"{top_name} ({_fmt_id(top_ch, signed=True)} poin)"
                )
            elif change > 0.5:
                peer_bit = (
                    f". Kenaikan {_fmt_id(abs(change))} poin menonjol "
                    f"dalam konteks Provinsi {prov}"
                )
            elif change < -0.5:
                peer_bit = (
                    f". Penurunan {_fmt_id(abs(change))} poin perlu dibaca "
                    f"bersama perkembangan kab/kota lain di {prov}"
                )

    if status == STATUS_EARLY_WARNING:
        tail = (
            ". Kondisi ini menunjukkan perlunya monitoring lebih intensif "
            "sebelum wilayah berpindah menjadi prioritas utama."
        )
    elif status == STATUS_PRIORITAS_UTAMA:
        tail = (
            ". Fokus segera pada verifikasi dan penguatan layanan agar risiko "
            "tinggi tidak berlarut."
        )
    elif status == STATUS_PERTAHANKAN:
        tail = (
            ". Pertahankan intervensi yang ada agar tren perbaikan tidak mundur."
        )
    else:
        tail = (
            ". Tetap pantau secara rutin agar lonjakan mendadak tidak terlewat."
        )

    return (base + peer_bit + tail).replace("  ", " ").strip()
