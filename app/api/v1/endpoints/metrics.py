from fastapi import APIRouter

from app.core.load import load_data
from app.core.config import load_config
from app.core.matching import greedy_match
from app.core.metrics import compute_metrics
from app.models.schemas import Metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=Metrics)
async def get_metrics():
    """
    Hitung KPI dari hasil matching.
    """
    facilities_df, patients_df = load_data()
    config = load_config()

    result = greedy_match(
        patients_df=patients_df,
        facilities_df=facilities_df,
        config=config,
    )

    metrics = compute_metrics(result)
    return metrics
