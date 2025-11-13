from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.load import load_data
from app.core.config import load_config
from app.core.matching import greedy_match
from app.core.explain import build_explanation_for_patient
from app.models.schemas import ExplainResult, Explanation

router = APIRouter(prefix="/explain", tags=["explain"])

class ExplainRequest(BaseModel):
    patient_id: Optional[str] = None
    lang: str = "id"
    limit: int = 10

@router.post("", response_model=ExplainResult)
async def explain(req: ExplainRequest):
    """
    Buat penjelasan naratif untuk hasil alokasi pasien.
    - Jika patient_id diberikan → 1 penjelasan untuk pasien tsb.
    - Jika tidak → kembalikan sampai 'limit' penjelasan untuk pasien yang ter-assign.
    """
    facilities_df, patients_df = load_data()
    config = load_config()
    result = greedy_match(patients_df, facilities_df, config)

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
        item_dict = build_explanation_for_patient(prow, match, facilities_df, config, lang=req.lang)
        items.append(Explanation(**item_dict))
    else:
        for a in assignments[: max(1, int(req.limit))]:
            prow = get_patient_row(str(a["patient_id"]))
            if prow is None:
                continue
            item_dict = build_explanation_for_patient(prow, a, facilities_df, config, lang=req.lang)
            items.append(Explanation(**item_dict))

    return ExplainResult(count=len(items), items=items)
