# app/api/v1/endpoints/facilities.py
from typing import List, Optional, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.data_access import load_facilities_df

router = APIRouter(tags=["facilities"])


class Facility(BaseModel):
    id_rs: str
    name: Optional[str]
    lat: float
    lon: float
    capacity_tt: int
    occupied_tt: int
    available_tt: int
    services: List[str]
    wilayah: str


@router.get("/facilities", response_model=list[Facility])
def list_facilities(
    wilayah: Optional[str] = Query(
        None,
        description="Filter berdasarkan wilayah, misal: Makassar",
    ),
    service_type: Optional[str] = Query(
        None,
        description="Filter RS yang punya layanan tertentu, misal: UGD, ICU",
    ),
) -> Any:
    """
    Ambil daftar fasilitas dari database.
    - Bisa difilter berdasarkan wilayah
    - Bisa difilter berdasarkan jenis layanan (service_type)
    """
    df = load_facilities_df(wilayah=wilayah)

    # Filter berdasarkan service_type di sisi Python (karena kolomnya array)
    if service_type:
        df = df[df["services"].apply(lambda s: service_type in s if s is not None else False)]

    records = df.to_dict(orient="records")
    return records
