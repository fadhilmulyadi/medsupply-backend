from typing import Any, Dict, List, Tuple

import pandas as pd

from app.core.distance import haversine
from app.core.supply import compute_occupancy_summary
from app.core.solver import solve_hungarian_with_capacity


def _extract_config(config: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float], str]:
    """
    Ambil parameter solver dari config.json
    - weights: wd, wo, wf
    - constraints: radius_km, max_load, target_occupancy
    - solver: greedy | hungarian | mcmf
    """
    weights_cfg = config.get("weights", {}) or {}
    constraints_cfg = config.get("constraints", {}) or {}
    policy_cfg = config.get("policy", {}) or {}
    solver = str(config.get("solver", "greedy")).lower()

    weights = {
        "wd": float(weights_cfg.get("wd", 0.6)),
        "wo": float(weights_cfg.get("wo", 0.3)),
        "wf": float(weights_cfg.get("wf", 0.1)),
    }
    constraints = {
        "radius_km": float(constraints_cfg.get("radius_km", 50.0)),
        "max_load": float(constraints_cfg.get("max_load", 1.0)),
        # simpan target_occupancy di constraints agar gampang diakses
        "target_occupancy": float(policy_cfg.get("target_occupancy", 0.7)),
    }
    return weights, constraints, solver


def _normalize_patients(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adaptasi nama kolom dari sumber berbeda ke format internal:
    - id_pasien      ← patient_code / id
    - kasus          ← service_type
    """
    out = df.copy()

    if "id_pasien" not in out.columns:
        if "patient_code" in out.columns:
            out["id_pasien"] = out["patient_code"]
        elif "id" in out.columns:
            out["id_pasien"] = out["id"]

    if "kasus" not in out.columns and "service_type" in out.columns:
        out["kasus"] = out["service_type"]

    return out


def _services_match(services_value: Any, case: str) -> bool:
    """
    Cek apakah facility punya layanan (case) yang diminta pasien.
    services_value bisa berupa:
    - list ['UGD', 'ICU', ...]  (hasil dari Postgres array)
    - string "UGD, ICU, RAWAT_INAP"
    """
    if not case:
        return True

    case_lower = case.lower()

    # Jika dari Postgres array -> list/tuple
    if isinstance(services_value, (list, tuple)):
        services_lower = [str(s).lower() for s in services_value]
        return case_lower in services_lower

    # Jika dari CSV / string biasa
    services_str = str(services_value or "").lower()
    return case_lower in services_str


def _compute_cost(
    distance_km: float,
    occ_ratio: float,
    weights: Dict[str, float],
    constraints: Dict[str, float],
) -> float:
    """
    Biaya = kombinasi jarak + penalty occupancy di atas target.
    Semakin kecil semakin baik.
    """
    radius_km = constraints["radius_km"]
    target_occ = constraints["target_occupancy"]

    d_norm = min(distance_km, radius_km) / radius_km if radius_km > 0 else 1.0
    occ_penalty = max(0.0, occ_ratio - target_occ)

    return weights["wd"] * d_norm + weights["wo"] * occ_penalty


def greedy_match(
    patients_df: pd.DataFrame,
    facilities_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Greedy matching:
    - sort pasien dari severity tertinggi
    - tiap pasien pilih RS dengan cost terkecil yang masih feasible
    """
    patients_df = _normalize_patients(patients_df)

    if patients_df.empty or facilities_df.empty:
        return {
            "summary": {
                "total_patients": int(len(patients_df)),
                "total_assigned": 0,
                "total_unassigned": int(len(patients_df)),
            },
            "assignments": [],
            "facilities": [],
        }

    weights, constraints, _ = _extract_config(config)
    radius_km = constraints["radius_km"]
    max_load = constraints["max_load"]

    # hitung occupancy awal
    facilities_df = compute_occupancy_summary(facilities_df)

    # Map kapasitas per id_rs
    capacity_map = (
        facilities_df.set_index("id_rs")[["capacity_tt", "occupied_tt"]]
        .to_dict(orient="index")
    )

    assignments: List[Dict[str, Any]] = []

    # Prioritaskan pasien dengan severity tertinggi
    if "severity" in patients_df.columns:
        patients_iter = patients_df.sort_values("severity", ascending=False).iterrows()
    else:
        patients_iter = patients_df.iterrows()

    for _, p in patients_iter:
        patient_id = p["id_pasien"]
        plat = float(p["lat"])
        plon = float(p["lon"])
        case = str(p.get("kasus", "")).lower()

        best_choice = None
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
            if occ_ratio >= max_load:
                continue

            # cek apakah layanan RS cocok dengan kasus pasien
            if not _services_match(rs.get("services"), case):
                continue

            distance_km = haversine(plat, plon, rlat, rlon)
            if distance_km > radius_km:
                continue

            cost = _compute_cost(distance_km, occ_ratio, weights, constraints)

            if cost < best_cost:
                best_cost = cost
                best_choice = (rs_id, distance_km, occ_ratio)

        if best_choice is None:
            # tidak ada RS feasible -> dianggap unassigned (tidak dimasukkan assignments)
            continue

        rs_id, distance_km, occ_before = best_choice

        # update occupancy di snapshot
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

    # Snapshot kondisi akhir fasilitas
    facilities_snapshot: List[Dict[str, Any]] = []
    for _, rs in facilities_df.iterrows():
        rs_id = rs["id_rs"]
        cap_info = capacity_map.get(rs_id)
        if not cap_info:
            continue
        cap = float(cap_info["capacity_tt"])
        occ = float(cap_info["occupied_tt"])
        occ_ratio = occ / cap if cap > 0 else 0.0
        facilities_snapshot.append(
            {
                "hospital_id": str(rs_id),
                "capacity_tt": cap,
                "occupied_tt": occ,
                "occ_ratio": float(occ_ratio),
                "wilayah": rs.get("wilayah"),
                "kelas": rs.get("kelas"),
            }
        )

    return {
        "summary": summary,
        "assignments": assignments,
        "facilities": facilities_snapshot,
    }


def run_match(
    patients_df: pd.DataFrame,
    facilities_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Wrapper memilih solver: greedy | hungarian | mcmf.
    Tetap kompatibel dengan versi lama, tapi sekarang:
    - support nama kolom dari database (patient_code, service_type, dll.)
    """
    patients_df = _normalize_patients(patients_df)

    if patients_df.empty or facilities_df.empty:
        return {
            "summary": {
                "total_patients": int(len(patients_df)),
                "total_assigned": 0,
                "total_unassigned": int(len(patients_df)),
            },
            "assignments": [],
            "facilities": [],
        }

    weights, constraints, solver = _extract_config(config)
    facilities_df = compute_occupancy_summary(facilities_df)

    if solver == "greedy":
        return greedy_match(patients_df, facilities_df, config)

    if solver in ("hungarian", "mcmf"):
        assignments, facilities_snapshot = solve_hungarian_with_capacity(
            patients_df=patients_df,
            facilities_df=facilities_df,
            weights=weights,
            constraints=constraints,
        )
        total_patients = int(len(patients_df))
        total_assigned = int(len(assignments))
        total_unassigned = total_patients - total_assigned
        summary = {
            "total_patients": total_patients,
            "total_assigned": total_assigned,
            "total_unassigned": total_unassigned,
        }
        return {
            "summary": summary,
            "assignments": assignments,
            "facilities": facilities_snapshot,
        }

    # fallback
    return greedy_match(patients_df, facilities_df, config)
