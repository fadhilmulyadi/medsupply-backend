from typing import List
import pandas as pd

class ValidationError(Exception):
    pass

def _ensure_columns(df: "pd.DataFrame", required: List[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError(f"{name} missing required columns: {missing}")

def validate_facilities_df(df: "pd.DataFrame") -> None:
    _ensure_columns(df, ["id_rs", "lat", "lon", "capacity_tt", "occupied_tt"], "facilities")
    errors = []
    if (df["capacity_tt"] <= 0).any(): errors.append("capacity_tt must be > 0")
    if (df["occupied_tt"] < 0).any(): errors.append("occupied_tt must be >= 0")
    if (df["occupied_tt"] > df["capacity_tt"]).any(): errors.append("occupied_tt cannot exceed capacity_tt")
    if ((df["lat"] < -90) | (df["lat"] > 90)).any(): errors.append("lat must be in [-90, 90]")
    if ((df["lon"] < -180) | (df["lon"] > 180)).any(): errors.append("lon must be in [-180, 180]")
    if errors: raise ValidationError("; ".join(errors))

def validate_patients_df(df: "pd.DataFrame") -> None:
    _ensure_columns(df, ["id_pasien", "lat", "lon"], "patients")
    errors = []
    if ((df["lat"] < -90) | (df["lat"] > 90)).any(): errors.append("lat must be in [-90, 90]")
    if ((df["lon"] < -180) | (df["lon"] > 180)).any(): errors.append("lon must be in [-180, 180]")
    if errors: raise ValidationError("; ".join(errors))
