from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.concept_research import ConceptResearch


def get_concept_research(db: Session, concept_id: str) -> ConceptResearch | None:
    return db.scalars(
        select(ConceptResearch).where(ConceptResearch.concept_id == concept_id)
    ).first()


def list_concept_research(db: Session) -> list[ConceptResearch]:
    return list(db.scalars(select(ConceptResearch)))


def upsert_concept_research(
    db: Session,
    *,
    concept_id: str,
    query: str,
    sample_size: int,
    top_hz_values: list,
    top_noise_types: list,
    top_themes: list,
    top_duration_buckets: list,
    top_videos: list,
) -> ConceptResearch:
    record = get_concept_research(db, concept_id)

    if record is None:
        record = ConceptResearch(concept_id=concept_id)
        db.add(record)

    record.query = query
    record.sample_size = sample_size
    record.top_hz_values = top_hz_values
    record.top_noise_types = top_noise_types
    record.top_themes = top_themes
    record.top_duration_buckets = top_duration_buckets
    record.top_videos = top_videos

    db.commit()
    db.refresh(record)
    return record
