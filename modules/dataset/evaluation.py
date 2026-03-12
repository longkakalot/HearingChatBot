# modules/dataset/evaluation.py
from __future__ import annotations

import os
import json
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

from modules.dataset.common import (
    safe_get,
    get_side_quality_score,
    get_side_reliability,
    get_side_rule_confidence,
)


JERGER_LABELS = ["A", "As", "Ad", "B", "C", "Unknown"]


def load_reviewed_cases(reviewed_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if not os.path.isdir(reviewed_dir):
        return rows

    for fn in sorted(os.listdir(reviewed_dir), reverse=True):
        if not fn.lower().endswith(".json"):
            continue

        full_path = os.path.join(reviewed_dir, fn)

        if os.path.isdir(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                obj = json.load(f)

            right = safe_get(obj, "right", default={}) or {}
            left = safe_get(obj, "left", default={}) or {}

            # Right ear
            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "Right",
                "engine_label": safe_get(obj, "review", "right", "engine_label"),
                "reviewed_label": safe_get(obj, "review", "right", "reviewed_label"),
                "label_changed": safe_get(obj, "review", "right", "label_changed"),
                "doctor_confirmed": safe_get(obj, "review", "doctor_confirmed"),
                "reviewer_name": safe_get(obj, "review", "reviewer_name"),
                "reviewed_at": safe_get(obj, "review", "reviewed_at"),
                "quality_score": get_side_quality_score(right),
                "quality_reliability": get_side_reliability(right),
                "rule_confidence": get_side_rule_confidence(right),
                "source_json": safe_get(obj, "review", "source_json"),
                "source_pdf": safe_get(obj, "meta", "source_pdf"),
            })

            # Left ear
            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "Left",
                "engine_label": safe_get(obj, "review", "left", "engine_label"),
                "reviewed_label": safe_get(obj, "review", "left", "reviewed_label"),
                "label_changed": safe_get(obj, "review", "left", "label_changed"),
                "doctor_confirmed": safe_get(obj, "review", "doctor_confirmed"),
                "reviewer_name": safe_get(obj, "review", "reviewer_name"),
                "reviewed_at": safe_get(obj, "review", "reviewed_at"),
                "quality_score": get_side_quality_score(left),
                "quality_reliability": get_side_reliability(left),
                "rule_confidence": get_side_rule_confidence(left),
                "source_json": safe_get(obj, "review", "source_json"),
                "source_pdf": safe_get(obj, "meta", "source_pdf"),
            })

        except Exception as e:
            rows.append({
                "file_name": fn,
                "full_path": full_path,
                "side": "ERROR",
                "engine_label": "ERROR",
                "reviewed_label": "ERROR",
                "label_changed": None,
                "doctor_confirmed": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "quality_score": None,
                "quality_reliability": None,
                "rule_confidence": None,
                "source_json": None,
                "source_pdf": f"JSON parse error: {e}",
            })

    return rows


def rows_to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "file_name",
            "full_path",
            "side",
            "engine_label",
            "reviewed_label",
            "label_changed",
            "doctor_confirmed",
            "reviewer_name",
            "reviewed_at",
            "quality_score",
            "quality_reliability",
            "rule_confidence",
            "source_json",
            "source_pdf",
        ])
    return pd.DataFrame(rows)


def _calc_accuracy(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0

    valid = df.dropna(subset=["engine_label", "reviewed_label"]).copy()
    if valid.empty:
        return 0.0

    return round((valid["engine_label"] == valid["reviewed_label"]).mean() * 100, 2)


def _per_class_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    valid = df.dropna(subset=["engine_label", "reviewed_label"]).copy()

    for label in JERGER_LABELS:
        subset = valid[valid["reviewed_label"] == label]
        n = len(subset)

        if n == 0:
            rows.append({
                "class": label,
                "n_reviewed": 0,
                "correct": 0,
                "accuracy_pct": None,
            })
            continue

        correct = int((subset["engine_label"] == subset["reviewed_label"]).sum())
        acc = round(correct / n * 100, 2)

        rows.append({
            "class": label,
            "n_reviewed": n,
            "correct": correct,
            "accuracy_pct": acc,
        })

    return pd.DataFrame(rows)


def _build_confusion_matrix(df: pd.DataFrame) -> pd.DataFrame:
    valid = df.dropna(subset=["engine_label", "reviewed_label"]).copy()

    if valid.empty:
        return pd.DataFrame(index=JERGER_LABELS, columns=JERGER_LABELS).fillna(0)

    cm = pd.crosstab(
        valid["reviewed_label"],
        valid["engine_label"],
        rownames=["Reviewed"],
        colnames=["Engine"],
        dropna=False,
    )

    cm = cm.reindex(index=JERGER_LABELS, columns=JERGER_LABELS, fill_value=0)
    return cm


def _quality_error_summary(df: pd.DataFrame) -> pd.DataFrame:
    valid = df.dropna(subset=["engine_label", "reviewed_label"]).copy()

    if valid.empty:
        return pd.DataFrame(columns=["bucket", "n", "error_rate_pct"])

    valid["is_correct"] = valid["engine_label"] == valid["reviewed_label"]

    def bucketize(x):
        if pd.isna(x):
            return "unknown"
        if x >= 0.90:
            return "0.90-1.00"
        if x >= 0.70:
            return "0.70-0.89"
        if x >= 0.50:
            return "0.50-0.69"
        return "<0.50"

    valid["bucket"] = valid["quality_score"].apply(bucketize)

    rows = []
    for bucket in ["0.90-1.00", "0.70-0.89", "0.50-0.69", "<0.50", "unknown"]:
        sub = valid[valid["bucket"] == bucket]
        n = len(sub)

        if n == 0:
            rows.append({
                "bucket": bucket,
                "n": 0,
                "error_rate_pct": None,
            })
            continue

        error_rate = round((~sub["is_correct"]).mean() * 100, 2)
        rows.append({
            "bucket": bucket,
            "n": n,
            "error_rate_pct": error_rate,
        })

    return pd.DataFrame(rows)


def render_evaluation_dashboard(out_dir: str):
    st.subheader("Evaluation Dashboard")

    reviewed_dir = os.path.join(out_dir, "reviewed")
    os.makedirs(reviewed_dir, exist_ok=True)

    rows = load_reviewed_cases(reviewed_dir)
    df = rows_to_df(rows)

    if df.empty:
        st.info("Chưa có reviewed dataset nào để đánh giá.")
        return

    # -------------------------
    # Filters
    # -------------------------
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        only_doctor_confirmed = st.checkbox(
            "Chỉ lấy ca đã bác sĩ xác nhận",
            value=True,
            key="eval_only_doctor_confirmed",
        )

    with c2:
        side_filter = st.selectbox(
            "Filter side",
            ["ALL", "Right", "Left"],
            index=0,
            key="eval_side_filter",
        )

    with c3:
        reviewed_label_filter = st.selectbox(
            "Filter reviewed label",
            ["ALL"] + JERGER_LABELS,
            index=0,
            key="eval_reviewed_label_filter",
        )

    with c4:
        keyword = st.text_input(
            "Search file / pdf",
            value="",
            key="eval_keyword_filter",
        ).strip().lower()

    filtered = df.copy()

    if only_doctor_confirmed:
        filtered = filtered[filtered["doctor_confirmed"] == True]

    if side_filter != "ALL":
        filtered = filtered[filtered["side"] == side_filter]

    if reviewed_label_filter != "ALL":
        filtered = filtered[filtered["reviewed_label"] == reviewed_label_filter]

    if keyword:
        filtered = filtered[
            filtered["file_name"].astype(str).str.lower().str.contains(keyword, na=False) |
            filtered["source_pdf"].astype(str).str.lower().str.contains(keyword, na=False)
        ]

    if filtered.empty:
        st.warning("Không có dữ liệu phù hợp bộ lọc hiện tại.")
        return

    # -------------------------
    # KPI
    # -------------------------
    overall_acc = _calc_accuracy(filtered)
    total_ears = len(filtered)
    changed_count = int(filtered["label_changed"].fillna(False).sum())
    confirmed_count = int(filtered["doctor_confirmed"].fillna(False).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total reviewed ears", total_ears)
    k2.metric("Overall accuracy (%)", overall_acc)
    k3.metric("Label changed", changed_count)
    k4.metric("Doctor confirmed", confirmed_count)

    # -------------------------
    # Per-class metrics
    # -------------------------
    st.markdown("### Accuracy theo từng lớp")
    per_class_df = _per_class_metrics(filtered)
    st.dataframe(per_class_df, use_container_width=True, hide_index=True)

    # -------------------------
    # Confusion matrix
    # -------------------------
    st.markdown("### Confusion Matrix")
    cm = _build_confusion_matrix(filtered)
    st.dataframe(cm, use_container_width=True)

    # -------------------------
    # Quality vs error
    # -------------------------
    st.markdown("### Quality score vs Error rate")
    q_df = _quality_error_summary(filtered)
    st.dataframe(q_df, use_container_width=True, hide_index=True)

    # -------------------------
    # Detailed reviewed table
    # -------------------------
    st.markdown("### Reviewed case details")
    detail_cols = [
        "file_name",
        "side",
        "engine_label",
        "reviewed_label",
        "label_changed",
        "doctor_confirmed",
        "quality_score",
        "quality_reliability",
        "rule_confidence",
        "reviewer_name",
        "reviewed_at",
        "source_pdf",
    ]
    show_df = filtered[detail_cols].copy()
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    # CSV export
    csv_bytes = show_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Export evaluation CSV",
        data=csv_bytes,
        file_name="tymp_evaluation.csv",
        mime="text/csv",
        key="eval_export_csv",
    )