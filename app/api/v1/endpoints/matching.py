from fastapi import APIRouter

from app.core.load import load_data
from app.core.config import load_config
from app.core.matching import greedy_match
from app.models.schemas import MatchResult

router = APIRouter(prefix="/match", tags=["matching"])


@router.post("", response_model=MatchResult)
async def run_matching():
    """
    Jalankan greedy matching untuk batch pasien dan fasilitas.
    Menggunakan konfigurasi default dari data/config.json.
    """
    facilities_df, patients_df = load_data()
    config = load_config()

    result = greedy_match(
        patients_df=patients_df,
        facilities_df=facilities_df,
        config=config,
    )
    # result sudah dict dengan key: summary, assignments
    return result
