from fastapi import APIRouter

from app.core.load import load_data
from app.core.supply import compute_occupancy_summary

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("")
async def list_facilities():
    """
    Return all facilities with basic occupancy info.
    """
    facilities_df, _ = load_data()
    facilities_with_occ = compute_occupancy_summary(facilities_df)

    return {
        "count": len(facilities_with_occ),
        "items": facilities_with_occ.to_dict(orient="records"),
    }
