from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.generation_costs import get_cost_summary
from app.schemas.generation_cost import GenerationCostSummary

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary", response_model=GenerationCostSummary)
def get_generation_cost_summary(db: Session = Depends(get_db)) -> GenerationCostSummary:
    return GenerationCostSummary(**get_cost_summary(db))
