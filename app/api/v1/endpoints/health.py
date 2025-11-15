# app/api/v1/endpoints/health.py
from datetime import datetime

from fastapi import APIRouter

from app.core.data_access import load_facilities_df

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """
    Health check API:
    - pastikan service hidup
    - cek koneksi ke database
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    try:
        facilities_df = load_facilities_df()
        return {
            "status": "ok",
            "timestamp": timestamp,
            "facilities_rows": int(facilities_df.shape[0]),
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": timestamp,
            "message": str(e),
        }
