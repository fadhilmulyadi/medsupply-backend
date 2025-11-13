from typing import List

from pydantic import BaseModel


class Assignment(BaseModel):
    patient_id: str
    hospital_id: str
    distance_km: float
    occ_before: float
    occ_after: float
    cost: float


class MatchSummary(BaseModel):
    total_patients: int
    total_assigned: int
    total_unassigned: int


class MatchResult(BaseModel):
    summary: MatchSummary
    assignments: List[Assignment]
