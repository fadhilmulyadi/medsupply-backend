from typing import Any, Dict, List, Optional, Tuple
import math
import pandas as pd

from app.core.matching import greedy_match
from app.core.metrics import compute_metrics


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def apply_capacity_drop(
    facilities_df: "pd.DataFrame",
    drop_pct: float,
    wilayah: Optional[str] = None,
    kelas: Optional[str] = None,
) -> "pd.DataFrame":
    """
    Turunkan kapasitas TT sebagian RS.
    drop_pct: 0.0..1.0  (mis. 0.3 berarti turunkan 30%)
    Bisa difilter per wilayah/kelas.
    """
    drop_pct = max(0.0, min(1.0, drop_pct))
    df = facilities_df.copy()

    mask = pd.Series([True] * len(df))
    if wilayah is not None:
        mask &= (df.get("wilayah").astype(str).str.lower() == str(wilayah).lower())
    if kelas is not None:
        mask &= (df.get("kelas").astype(str).str.lower() == str(kelas).lower())

    # turunkan kapasitas; jaga agar capacity >= occupied
    df.loc[mask, "capacity_tt"] = (df.loc[mask, "capacity_tt"] * (1.0 - drop_pct)).round().clip(lower=1)
    over_occ = df["occupied_tt"] > df["capacity_tt"]
    df.loc[over_occ, "capacity_tt"] = df.loc[over_occ, "occupied_tt"]

    return df


def apply_policy_change(
    config: Dict[str, Any],
    radius_km: Optional[float] = None,
    max_load: Optional[float] = None,
    target_occupancy: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Ubah parameter kebijakan di config (in-place copy).
    """
    new_cfg = dict(config)  # shallow copy ok
    constraints = dict(new_cfg.get("constraints", {}) or {})
    policy = dict(new_cfg.get("policy", {}) or {})

    if radius_km is not None:
        constraints["radius_km"] = float(radius_km)
    if max_load is not None:
        constraints["max_load"] = float(max_load)
    if target_occupancy is not None:
        policy["target_occupancy"] = float(target_occupancy)

    new_cfg["constraints"] = constraints
    new_cfg["policy"] = policy
    return new_cfg


def apply_demand_spike(
    patients_df: "pd.DataFrame",
    spike_pct: float,
    wilayah: Optional[str] = None,
    kasus: Optional[str] = None,
    severity_shift: float = 0.0,
) -> "pd.DataFrame":
    """
    Gandakan sebagian pasien sebagai simulasi lonjakan demand.
    spike_pct: 0.0..1.0 -> porsi pasien yang digandakan dari subset terfilter.
    """
    spike_pct = max(0.0, min(1.0, spike_pct))
    base = patients_df.copy()

    subset = base.copy()
    if wilayah is not None:
        subset = subset[subset.get("wilayah").astype(str).str.lower() == str(wilayah).lower()]
    if kasus is not None:
        subset = subset[subset.get("kasus").astype(str).str.lower().str.contains(str(kasus).lower(), na=False)]

    if subset.empty or spike_pct <= 0.0:
        return base

    n_extra = max(1, int(len(subset) * spike_pct))
    # sample with replacement
    extra = subset.sample(n=n_extra, replace=True, random_state=42).copy()

    # adjust severity jika kolom ada
    if "severity" in extra.columns and abs(severity_shift) > 0:
        extra["severity"] = extra["severity"].apply(lambda v: _safe_float(v) + severity_shift)

    # buat id_pasien baru agar unik
    if "id_pasien" in extra.columns:
        extra["id_pasien"] = extra["id_pasien"].astype(str) + "_SPK"

    return pd.concat([base, extra], ignore_index=True)


def summarize_fac_changes(before_fac: List[Dict[str, Any]], after_fac: List[Dict[str, Any]], top_k: int = 5):
    """
    Ringkas perubahan occupancy RS tertinggi.
    """
    bmap = {str(x["hospital_id"]): _safe_float(x.get("occ_ratio")) for x in before_fac}
    rows = []
    for f in after_fac:
        hid = str(f["hospital_id"])
        after = _safe_float(f.get("occ_ratio"))
        before = bmap.get(hid, 0.0)
        rows.append(
            {
                "hospital_id": hid,
                "occ_before": before,
                "occ_after": after,
                "delta_occ": after - before,
            }
        )
    rows.sort(key=lambda r: abs(r["delta_occ"]), reverse=True)
    return rows[:top_k]


def run_scenario(
    scenario: Dict[str, Any],
    facilities_df: "pd.DataFrame",
    patients_df: "pd.DataFrame",
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Jalankan apa-adanya tiga tipe skenario:
      - capacity_drop: {drop_pct, wilayah?, kelas?}
      - policy_change: {radius_km?, max_load?, target_occupancy?}
      - demand_spike : {spike_pct, wilayah?, kasus?, severity_shift?}
    Return: before/after metrics + delta dan ringkasan perubahan RS.
    """
    s_type = str(scenario.get("type", "")).lower()
    params = scenario.get("params", {}) or {}

    # baseline
    base_result = greedy_match(patients_df, facilities_df, config)
    base_metrics = compute_metrics(base_result)

    # clone objek kerja
    new_fac = facilities_df.copy()
    new_pat = patients_df.copy()
    new_cfg = dict(config)

    if s_type == "capacity_drop":
        new_fac = apply_capacity_drop(
            facilities_df=new_fac,
            drop_pct=_safe_float(params.get("drop_pct", 0.0)),
            wilayah=params.get("wilayah"),
            kelas=params.get("kelas"),
        )
    elif s_type == "policy_change":
        new_cfg = apply_policy_change(
            config=new_cfg,
            radius_km=params.get("radius_km"),
            max_load=params.get("max_load"),
            target_occupancy=params.get("target_occupancy"),
        )
    elif s_type == "demand_spike":
        new_pat = apply_demand_spike(
            patients_df=new_pat,
            spike_pct=_safe_float(params.get("spike_pct", 0.0)),
            wilayah=params.get("wilayah"),
            kasus=params.get("kasus"),
            severity_shift=_safe_float(params.get("severity_shift", 0.0)),
        )
    else:
        raise ValueError(f"Tipe skenario tidak dikenali: {s_type}")

    # after
    after_result = greedy_match(new_pat, new_fac, new_cfg)
    after_metrics = compute_metrics(after_result)

    # delta metrics (after - before) untuk angka-angka utama
    keys = [
        "total_patients", "total_assigned", "total_unassigned",
        "avg_distance_km", "unmet_ratio", "load_balance_index",
        "occ_mean", "occ_min", "occ_max", "service_compliance",
    ]
    delta = {k: _safe_float(after_metrics.get(k)) - _safe_float(base_metrics.get(k)) for k in keys}

    # ringkas perubahan occupancy RS terbesar
    top_changes = summarize_fac_changes(
        before_fac=base_result.get("facilities", []) or [],
        after_fac=after_result.get("facilities", []) or [],
        top_k=5,
    )

    return {
        "scenario": {"type": s_type, "params": params},
        "before": base_metrics,
        "after": after_metrics,
        "delta": delta,
        "top_facility_changes": top_changes,
    }
