# modules/tymp/tuning.py
from __future__ import annotations

import os
import json
import copy
from datetime import datetime
from typing import Dict, Any

import streamlit as st


def _tuple_to_list(obj):
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, list):
        return [_tuple_to_list(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _tuple_to_list(v) for k, v in obj.items()}
    return obj


def _list_to_tuple_for_ranges(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    ranges = cfg.get("ranges", {})
    for k, v in list(ranges.items()):
        if isinstance(v, list) and len(v) == 2:
            ranges[k] = (float(v[0]), float(v[1]))
    return cfg


def _get_versioned_key(key_prefix: str, name: str) -> str:
    version = st.session_state.get(f"{key_prefix}_widget_version", 0)
    return f"{key_prefix}_{name}_v{version}"


def _reset_to_default(default_cfg: Dict[str, Any], key_prefix: str):
    st.session_state[f"{key_prefix}_cfg"] = copy.deepcopy(default_cfg)
    st.session_state[f"{key_prefix}_widget_version"] = st.session_state.get(f"{key_prefix}_widget_version", 0) + 1


def _load_cfg_to_state(loaded_cfg: Dict[str, Any], key_prefix: str):
    st.session_state[f"{key_prefix}_cfg"] = copy.deepcopy(loaded_cfg)
    st.session_state[f"{key_prefix}_widget_version"] = st.session_state.get(f"{key_prefix}_widget_version", 0) + 1


def build_tuning_sidebar(default_cfg: Dict[str, Any], out_dir: str, *, key_prefix: str = "tymp") -> Dict[str, Any]:
    state_key = f"{key_prefix}_cfg"
    version_key = f"{key_prefix}_widget_version"

    if state_key not in st.session_state:
        st.session_state[state_key] = copy.deepcopy(default_cfg)
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    cfg = copy.deepcopy(st.session_state[state_key])

    cfg.setdefault("pressure_windows", {})
    cfg.setdefault("compliance_cutoffs", {})
    cfg.setdefault("ecv_hints", {})
    cfg.setdefault("gradient_notes", {})
    cfg.setdefault("ranges", {})

    st.sidebar.header("⚙️ Tuning (Jerger rules)")
    st.sidebar.caption("Chỉnh ngưỡng realtime. Kết quả phân loại sẽ đổi ngay.")

    with st.sidebar.expander("Ngưỡng Pressure (A/C)", expanded=True):
        a_min = st.slider(
            "A_PRESS_MIN",
            min_value=-300.0,
            max_value=0.0,
            value=float(cfg["pressure_windows"].get("A_PRESS_MIN", -100.0)),
            step=5.0,
            key=_get_versioned_key(key_prefix, "A_PRESS_MIN"),
        )
        a_max = st.slider(
            "A_PRESS_MAX",
            min_value=0.0,
            max_value=200.0,
            value=float(cfg["pressure_windows"].get("A_PRESS_MAX", 50.0)),
            step=5.0,
            key=_get_versioned_key(key_prefix, "A_PRESS_MAX"),
        )
        c_cut = st.slider(
            "C_PRESS_CUTOFF (<= là C)",
            min_value=-300.0,
            max_value=0.0,
            value=float(cfg["pressure_windows"].get("C_PRESS_CUTOFF", -100.0)),
            step=5.0,
            key=_get_versioned_key(key_prefix, "C_PRESS_CUTOFF"),
        )
        c2_cut = st.slider(
            "C2_CUTOFF (<= là C2)",
            min_value=-400.0,
            max_value=-50.0,
            value=float(cfg["pressure_windows"].get("C2_CUTOFF", -200.0)),
            step=5.0,
            key=_get_versioned_key(key_prefix, "C2_CUTOFF"),
        )

        if a_min > a_max:
            st.warning("A_PRESS_MIN đang lớn hơn A_PRESS_MAX → tự đổi chỗ.")
            a_min, a_max = a_max, a_min

        cfg["pressure_windows"]["A_PRESS_MIN"] = float(a_min)
        cfg["pressure_windows"]["A_PRESS_MAX"] = float(a_max)
        cfg["pressure_windows"]["C_PRESS_CUTOFF"] = float(c_cut)
        cfg["pressure_windows"]["C2_CUTOFF"] = float(c2_cut)

    with st.sidebar.expander("Ngưỡng Compliance (A/As/Ad/B)", expanded=True):
        b_cut = st.slider(
            "B_COMP_CUTOFF (<= là B)",
            min_value=0.00,
            max_value=0.60,
            value=float(cfg["compliance_cutoffs"].get("B_COMP_CUTOFF", 0.20)),
            step=0.01,
            key=_get_versioned_key(key_prefix, "B_COMP_CUTOFF"),
        )
        as_cut = st.slider(
            "AS_CUTOFF (< là As)",
            min_value=0.05,
            max_value=1.00,
            value=float(cfg["compliance_cutoffs"].get("AS_CUTOFF", 0.30)),
            step=0.01,
            key=_get_versioned_key(key_prefix, "AS_CUTOFF"),
        )
        ad_cut = st.slider(
            "AD_CUTOFF (> là Ad)",
            min_value=0.50,
            max_value=3.50,
            value=float(cfg["compliance_cutoffs"].get("AD_CUTOFF", 1.60)),
            step=0.01,
            key=_get_versioned_key(key_prefix, "AD_CUTOFF"),
        )

        if b_cut > as_cut:
            st.warning("B_COMP_CUTOFF > AS_CUTOFF (khuyến nghị B <= As).")
        if as_cut >= ad_cut:
            st.warning("AS_CUTOFF >= AD_CUTOFF (khuyến nghị As < Ad).")

        cfg["compliance_cutoffs"]["B_COMP_CUTOFF"] = float(b_cut)
        cfg["compliance_cutoffs"]["AS_CUTOFF"] = float(as_cut)
        cfg["compliance_cutoffs"]["AD_CUTOFF"] = float(ad_cut)

    with st.sidebar.expander("Gợi ý ECV cho Type B (hint)", expanded=False):
        high_ecv = st.slider(
            "HIGH_ECV_HINT",
            min_value=0.50,
            max_value=5.00,
            value=float(cfg["ecv_hints"].get("HIGH_ECV_HINT", 2.0)),
            step=0.10,
            key=_get_versioned_key(key_prefix, "HIGH_ECV_HINT"),
        )
        cfg["ecv_hints"]["HIGH_ECV_HINT"] = float(high_ecv)

    with st.sidebar.expander("Gradient note (giảm confidence nếu bất thường)", expanded=False):
        g_low = st.slider(
            "GRAD_LOW",
            min_value=0.0,
            max_value=200.0,
            value=float(cfg["gradient_notes"].get("LOW", 30.0)),
            step=1.0,
            key=_get_versioned_key(key_prefix, "GRAD_LOW"),
        )
        g_high = st.slider(
            "GRAD_HIGH",
            min_value=50.0,
            max_value=300.0,
            value=float(cfg["gradient_notes"].get("HIGH", 200.0)),
            step=1.0,
            key=_get_versioned_key(key_prefix, "GRAD_HIGH"),
        )

        if g_low > g_high:
            st.warning("GRAD_LOW > GRAD_HIGH → tự đổi chỗ.")
            g_low, g_high = g_high, g_low

        cfg["gradient_notes"]["LOW"] = float(g_low)
        cfg["gradient_notes"]["HIGH"] = float(g_high)

    st.session_state[state_key] = copy.deepcopy(cfg)

    st.sidebar.divider()

    col_a, col_b = st.sidebar.columns(2)

    with col_a:
        if st.button("↩️ Reset", key=f"{key_prefix}_reset_btn"):
            _reset_to_default(default_cfg, key_prefix)
            st.rerun()

    with col_b:
        save_clicked = st.button("💾 Save", key=f"{key_prefix}_save_btn")

    uploaded = st.sidebar.file_uploader(
        "Load config JSON",
        type=["json"],
        key=f"{key_prefix}_uploader",
    )
    if uploaded is not None:
        try:
            loaded = json.load(uploaded)
            loaded = _list_to_tuple_for_ranges(loaded)
            _load_cfg_to_state(loaded, key_prefix)
            st.sidebar.success("Đã load config JSON.")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Load config lỗi: {e}")

    if save_clicked:
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_cfg_path = os.path.join(out_dir, f"tymp_config_saved_{ts}.json")
        with open(out_cfg_path, "w", encoding="utf-8") as f:
            json.dump(_tuple_to_list(st.session_state[state_key]), f, ensure_ascii=False, indent=2)
        st.sidebar.success(f"Đã lưu: {out_cfg_path}")

    st.sidebar.download_button(
        "⬇️ Download config",
        data=json.dumps(_tuple_to_list(st.session_state[state_key]), ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="tymp_config.json",
        mime="application/json",
        key=f"{key_prefix}_download_btn",
    )

    with st.sidebar.expander("Xem cfg hiện tại", expanded=False):
        st.json(_tuple_to_list(st.session_state[state_key]))

    return copy.deepcopy(st.session_state[state_key])