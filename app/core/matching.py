from typing import Any, Dict, List, Tuple

import pandas as pd

from app.core.distance import haversine
from app.core.supply import compute_occupancy_summary


def _extract_config(config: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Mengambil parameter bobot dan batasan dari dictionary konfigurasi.
    Mengembalikan (weights, constraints) dengan nilai default yang sesuai.
    """
    weights_cfg = config.get("weights", {}) or {}
    constraints_cfg = config.get("constraints", {}) or {}
    policy_cfg = config.get("policy", {}) or {}

    weights = {
        "wd": float(weights_cfg.get("wd", 0.6)),  # weight distance
        "wo": float(weights_cfg.get("wo", 0.3)),  # weight occupancy
        "wf": float(weights_cfg.get("wf", 0.1)),  # reserved for fairness
    }

    constraints = {
        "radius_km": float(constraints_cfg.get("radius_km", 50.0)),
        "max_load": float(constraints_cfg.get("max_load", 1.0)),
        "target_occupancy": float(policy_cfg.get("target_occupancy", 0.7)),
    }

    return weights, constraints


def _compute_cost(
    distance_km: float,
    occ_ratio: float,
    weights: Dict[str, float],
    constraints: Dict[str, float],
) -> float:
    """
    Menghitung biaya pencocokan antara pasien dan fasilitas.
    Nilai yang lebih rendah menunjukkan kecocokan yang lebih baik.   
    """
    radius_km = constraints["radius_km"]
    target_occ = constraints["target_occupancy"]

    # Normalize distance relative to allowed radius
    d_norm = min(distance_km, radius_km) / radius_km if radius_km > 0 else 1.0

    # Penalize occupancy above target
    occ_penalty = max(0.0, occ_ratio - target_occ)

    wd = weights["wd"]
    wo = weights["wo"]
    wf = weights["wf"]  # belum dipakai, hook untuk fairness ke depan

    # Untuk sekarang fairness term (wf) belum diaktifkan
    cost = wd * d_norm + wo * occ_penalty

    return cost


def greedy_match(
    patients_df: "pd.DataFrame",
    facilities_df: "pd.DataFrame",
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Greedy matching:
    - Patients disortir berdasarkan severity (tinggi dulu).
    - Untuk setiap pasien, pilih RS feasible dengan cost terendah.
    - Update occupancy setiap kali pasien ditugaskan.

    Returns dict with:
        {
          "summary": {...},
          "assignments": [ {...}, ... ]
        }
    """
    if patients_df.empty or facilities_df.empty:
        return {
            "summary": {
                "total_patients": int(len(patients_df)),
                "total_assigned": 0,
                "total_unassigned": int(len(patients_df)),
            },
            "assignments": [],
        }

    weights, constraints = _extract_config(config)
    radius_km = constraints["radius_km"]
    max_load = constraints["max_load"]

    # Tambahkan occ_ratio awal
    facilities_df = compute_occupancy_summary(facilities_df)

    # Map kapasitas dan occupancy: id_rs -> dict(capacity_tt, occupied_tt)
    capacity_map: Dict[Any, Dict[str, float]] = (
        facilities_df.set_index("id_rs")[["capacity_tt", "occupied_tt"]]
        .to_dict(orient="index")
    )

    assignments: List[Dict[str, Any]] = []

    # Sort pasien berdasarkan severity menurun (kalau kolom ada)
    if "severity" in patients_df.columns:
        patients_iter = patients_df.sort_values("severity", ascending=False).iterrows()
    else:
        patients_iter = patients_df.iterrows()

    for _, p in patients_iter:
        patient_id = p["id_pasien"]
        plat = float(p["lat"])
        plon = float(p["lon"])
        case = str(p.get("kasus", "")).lower()

        best_choice = None  # type: ignore
        best_cost = float("inf")

        for _, rs in facilities_df.iterrows():
            rs_id = rs["id_rs"]
            rlat = float(rs["lat"])
            rlon = float(rs["lon"])

            cap_info = capacity_map.get(rs_id)
            if not cap_info:
                continue

            current_occ = float(cap_info["occupied_tt"])
            capacity = float(cap_info["capacity_tt"])
            if capacity <= 0:
                continue

            occ_ratio = current_occ / capacity

            # Hard constraint: jangan melebihi max_load
            if occ_ratio >= max_load:
                continue

            # Hard constraint: layanan harus cocok (kalau ada kolom 'services' dan 'kasus')
            services_str = str(rs.get("services", "")).lower()
            if case and case not in services_str:
                # Lompati RS yang tidak punya layanan yg relevan
                continue

            distance_km = haversine(plat, plon, rlat, rlon)

            # Hard constraint: radius maksimum
            if distance_km > radius_km:
                continue

            cost = _compute_cost(
                distance_km=distance_km,
                occ_ratio=occ_ratio,
                weights=weights,
                constraints=constraints,
            )

            if cost < best_cost:
                best_cost = cost
                best_choice = (rs_id, distance_km, occ_ratio)

        if best_choice is None:
            # Pasien tidak bisa ditempatkan (tidak ada RS feasible)
            continue

        rs_id, distance_km, occ_before = best_choice

        # Update occupancy RS terpilih
        cap_info = capacity_map[rs_id]
        cap_info["occupied_tt"] = cap_info["occupied_tt"] + 1.0
        occ_after = cap_info["occupied_tt"] / cap_info["capacity_tt"]

        assignments.append(
            {
                "patient_id": str(patient_id),
                "hospital_id": str(rs_id),
                "distance_km": float(distance_km),
                "occ_before": float(occ_before),
                "occ_after": float(occ_after),
                "cost": float(best_cost),
            }
        )

    total_patients = int(len(patients_df))
    total_assigned = int(len(assignments))
    total_unassigned = total_patients - total_assigned

    summary = {
        "total_patients": total_patients,
        "total_assigned": total_assigned,
        "total_unassigned": total_unassigned,
    }

    return {"summary": summary, "assignments": assignments}
