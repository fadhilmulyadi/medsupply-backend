import os
import uuid
from datetime import date

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.validate import ValidationError
from app.core.data_access import load_data_for_matching

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.facilities import router as facilities_router
from app.api.v1.endpoints.matching import router as matching_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.simulate import router as simulate_router
from app.api.v1.endpoints.explain import router as explain_router

app = FastAPI(
    title="MedSupply AI Backend",
    version="1.0.0",
    description="Backend service for hospital-patient matching and demand optimization.",
)

# =====================================================
#  ROUTERS
# =====================================================

app.include_router(health_router, prefix="/api/v1")
app.include_router(facilities_router, prefix="/api/v1")
app.include_router(matching_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(simulate_router, prefix="/api/v1")
app.include_router(explain_router, prefix="/api/v1")

# =====================================================
#  CORS
# =====================================================

origins = [o for o in os.getenv("ALLOW_ORIGINS", "*").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
#  MIDDLEWARE: REQUEST ID
# =====================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# =====================================================
#  ERROR HANDLER
# =====================================================

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})

# =====================================================
#  ROOT
# =====================================================

@app.get("/")
async def root():
    return {"status": "ok", "message": "MedSupply AI Backend is running"}

# =====================================================
#  DEBUG: CEK KONEKSI DB + CONFIG
# =====================================================

@app.get("/api/v1/debug/db")
async def debug_db():
    """
    Endpoint debug untuk memastikan:
      - koneksi ke PostgreSQL lokal OK
      - data facilities & patients bisa di-load
      - config.json terbaca
    """
    try:
        facilities_df, patients_df, config = load_data_for_matching(
        )

        return {
            "status": "ok",
            "facilities_rows": int(facilities_df.shape[0]),
            "patients_rows": int(patients_df.shape[0]),
            "config_keys": list(config.keys()),
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": str(e),
            },
        )
