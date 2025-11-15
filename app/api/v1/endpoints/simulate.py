from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_api_key
from app.core.data_access import load_data_for_matching
from app.core.matching import run_match
from app.core.simulate import run_scenario

router = APIRouter(prefix="/simulate", tags=["simulate"], dependencies=[Depends(require_api_key)])


class SimulationRequest(BaseModel):
    type: str
    params: Dict[str, Any] = {}


@router.post("", summary="Run scenario simulation")
async def simulate(req: SimulationRequest):
    try:
        facilities_df, patients_df, config = load_data_for_matching()
        result = run_scenario(
            scenario=req.dict(),
            facilities_df=facilities_df,
            patients_df=patients_df,
            config=config,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")
