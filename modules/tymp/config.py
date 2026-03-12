# modules/tymp/config.py
from __future__ import annotations

# Default thresholds (tunable per device / SOP)
DEFAULT_TYMP_CFG = {
    "ranges": {
        "ecv_ml": (0.0, 5.0),          # đổi từ volume_ml -> ecv_ml
        "compliance_ml": (0.0, 5.0),
        "pressure_dapa": (-600.0, 300.0),
        "gradient_dapa": (0.0, 300.0),
    },

    "pressure_windows": {
        # Normal peak pressure window used for A/As/Ad
        "A_PRESS_MIN": -100.0,
        "A_PRESS_MAX": 50.0,

        # C type if negative pressure beyond this
        "C_PRESS_CUTOFF": -100.0,

        # C2 if very negative pressure
        "C2_CUTOFF": -200.0,
    },

    "compliance_cutoffs": {
        "AS_CUTOFF": 0.30,
        "AD_CUTOFF": 1.60,
        "B_COMP_CUTOFF": 0.20,
    },

    "ecv_hints": {
        "HIGH_ECV_HINT": 2.0,
    },

    "gradient_notes": {
        "LOW": 30.0,
        "HIGH": 200.0,
    },
}