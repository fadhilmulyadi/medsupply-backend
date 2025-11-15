from pathlib import Path
from typing import Tuple
import pandas as pd
from app.core.validate import validate_facilities_df, validate_patients_df

def load_data() -> Tuple["pd.DataFrame", "pd.DataFrame"]:
    data_dir = Path("data")
    facilities_path = data_dir / "facilities.csv"
    patients_path = data_dir / "patients_batch.csv"

    if not facilities_path.exists():
        raise FileNotFoundError(f"facilities.csv not found at {facilities_path.resolve()}")
    if not patients_path.exists():
        raise FileNotFoundError(f"patients_batch.csv not found at {patients_path.resolve()}")

    facilities_df = pd.read_csv(facilities_path)
    patients_df = pd.read_csv(patients_path)

    validate_facilities_df(facilities_df)
    validate_patients_df(patients_df)

    return facilities_df, patients_df
