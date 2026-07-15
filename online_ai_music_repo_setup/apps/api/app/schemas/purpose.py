from pydantic import BaseModel


class PurposeProfileResponse(BaseModel):
    id: str
    label: str
    description: str
    recommended_duration_seconds: int
    target_lufs: float
    true_peak_dbtp: float
    energy_start: float
    energy_middle: float
    energy_end: float
    suggested_mode: str
    notes: str
