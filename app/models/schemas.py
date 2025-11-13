from typing import List, Optional

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

class Metrics(BaseModel):
    total_patients: int
    total_assigned: int
    total_unassigned: int
    avg_distance_km: float
    unmet_ratio: float
    load_balance_index: float
    occ_mean: float
    occ_min: float
    occ_max: float
    service_compliance: float

class AlternativeSuggestion(BaseModel):
    hospital_id: str
    distance_km: float
    occ_ratio: float
    cost: float

class Explanation(BaseModel):
    patient_id: str
    hospital_id: str
    narrative: str
    alternative: Optional[AlternativeSuggestion] = None

class ExplainResult(BaseModel):
    count: int
    items: List[Explanation]