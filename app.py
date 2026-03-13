import os
import json
from datetime import datetime

import streamlit as st
import fitz
from PIL import Image

from modules.ocr import set_tesseract_path
from modules.common.app_utils import safe_filename, make_json_safe_result

# ---- Tymp domain (new structure) ----
from modules.tymp.config import DEFAULT_TYMP_CFG as TYMP_CFG
from modules.tymp.tuning import build_tuning_sidebar
from modules.tymp.pipeline import run_tymp_pipeline

# ---- Dataset / review / evaluation ----
from modules.dataset.dataset_explorer import render_dataset_explorer
from modules.dataset.case_review import render_case_review
from modules.dataset.evaluation import render_evaluation_dashboard


# ----------------------------
# App-level constants
# ----------------------------
APP_TITLE = "🦻 Hearing ChatBot"
PAGE_TITLE = "Hearing ChatBot"
DEFAULT_OUT_DIR = "outputs"
DEFAULT_TYMP_PAGE_INDEX = 1
DEFAULT_ZOOM = 3.0
DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def ensure_output_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def render_tymp_result(result: dict, debug: bool = False):
    """
    Render pipeline result to Streamlit UI.
    """
    ui = result.get("_ui", {}) or {}

    page_img = ui.get("page_img")
    right_box = ui.get("right_box")
    left_box = ui.get("left_box")

    cv_right = ui.get("cv_right", {}) or {}
    cv_left = ui.get("cv_left", {}) or {}

    right = result.get("right", {}) or {}
    left = result.get("left", {}) or {}

    cls_r = right.get("tymp_classification", {}) or {}
    cls_l = left.get("tymp_classification", {}) or {}

    interp_r = right.get("interpretation", {}) or {}
    interp_l = left.get("interpretation", {}) or {}

    quality_r = right.get("quality", {}) or {}
    quality_l = left.get("quality", {}) or {}

    bilateral = result.get("bilateral_pattern", {}) or {}
    overall = result.get("overall_summary", "")

    # ----------------------------
    # Debug image / CV
    # ----------------------------
    if debug:
        st.subheader("CV Peak Pressure (daPa) — debug only")
        st.write("Right (CV):", cv_right.get("peak_pressure_dapa"), "quality:", cv_right.get("quality"))
        st.json(cv_right.get("debug", {}))
        st.write("Left  (CV):", cv_left.get("peak_pressure_dapa"), "quality:", cv_left.get("quality"))
        st.json(cv_left.get("debug", {}))

        if page_img is not None:
            st.image(page_img, caption="Trang nhĩ lượng đồ (page 2)", use_container_width=True)

    # ----------------------------
    # Main numeric outputs
    # ----------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Right")
        if debug and right_box is not None:
            st.image(right_box, caption="ROI Right (auto)", use_container_width=True)
            st.text_area("OCR raw (Right)", right.get("raw_text", ""), height=120, key="ocr_raw_right")

        st.write({
            "ECV (ml)": right.get("ecv_ml"),
            "Compliance (ml)": right.get("compliance_ml"),
            "Pressure (daPa) [OCR]": (right.get("debug", {}) or {}).get("pressure_ocr"),
            "Pressure (daPa) [CV]": (right.get("debug", {}) or {}).get("pressure_cv"),
            "Pressure (daPa) [FINAL]": right.get("pressure_dapa"),
            "Pressure source": right.get("pressure_source"),
            "Gradient (daPa)": right.get("gradient_dapa"),
            "Tymp type (Jerger)": cls_r.get("jerger_type"),
            "Rule confidence": cls_r.get("confidence"),
            "Rule reasons": (cls_r.get("reasons", {}) or {}).get("rule"),
        })

        st.markdown("**Tymp Quality**")
        st.write({
            "Quality score": quality_r.get("score"),
            "Reliability": quality_r.get("reliability"),
            "Quality flags": quality_r.get("flags"),
        })

    with col2:
        st.subheader("Left")
        if debug and left_box is not None:
            st.image(left_box, caption="ROI Left (auto)", use_container_width=True)
            st.text_area("OCR raw (Left)", left.get("raw_text", ""), height=120, key="ocr_raw_left")

        st.write({
            "ECV (ml)": left.get("ecv_ml"),
            "Compliance (ml)": left.get("compliance_ml"),
            "Pressure (daPa) [OCR]": (left.get("debug", {}) or {}).get("pressure_ocr"),
            "Pressure (daPa) [CV]": (left.get("debug", {}) or {}).get("pressure_cv"),
            "Pressure (daPa) [FINAL]": left.get("pressure_dapa"),
            "Pressure source": left.get("pressure_source"),
            "Gradient (daPa)": left.get("gradient_dapa"),
            "Tymp type (Jerger)": cls_l.get("jerger_type"),
            "Rule confidence": cls_l.get("confidence"),
            "Rule reasons": (cls_l.get("reasons", {}) or {}).get("rule"),
        })

        st.markdown("**Tymp Quality**")
        st.write({
            "Quality score": quality_l.get("score"),
            "Reliability": quality_l.get("reliability"),
            "Quality flags": quality_l.get("flags"),
        })

    # ----------------------------
    # Interpretation
    # ----------------------------
    st.divider()
    st.subheader("Diễn giải lâm sàng")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Tai phải")
        st.write(interp_r.get("summary_vi", ""))

        if interp_r.get("red_flags"):
            st.warning("\n".join([f"- {x}" for x in interp_r["red_flags"]]))

        with st.expander("Nguyên nhân gợi ý", expanded=False):
            causes = interp_r.get("possible_causes", []) or []
            st.write("\n".join([f"- {x}" for x in causes]) if causes else "—")

        with st.expander("Gợi ý bước tiếp theo", expanded=False):
            steps = interp_r.get("suggest_next_steps", []) or []
            st.write("\n".join([f"- {x}" for x in steps]) if steps else "—")

        st.caption(f"Độ tin cậy diễn giải: {interp_r.get('confidence')}")
        st.caption(f"Tymp quality: {quality_r.get('score')} ({quality_r.get('reliability')})")

        if debug:
            with st.expander("Notes (Right) — debug", expanded=False):
                notes = interp_r.get("notes", []) or []
                st.write("\n".join([f"- {x}" for x in notes]) if notes else "—")

    with c2:
        st.markdown("### Tai trái")
        st.write(interp_l.get("summary_vi", ""))

        if interp_l.get("red_flags"):
            st.warning("\n".join([f"- {x}" for x in interp_l["red_flags"]]))

        with st.expander("Nguyên nhân gợi ý", expanded=False):
            causes = interp_l.get("possible_causes", []) or []
            st.write("\n".join([f"- {x}" for x in causes]) if causes else "—")

        with st.expander("Gợi ý bước tiếp theo", expanded=False):
            steps = interp_l.get("suggest_next_steps", []) or []
            st.write("\n".join([f"- {x}" for x in steps]) if steps else "—")

        st.caption(f"Độ tin cậy diễn giải: {interp_l.get('confidence')}")
        st.caption(f"Tymp quality: {quality_l.get('score')} ({quality_l.get('reliability')})")

        if debug:
            with st.expander("Notes (Left) — debug", expanded=False):
                notes = interp_l.get("notes", []) or []
                st.write("\n".join([f"- {x}" for x in notes]) if notes else "—")

    # ----------------------------
    # Bilateral / overall
    # ----------------------------
    st.markdown("### Tổng kết 2 tai")
    st.info(overall)

    st.subheader("Bilateral Clinical Pattern")
    st.write({
        "Pattern": bilateral.get("pattern"),
        "Clinical suggestion": bilateral.get("clinical_suggestion"),
        "Notes": bilateral.get("notes"),
    })

    if debug:
        st.subheader("JSON preview")
        st.json(make_json_safe_result(result))


def render_pdf_analysis_tab():
    set_tesseract_path(DEFAULT_TESSERACT_PATH)

    uploaded_file = st.file_uploader("Chọn file PDF (scan)", type=["pdf"], key="pdf_uploader_main")
    debug = st.checkbox("Debug: hiển thị vùng crop / OCR raw / CV debug", value=False, key="debug_main")

    out_dir = ensure_output_dir(DEFAULT_OUT_DIR)
    active_cfg = build_tuning_sidebar(TYMP_CFG, out_dir)

    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "last_run_key" not in st.session_state:
        st.session_state.last_run_key = None
    if "last_saved_path" not in st.session_state:
        st.session_state.last_saved_path = None

    if not uploaded_file:
        return

    pdf_bytes = uploaded_file.getvalue()

    # run_key nhận diện duy nhất cho file + config hiện tại
    cfg_key = json.dumps(active_cfg, ensure_ascii=False, sort_keys=True, default=str)
    run_key = f"{uploaded_file.name}_{len(pdf_bytes)}_{cfg_key}"

    col_a, col_b = st.columns([1, 3])
    with col_a:
        run_clicked = st.button("Phân tích PDF", type="primary")
    with col_b:
        st.caption("Cùng file + cùng config sẽ không lưu lặp lại.")

    if run_clicked:
        # Nếu cùng file + cùng config như lần trước thì không chạy/lưu lại
        if st.session_state.last_run_key == run_key and st.session_state.last_result is not None:
            st.info("File này với cấu hình hiện tại đã được phân tích trước đó. Không lưu thêm bản mới.")
        else:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            page_index = DEFAULT_TYMP_PAGE_INDEX
            page = doc.load_page(page_index)

            zoom = DEFAULT_ZOOM
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            result = run_tymp_pipeline(
                page_img=page_img,
                cfg=active_cfg,
                source_pdf=uploaded_file.name,
                page_index=page_index,
                zoom=zoom,
                debug=debug,
            )

            base_name = safe_filename(uploaded_file.name.replace(".pdf", ""))
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(out_dir, f"{base_name}_tymp_{ts}.json")

            result_to_save = make_json_safe_result(result)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result_to_save, f, ensure_ascii=False, indent=2)

            st.session_state.last_result = result
            st.session_state.last_run_key = run_key
            st.session_state.last_saved_path = out_path

            st.success(f"Đã lưu kết quả JSON: {out_path}")

    if st.session_state.last_result is not None and st.session_state.last_run_key == run_key:
        render_tymp_result(st.session_state.last_result, debug=debug)

        if st.session_state.last_saved_path:
            st.info(f"File JSON đã lưu: {st.session_state.last_saved_path}")


def render_dataset_tabs():
    out_dir = ensure_output_dir(DEFAULT_OUT_DIR)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Phân tích PDF",
        "Dataset Explorer",
        "Case Review",
        "Evaluation",
    ])

    with tab1:
        render_pdf_analysis_tab()

    with tab2:
        render_dataset_explorer(out_dir)

    with tab3:
        render_case_review(out_dir)

    with tab4:
        render_evaluation_dashboard(out_dir)


# ----------------------------
# Streamlit UI entry
# ----------------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title(APP_TITLE)
render_dataset_tabs()