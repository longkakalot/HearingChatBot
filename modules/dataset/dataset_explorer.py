# modules/dataset/dataset_explorer.py
from __future__ import annotations

from typing import Dict, Any, List

import pandas as pd
import streamlit as st

from modules.dataset.common import (
    safe_get,
    get_side_type,
    get_side_rule_confidence,
    get_side_quality_score,
    get_side_reliability,
    get_pressure_source,
    get_interpretation,
    get_ecv,
)
from modules.dataset.repository import (
    load_tymp_case_rows,
    load_case_by_path,
)


def rows_to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "file_name",
            "created_at",
            "source_pdf",
            "right_type",
            "left_type",
            "right_quality_score",
            "left_quality_score",
            "right_reliability",
            "left_reliability",
            "right_pressure_source",
            "left_pressure_source",
            "bilateral_pattern",
            "overall_summary",
            "full_path",
        ])

    df = pd.DataFrame(rows)

    preferred_cols = [
        "file_name",
        "created_at",
        "source_pdf",
        "right_type",
        "left_type",
        "right_quality_score",
        "left_quality_score",
        "right_reliability",
        "left_reliability",
        "right_pressure_source",
        "left_pressure_source",
        "bilateral_pattern",
        "overall_summary",
        "full_path",
    ]
    cols = [c for c in preferred_cols if c in df.columns] + [c for c in df.columns if c not in preferred_cols]
    return df[cols]


def _type_options(df: pd.DataFrame, col: str) -> List[str]:
    vals = sorted([str(x) for x in df[col].dropna().unique().tolist()])
    return ["ALL"] + vals


def render_dataset_explorer(out_dir: str):
    st.subheader("Dataset Explorer")

    rows = load_tymp_case_rows(out_dir)
    df = rows_to_dataframe(rows)

    st.caption(f"Số file JSON tìm thấy: {len(df)}")

    if df.empty:
        st.info("Chưa có file JSON nào trong thư mục outputs.")
        return

    # -------------------------
    # Filters
    # -------------------------
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        right_type_filter = st.selectbox(
            "Filter Right Type",
            _type_options(df, "right_type"),
            index=0,
            key="dataset_explorer_filter_right_type",
        )

    with c2:
        left_type_filter = st.selectbox(
            "Filter Left Type",
            _type_options(df, "left_type"),
            index=0,
            key="dataset_explorer_filter_left_type",
        )

    with c3:
        reliability_filter = st.selectbox(
            "Filter Reliability",
            ["ALL", "High", "Acceptable", "Review recommended", "Low"],
            index=0,
            key="dataset_explorer_filter_reliability",
        )

    with c4:
        text_filter = st.text_input(
            "Search file / summary",
            value="",
            key="dataset_explorer_text_filter",
        ).strip().lower()

    filtered = df.copy()

    if right_type_filter != "ALL":
        filtered = filtered[filtered["right_type"].astype(str) == right_type_filter]

    if left_type_filter != "ALL":
        filtered = filtered[filtered["left_type"].astype(str) == left_type_filter]

    if reliability_filter != "ALL":
        filtered = filtered[
            (filtered["right_reliability"].astype(str) == reliability_filter) |
            (filtered["left_reliability"].astype(str) == reliability_filter)
        ]

    if text_filter:
        filtered = filtered[
            filtered["file_name"].astype(str).str.lower().str.contains(text_filter, na=False) |
            filtered["source_pdf"].astype(str).str.lower().str.contains(text_filter, na=False) |
            filtered["overall_summary"].astype(str).str.lower().str.contains(text_filter, na=False)
        ]

    st.markdown("### Danh sách ca")
    st.dataframe(
        filtered.drop(columns=["full_path"], errors="ignore"),
        use_container_width=True,
        hide_index=True
    )

    # -------------------------
    # CSV export
    # -------------------------
    csv_bytes = filtered.drop(columns=["full_path"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Export summary CSV",
        data=csv_bytes,
        file_name="tymp_dataset_summary.csv",
        mime="text/csv",
        key="dataset_explorer_export_csv",
    )

    # -------------------------
    # Case details
    # -------------------------
    st.markdown("### Xem chi tiết 1 ca")

    file_options = filtered["file_name"].tolist()
    if not file_options:
        st.warning("Không có ca nào phù hợp bộ lọc hiện tại.")
        return

    selected_file = st.selectbox(
        "Chọn file JSON",
        file_options,
        index=0,
        key="dataset_explorer_selected_file",
    )

    row = filtered[filtered["file_name"] == selected_file].iloc[0]
    full_path = row["full_path"]

    case_obj = load_case_by_path(full_path)
    if case_obj is None:
        st.error("Không đọc được file JSON.")
        return

    right = safe_get(case_obj, "right", default={}) or {}
    left = safe_get(case_obj, "left", default={}) or {}

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown("#### Right")
        st.write({
            "Type": get_side_type(right),
            "Rule confidence": get_side_rule_confidence(right),
            "Quality score": get_side_quality_score(right),
            "Reliability": get_side_reliability(right),
            "ECV": get_ecv(right),
            "Compliance": right.get("compliance_ml"),
            "Pressure": right.get("pressure_dapa"),
            "Gradient": right.get("gradient_dapa"),
            "Pressure source": get_pressure_source(right),
        })

        interp_r = get_interpretation(right)
        if interp_r:
            st.markdown("**Interpretation**")
            st.write(interp_r.get("summary_vi"))
            if interp_r.get("red_flags"):
                st.warning("\n".join([f"- {x}" for x in interp_r["red_flags"]]))

    with c_right:
        st.markdown("#### Left")
        st.write({
            "Type": get_side_type(left),
            "Rule confidence": get_side_rule_confidence(left),
            "Quality score": get_side_quality_score(left),
            "Reliability": get_side_reliability(left),
            "ECV": get_ecv(left),
            "Compliance": left.get("compliance_ml"),
            "Pressure": left.get("pressure_dapa"),
            "Gradient": left.get("gradient_dapa"),
            "Pressure source": get_pressure_source(left),
        })

        interp_l = get_interpretation(left)
        if interp_l:
            st.markdown("**Interpretation**")
            st.write(interp_l.get("summary_vi"))
            if interp_l.get("red_flags"):
                st.warning("\n".join([f"- {x}" for x in interp_l["red_flags"]]))

    st.markdown("#### Bilateral / Overall")
    st.write({
        "Bilateral pattern": safe_get(case_obj, "bilateral_pattern", "pattern"),
        "Clinical suggestion": safe_get(case_obj, "bilateral_pattern", "clinical_suggestion"),
        "Overall summary": safe_get(case_obj, "overall_summary"),
    })

    with st.expander("Xem toàn bộ JSON", expanded=False):
        st.json(case_obj)