# modules/dataset/case_review.py
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

from modules.dataset.common import (
    safe_get,
    get_side_type,
    get_side_rule_confidence,
    get_side_quality_score,
    get_interpretation,
    get_ecv,
)


JERGER_OPTIONS = ["A", "As", "Ad", "B", "C", "Unknown"]


def load_case_jsons(out_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if not os.path.isdir(out_dir):
        return rows

    for fn in sorted(os.listdir(out_dir), reverse=True):
        if not fn.lower().endswith(".json"):
            continue

        full_path = os.path.join(out_dir, fn)

        if os.path.isdir(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                obj = json.load(f)

            right = safe_get(obj, "right", default={}) or {}
            left = safe_get(obj, "left", default={}) or {}

            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "created_at": safe_get(obj, "meta", "created_at"),
                "source_pdf": safe_get(obj, "meta", "source_pdf"),
                "right_type": get_side_type(right),
                "left_type": get_side_type(left),
                "right_quality": get_side_quality_score(right),
                "left_quality": get_side_quality_score(left),
            })

        except Exception as e:
            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "created_at": None,
                "source_pdf": None,
                "right_type": "ERROR",
                "left_type": "ERROR",
                "right_quality": None,
                "left_quality": None,
                "error": str(e),
            })

    return rows


def rows_to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "file_name",
            "created_at",
            "source_pdf",
            "right_type",
            "left_type",
            "right_quality",
            "left_quality",
            "full_path",
        ])
    return pd.DataFrame(rows)


def _save_reviewed_case(case_obj: Dict[str, Any], reviewed_dir: str, original_file_name: str) -> str:
    os.makedirs(reviewed_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = original_file_name.rsplit(".", 1)[0]
    out_name = f"{base_name}_reviewed_{ts}.json"
    out_path = os.path.join(reviewed_dir, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(case_obj, f, ensure_ascii=False, indent=2)

    return out_path


def render_case_review(out_dir: str):
    st.subheader("Case Review / Relabel")

    reviewed_dir = os.path.join(out_dir, "reviewed")
    os.makedirs(reviewed_dir, exist_ok=True)

    rows = load_case_jsons(out_dir)
    df = rows_to_df(rows)

    # loại các file nằm trong outputs/reviewed nếu lẫn logic path
    if not df.empty and "full_path" in df.columns:
        df = df[
            ~df["full_path"].astype(str).str.replace("\\", "/").str.contains("/reviewed/", na=False)
        ]

    if df.empty:
        st.info("Chưa có file JSON nào để review.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        filter_r = st.selectbox(
            "Filter Right Type",
            ["ALL"] + sorted(df["right_type"].dropna().astype(str).unique().tolist()),
            key="case_review_filter_r",
        )
    with c2:
        filter_l = st.selectbox(
            "Filter Left Type",
            ["ALL"] + sorted(df["left_type"].dropna().astype(str).unique().tolist()),
            key="case_review_filter_l",
        )
    with c3:
        keyword = st.text_input(
            "Search file / PDF",
            value="",
            key="case_review_keyword",
        ).strip().lower()

    filtered = df.copy()

    if filter_r != "ALL":
        filtered = filtered[filtered["right_type"].astype(str) == filter_r]
    if filter_l != "ALL":
        filtered = filtered[filtered["left_type"].astype(str) == filter_l]
    if keyword:
        filtered = filtered[
            filtered["file_name"].astype(str).str.lower().str.contains(keyword, na=False) |
            filtered["source_pdf"].astype(str).str.lower().str.contains(keyword, na=False)
        ]

    st.markdown("### Danh sách ca cần review")
    st.dataframe(
        filtered.drop(columns=["full_path"], errors="ignore"),
        use_container_width=True,
        hide_index=True
    )

    if filtered.empty:
        st.warning("Không có ca nào phù hợp bộ lọc.")
        return

    selected_file = st.selectbox(
        "Chọn ca để review",
        filtered["file_name"].tolist(),
        key="case_review_selected_file",
    )
    selected_row = filtered[filtered["file_name"] == selected_file].iloc[0]
    full_path = selected_row["full_path"]

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            case_obj = json.load(f)
    except Exception as e:
        st.error(f"Không đọc được JSON: {e}")
        return

    right = safe_get(case_obj, "right", default={}) or {}
    left = safe_get(case_obj, "left", default={}) or {}

    st.markdown("### Thông tin hiện tại")

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown("#### Tai phải")
        st.write({
            "Engine type": get_side_type(right),
            "Rule confidence": get_side_rule_confidence(right),
            "Quality score": get_side_quality_score(right),
            "ECV": get_ecv(right),
            "Compliance": right.get("compliance_ml"),
            "Pressure": right.get("pressure_dapa"),
            "Gradient": right.get("gradient_dapa"),
        })
        st.write("Interpretation:", (get_interpretation(right) or {}).get("summary_vi"))

    with c_right:
        st.markdown("#### Tai trái")
        st.write({
            "Engine type": get_side_type(left),
            "Rule confidence": get_side_rule_confidence(left),
            "Quality score": get_side_quality_score(left),
            "ECV": get_ecv(left),
            "Compliance": left.get("compliance_ml"),
            "Pressure": left.get("pressure_dapa"),
            "Gradient": left.get("gradient_dapa"),
        })
        st.write("Interpretation:", (get_interpretation(left) or {}).get("summary_vi"))

    st.markdown("### Review / Relabel")

    engine_r = get_side_type(right) or "Unknown"
    engine_l = get_side_type(left) or "Unknown"

    rr1, rr2 = st.columns(2)

    with rr1:
        reviewed_right = st.selectbox(
            "Reviewed Right Type",
            JERGER_OPTIONS,
            index=JERGER_OPTIONS.index(engine_r) if engine_r in JERGER_OPTIONS else JERGER_OPTIONS.index("Unknown"),
            key=f"review_right_{selected_file}",
        )

    with rr2:
        reviewed_left = st.selectbox(
            "Reviewed Left Type",
            JERGER_OPTIONS,
            index=JERGER_OPTIONS.index(engine_l) if engine_l in JERGER_OPTIONS else JERGER_OPTIONS.index("Unknown"),
            key=f"review_left_{selected_file}",
        )

    reviewer_name = st.text_input(
        "Reviewer name",
        value="",
        key=f"reviewer_{selected_file}",
    )
    reviewer_note = st.text_area(
        "Reviewer note",
        value="",
        height=120,
        key=f"review_note_{selected_file}",
    )
    doctor_confirmed = st.checkbox(
        "Bác sĩ xác nhận nhãn review này",
        value=False,
        key=f"doctor_confirmed_{selected_file}",
    )

    changed_right = reviewed_right != engine_r
    changed_left = reviewed_left != engine_l

    if changed_right or changed_left:
        st.warning(
            f"Đã thay đổi nhãn: "
            f"Right {engine_r} → {reviewed_right}; "
            f"Left {engine_l} → {reviewed_left}"
        )
    else:
        st.info("Nhãn review hiện trùng với nhãn engine.")

    if st.button("💾 Lưu reviewed case", key=f"save_reviewed_{selected_file}"):
        reviewed_obj = json.loads(json.dumps(case_obj))  # deep copy safe

        reviewed_obj.setdefault("review", {})
        reviewed_obj["review"]["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reviewed_obj["review"]["reviewer_name"] = reviewer_name
        reviewed_obj["review"]["reviewer_note"] = reviewer_note
        reviewed_obj["review"]["doctor_confirmed"] = doctor_confirmed
        reviewed_obj["review"]["source_json"] = selected_file

        reviewed_obj["review"]["right"] = {
            "engine_label": engine_r,
            "reviewed_label": reviewed_right,
            "label_changed": changed_right,
        }
        reviewed_obj["review"]["left"] = {
            "engine_label": engine_l,
            "reviewed_label": reviewed_left,
            "label_changed": changed_left,
        }

        reviewed_obj["gold_label"] = {
            "right_jerger_type": reviewed_right,
            "left_jerger_type": reviewed_left,
            "is_doctor_confirmed": doctor_confirmed,
        }

        out_path = _save_reviewed_case(reviewed_obj, reviewed_dir, selected_file)
        st.success(f"Đã lưu reviewed case: {out_path}")

    with st.expander("Xem JSON hiện tại", expanded=False):
        st.json(case_obj)

    st.markdown("### Reviewed dataset files")
    reviewed_files = sorted(
        [x for x in os.listdir(reviewed_dir) if x.lower().endswith(".json")],
        reverse=True
    )
    if reviewed_files:
        st.write(reviewed_files[:30])
    else:
        st.caption("Chưa có reviewed file nào.")