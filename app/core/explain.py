from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from app.core.distance import haversine

def _extract_config(config: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
    weights_cfg = (config or {}).get("weights", {}) or {}
    constraints_cfg = (config or {}).get("constraints", {}) or {}
    policy_cfg = (config or {}).get("policy", {}) or {}
    weights = {"wd": float(weights_cfg.get("wd", 0.6)),
               "wo": float(weights_cfg.get("wo", 0.3)),
               "wf": float(weights_cfg.get("wf", 0.1))}
    constraints = {"radius_km": float(constraints_cfg.get("radius_km", 50.0)),
                   "max_load": float(constraints_cfg.get("max_load", 1.0)),
                   "target_occupancy": float(policy_cfg.get("target_occupancy", 0.7))}
    return weights, constraints

def _compute_cost(distance_km: float, occ_ratio: float, weights: Dict[str, float], constraints: Dict[str, float]) -> float:
    radius_km = constraints["radius_km"]
    target_occ = constraints["target_occupancy"]
    d_norm = min(distance_km, radius_km) / radius_km if radius_km > 0 else 1.0
    occ_penalty = max(0.0, occ_ratio - target_occ)
    return weights["wd"] * d_norm + weights["wo"] * occ_penalty

def _feasible_candidates(patient: "pd.Series", facilities_df: "pd.DataFrame", config: Dict[str, Any]) -> List[Dict[str, Any]]:
    weights, constraints = _extract_config(config)
    radius_km = constraints["radius_km"]
    max_load = constraints["max_load"]

    plat = float(patient["lat"]); plon = float(patient["lon"])
    case = str(patient.get("kasus", "")).lower()

    rows: List[Dict[str, Any]] = []
    for _, rs in facilities_df.iterrows():
        cap = float(rs.get("capacity_tt", 0)); occ = float(rs.get("occupied_tt", 0))
        if cap <= 0: continue
        occ_ratio = occ / cap
        if occ_ratio >= max_load: continue

        services_str = str(rs.get("services", "")).lower()
        if case and case not in services_str: continue

        distance_km = haversine(plat, plon, float(rs["lat"]), float(rs["lon"]))
        if distance_km > radius_km: continue

        cost = _compute_cost(distance_km, occ_ratio, weights, constraints)
        rows.append({"hospital_id": str(rs["id_rs"]),
                     "distance_km": float(distance_km),
                     "occ_ratio": float(occ_ratio),
                     "cost": float(cost),
                     "services": services_str})
    rows.sort(key=lambda r: r["cost"])
    return rows

def _fmt_pct(x: float) -> str:
    return f"{x*100:.0f}%"

def build_explanation_for_patient(
    patient: "pd.Series",
    assigned: Dict[str, Any],
    facilities_df: "pd.DataFrame",
    config: Dict[str, Any],
    lang: str = "id",
    top_k_alternatives: int = 1,
) -> Dict[str, Any]:
    weights, constraints = _extract_config(config)
    radius_km = constraints["radius_km"]; target_occ = constraints["target_occupancy"]

    patient_id = str(assigned["patient_id"])
    rs_id = str(assigned["hospital_id"])
    dist = float(assigned.get("distance_km", 0.0))
    occ_before = float(assigned.get("occ_before", 0.0))
    occ_after = float(assigned.get("occ_after", 0.0))

    # alternatif dihitung dari kondisi "sebelum"
    candidates = _feasible_candidates(patient, facilities_df, config)
    alt = next((c for c in candidates if c["hospital_id"] != rs_id), None)

    case = str(patient.get("kasus", "")).upper() if patient.get("kasus") is not None else ""
    sev_part = ""
    if "severity" in patient and pd.notna(patient["severity"]):
        try:
            sev_part = f" dengan tingkat keparahan {float(patient['severity']):.1f}"
        except Exception:
            sev_part = ""

    if lang == "en":
        reason = (f"Patient {patient_id}{sev_part} is allocated to hospital {rs_id} "
                  f"because its distance is {dist:.2f} km (within {radius_km:.0f} km radius), "
                  f"the required service '{case}' is available, and the occupancy was {_fmt_pct(occ_before)} "
                  f"(target {int(target_occ*100)}%). After allocation, occupancy became {_fmt_pct(occ_after)}.")
        if alt:
            reason += (f" Top alternative: {alt['hospital_id']} at {alt['distance_km']:.2f} km "
                       f"with cost {alt['cost']:.3f} and occupancy {_fmt_pct(alt['occ_ratio'])}.")
    else:
        reason = (f"Pasien {patient_id}{sev_part} dialokasikan ke RS {rs_id} "
                  f"karena jarak {dist:.2f} km (dalam radius {radius_km:.0f} km), "
                  f"layanan '{case}' tersedia, dan okupansi {_fmt_pct(occ_before)} "
                  f"(target {int(target_occ*100)}%). Setelah alokasi, okupansi menjadi {_fmt_pct(occ_after)}.")
        if alt:
            reason += (f" Alternatif terbaik: {alt['hospital_id']} berjarak {alt['distance_km']:.2f} km "
                       f"dengan cost {alt['cost']:.3f} dan okupansi {_fmt_pct(alt['occ_ratio'])}.")

    item: Dict[str, Any] = {"patient_id": patient_id, "hospital_id": rs_id, "narrative": reason}
    if alt:
        item["alternative"] = {"hospital_id": alt["hospital_id"],
                               "distance_km": alt["distance_km"],
                               "occ_ratio": alt["occ_ratio"],
                               "cost": alt["cost"]}
    return item
