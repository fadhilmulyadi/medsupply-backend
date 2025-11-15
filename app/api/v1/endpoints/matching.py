from datetime import date
from typing import Optional, Any

from fastapi import APIRouter, Depends, Response, Request
from pydantic import BaseModel

from app.core.data_access import load_data_for_matching
from app.core.matching import run_match
from app.models.schemas import MatchResult
from app.core.security import require_api_key
from app.core.state import state, compute_data_signature
from app.core.audit import log_event

router = APIRouter(
    prefix="/match",
    tags=["matching"],
    dependencies=[Depends(require_api_key)],
)


class MatchRequest(BaseModel):
    """
    Filter opsional untuk proses matching.
    Kalau semua None, berarti pakai default loader
    (misal: semua pasien hari ini / semua data yang diset di load_data_for_matching).
    """
    wilayah: Optional[str] = None
    visit_date: Optional[date] = None
    service_type: Optional[str] = None


@router.post("", response_model=MatchResult)
async def run_matching(
    response: Response,
    request: Request,
    body: MatchRequest | None = None,
):
    """
    Jalankan matching pasien → rumah sakit.
    - Terproteksi API key (require_api_key).
    - Menggunakan data dari PostgreSQL (via load_data_for_matching).
    - Menyimpan state last_run + log audit.
    """
    body = body or MatchRequest()

    facilities_df, patients_df, config = load_data_for_matching(
        wilayah=body.wilayah,
        visit_date=body.visit_date,
        service_type=body.service_type,
    )

    result = run_match(
        patients_df=patients_df,
        facilities_df=facilities_df,
        config=config,
    )

    sig = compute_data_signature()
    run = state.set_last_run(
        config=config,
        result=result,
        data_signature=sig,
    )

    req_id = getattr(request.state, "request_id", None)
    log_event(
        "match_run",
        {
            "summary": result.get("summary", {}),
            "data_signature": sig,
            "filters": {
                "wilayah": body.wilayah,
                "visit_date": body.visit_date.isoformat() if body.visit_date else None,
                "service_type": body.service_type,
            },
        },
        request_id=req_id,
        run_id=run.run_id,
    )

    # 5) Tambahkan header Run ID
    response.headers["X-Run-ID"] = run.run_id

    return result
