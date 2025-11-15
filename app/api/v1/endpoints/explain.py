from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from app.core.data_access import load_data_for_matching
from app.core.matching import run_match
from app.core.matching import run_match
from app.core.explain import build_explanation_for_patient
from app.models.schemas import ExplainResult, Explanation
from app.core.security import require_api_key
from app.core.state import state
from app.core.audit import log_event

router = APIRouter(prefix="/explain", tags=["explain"], dependencies=[Depends(require_api_key)])

class ExplainRequest(BaseModel):
    patient_id: Optional[str] = None
    lang: str = "id"
    limit: int = 10

@router.post("", response_model=ExplainResult)
async def explain(req: ExplainRequest, request: Request):
    last = state.get_last_run()
    if last and state.is_valid_for_current_data():
        result = last.result
        facilities_df, patients_df = load_data_for_matching()
        run_id = last.run_id
        cached = True
    else:
        facilities_df, patients_df, config = load_data_for_matching()
        result = run_match(patients_df, facilities_df, config)
        run = state.set_last_run(config=config, result=result)
        run_id = run.run_id
        cached = False

    assignments: List[Dict[str, Any]] = result.get("assignments", []) or []
    if not assignments:
        return ExplainResult(count=0, items=[])

    def get_patient_row(pid: str):
        rows = patients_df[patients_df["id_pasien"].astype(str) == str(pid)]
        return None if rows.empty else rows.iloc[0]

    items: List[Explanation] = []
    if req.patient_id:
        match = next((a for a in assignments if str(a["patient_id"]) == str(req.patient_id)), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"patient_id {req.patient_id} tidak ditemukan pada hasil matching")
        prow = get_patient_row(str(req.patient_id))
        if prow is None:
            raise HTTPException(status_code=404, detail=f"Data pasien {req.patient_id} tidak ditemukan di patients_batch.csv")
        item_dict = build_explanation_for_patient(prow, match, facilities_df, config=state.get_last_run().config if state.get_last_run() else {}, lang=req.lang)
        items.append(Explanation(**item_dict))
    else:
        for a in assignments[: max(1, int(req.limit))]:
            prow = get_patient_row(str(a["patient_id"]))
            if prow is None:
                continue
            item_dict = build_explanation_for_patient(prow, a, facilities_df, config=state.get_last_run().config if state.get_last_run() else {}, lang=req.lang)
            items.append(Explanation(**item_dict))

    log_event("explain", {"count": len(items), "cached": cached}, request_id=getattr(request.state, "request_id", None), run_id=run_id)
    return ExplainResult(count=len(items), items=items)
