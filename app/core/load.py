from pathlib import Path
from typing import Tuple

import pandas as pd


def load_data() -> Tuple["pd.DataFrame", "pd.DataFrame"]:
    """
    Memuat data fasilitas dan data batch pasien ke dalam DataFrame pandas.
    """

    data_dir = Path("data")
    facilities_path = data_dir / "facilities.csv"
    patients_path = data_dir / "patients_batch.csv"

    if not facilities_path.exists():
        raise FileNotFoundError(f"facilities.csv not found at {facilities_path.resolve()}")
    if not patients_path.exists():
        raise FileNotFoundError(f"patients_batch.csv not found at {patients_path.resolve()}")

    facilities_df = pd.read_csv(facilities_path)
    patients_df = pd.read_csv(patients_path)

    required_fac_cols = {"id_rs", "lat", "lon", "capacity_tt", "occupied_tt"}
    missing_fac = required_fac_cols - set(facilities_df.columns)
    if missing_fac:
        raise ValueError(f"facilities.csv missing required columns: {missing_fac}")

    required_pat_cols = {"id_pasien", "lat", "lon"}
    missing_pat = required_pat_cols - set(patients_df.columns)
    if missing_pat:
        raise ValueError(f"patients_batch.csv missing required columns: {missing_pat}")

    return facilities_df, patients_df
