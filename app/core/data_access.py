# app/core/data_access.py
from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import date
from typing import Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import engine

load_dotenv()

CONFIG_PATH = os.getenv("CONFIG_PATH", "data/config.json")


# =========================
# CONFIG LOADER
# =========================

def load_config() -> dict:
    """
    Membaca file config JSON yang berisi:
      - solver
      - weights
      - constraints
      - policy
      - forecast, dll.

    Kalau file tidak ada → lempar error yang jelas.
    """
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file tidak ditemukan di {path.resolve()}. "
            f"Set CONFIG_PATH di .env jika lokasinya berbeda."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# FACILITIES LOADER
# =========================

def load_facilities_df(
    db_engine: Optional[Engine] = None,
    wilayah: Optional[str] = None,
) -> pd.DataFrame:
    """
    Mengambil data fasilitas dari tabel public.facilities (Supabase)
    dan mengembalikan pandas DataFrame.

    Kolom:
      - id_rs
      - name
      - lat, lon
      - capacity_tt, occupied_tt
      - available_tt (capacity_tt - occupied_tt)
      - services (array text)
      - wilayah
    """
    if db_engine is None:
        db_engine = engine

    base_query = """
        SELECT
            id_rs,
            name,
            lat,
            lon,
            capacity_tt,
            occupied_tt,
            (capacity_tt - occupied_tt) AS available_tt,
            services,
            wilayah
        FROM public.facilities
    """

    conditions = []
    params: dict = {}

    if wilayah:
        conditions.append("wilayah = :wilayah")
        params["wilayah"] = wilayah

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY id_rs"  # stabil

    df = pd.read_sql(text(base_query), db_engine, params=params)

    # Pastikan tipe numeric yang konsisten
    numeric_cols = ["capacity_tt", "occupied_tt", "available_tt", "lat", "lon"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# =========================
# PATIENTS LOADER
# =========================

def load_patients_df(
    db_engine: Optional[Engine] = None,
    visit_date: Optional[date] = None,
    service_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    Mengambil data pasien dari tabel public.patients
    dan mengembalikan pandas DataFrame.
    """
    if db_engine is None:
        db_engine = engine

    base_query = """
        SELECT
            patient_code AS id_pasien,
            visit_date,
            full_name,
            gender,
            age_years,
            severity,
            service_type AS kasus,
            lat,
            lon
        FROM public.patients
    """

    conditions = []
    params: dict = {}

    if visit_date:
        conditions.append("visit_date = :visit_date")
        params["visit_date"] = visit_date

    if service_type:
        conditions.append("service_type = :service_type")
        params["service_type"] = service_type

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY severity DESC, patient_code"

    df = pd.read_sql(text(base_query), db_engine, params=params)

    # Tipe numeric
    numeric_cols = ["age_years", "severity", "lat", "lon"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# =========================
# MAIN LOADER UNTUK MATCHING
# =========================

def load_data_for_matching(
    db_engine: Optional[Engine] = None,
    wilayah: Optional[str] = None,
    visit_date: Optional[date] = None,
    service_type: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Loader utama yang bisa kamu panggil dari core.matching / endpoints.

    Return:
      facilities_df, patients_df, config_dict

    Param:
      - wilayah: filter fasilitas berdasarkan wilayah (opsional)
      - visit_date: ambil pasien untuk tanggal tertentu (opsional, default: semua)
      - service_type: filter pasien per layanan (opsional)
    """
    if db_engine is None:
        db_engine = engine

    config = load_config()
    facilities_df = load_facilities_df(db_engine=db_engine, wilayah=wilayah)
    patients_df = load_patients_df(
        db_engine=db_engine,
        visit_date=visit_date,
        service_type=service_type,
    )

    return facilities_df, patients_df, config
