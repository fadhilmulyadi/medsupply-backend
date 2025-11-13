from typing import Any, Dict, List

import numpy as np


def compute_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hitung KPI utama dari hasil matching.
    """
    summary = result.get("summary", {}) or {}
    assignments: List[Dict[str, Any]] = result.get("assignments", []) or []
    facilities: List[Dict[str, Any]] = result.get("facilities", []) or []

    total_patients = int(summary.get("total_patients", 0))
    total_assigned = int(summary.get("total_assigned", 0))
    total_unassigned = int(summary.get("total_unassigned", total_patients - total_assigned))

    # --- Average distance ---
    if assignments:
        distances = np.array(
            [float(a.get("distance_km", 0.0)) for a in assignments],
            dtype=float,
        )
        avg_distance_km = float(np.mean(distances))
    else:
        avg_distance_km = 0.0

    occ_ratios = []
    for f in facilities:
        occ_ratio = f.get("occ_ratio")
        if occ_ratio is not None:
            occ_ratios.append(float(occ_ratio))

    if occ_ratios:
        occ_arr = np.array(occ_ratios, dtype=float)
        occ_mean = float(np.mean(occ_arr))
        occ_min = float(np.min(occ_arr))
        occ_max = float(np.max(occ_arr))
        if occ_mean > 0:
            load_balance_index = float(np.std(occ_arr) / (occ_mean + 1e-6))
        else:
            load_balance_index = 0.0
    else:
        occ_mean = occ_min = occ_max = 0.0
        load_balance_index = 0.0

    unmet_ratio = 0.0
    if total_patients > 0:
        unmet_ratio = float(total_unassigned / total_patients)

    service_flags = []
    for a in assignments:
        if "service_ok" in a:
            service_flags.append(bool(a["service_ok"]))

    if service_flags:
        service_compliance = float(np.mean(service_flags))
    else:
        service_compliance = 1.0 if assignments else 0.0

    metrics = {
        "total_patients": total_patients,
        "total_assigned": total_assigned,
        "total_unassigned": total_unassigned,
        "avg_distance_km": avg_distance_km,
        "unmet_ratio": unmet_ratio,
        "load_balance_index": load_balance_index,
        "occ_mean": occ_mean,
        "occ_min": occ_min,
        "occ_max": occ_max,
        "service_compliance": service_compliance,
    }

    return metrics
