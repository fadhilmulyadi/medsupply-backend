from fastapi import APIRouter, Depends, Request
from app.core.data_access import load_data_for_matching
from app.core.matching import run_match
from app.core.matching import run_match
from app.core.metrics import compute_metrics
from app.models.schemas import Metrics
from app.core.security import require_api_key
from app.core.state import state, compute_data_signature
from app.core.audit import log_event

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(require_api_key)])

@router.get("", response_model=Metrics)
async def get_metrics(request: Request):
    if state.is_valid_for_current_data() and state.get_last_run():
        last = state.get_last_run()
        result = last.result
        metrics = compute_metrics(result)
        log_event("metrics_cached", {"summary": result.get("summary", {})}, request_id=getattr(request.state, "request_id", None), run_id=last.run_id)
        return metrics

    facilities_df, patients_df, config = load_data_for_matching()
    result = run_match(patients_df=patients_df, facilities_df=facilities_df, config=config)

    sig = compute_data_signature()
    run = state.set_last_run(config=config, result=result, data_signature=sig)
    metrics = compute_metrics(result)
    log_event("metrics_fresh", {"summary": result.get("summary", {})}, request_id=getattr(request.state, "request_id", None), run_id=run.run_id)
    return metrics
