from fastapi import FastAPI

from app.core.load import load_data
from app.core.config import load_config
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.facilities import router as facilities_router
from app.api.v1.endpoints.matching import router as matching_router

app = FastAPI(
    title="MedSupply AI Backend",
    version="1.0.0",
    description="Backend service for hospital-patient matching and demand optimization.",
)

facilities_df, patients_df = load_data()
config = load_config()

app.include_router(health_router, prefix="/api/v1")
app.include_router(facilities_router, prefix="/api/v1")
app.include_router(matching_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "ok", "message": "MedSupply AI Backend is running"}
