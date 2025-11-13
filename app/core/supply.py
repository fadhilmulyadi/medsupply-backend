import pandas as pd


def compute_occupancy_summary(facilities_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Menambahkan kolom rasio okupansi dan mengembalikan DataFrame yang telah diperbarui.
    """
    df = facilities_df.copy()
    df["occ_ratio"] = df["occupied_tt"] / df["capacity_tt"]
    return df
