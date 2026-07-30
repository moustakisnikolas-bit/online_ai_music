from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.generation_cost import GenerationCost

# Recognized "kind" values. get_cost_summary() groups by this exact
# string, so call sites use these constants rather than retyping the
# literal -- a typo in a hand-typed string would silently create a new
# bucket in the summary instead of erroring.
STABLE_AUDIO_OPEN = "stable_audio_open"
FLUX_REPLICATE = "flux_replicate"
OPENROUTER_IMAGE = "openrouter_image"
OPENROUTER_METADATA = "openrouter_metadata"


def _record(
    db: Session, *, kind: str, cost_usd: float, estimated: bool, reference: str | None
) -> GenerationCost:
    entry = GenerationCost(kind=kind, cost_usd=cost_usd, estimated=estimated, reference=reference)
    db.add(entry)
    db.commit()
    return entry


def record_estimated_cost(
    db: Session, *, kind: str, estimate_usd: float, reference: str | None = None
) -> GenerationCost:
    """Record spend for a provider with no real-time billing in its
    response (e.g. Replicate's prediction API) -- estimate_usd is a
    documented per-call figure from settings, not what was actually
    billed."""
    return _record(db, kind=kind, cost_usd=estimate_usd, estimated=True, reference=reference)


def record_reported_cost(
    db: Session, *, kind: str, reported_usd: float | None, reference: str | None = None
) -> GenerationCost | None:
    """Record spend for a provider that reports its exact cost in the
    response (e.g. OpenRouter) -- no-ops if the provider didn't include a
    cost this time, rather than recording a wrong $0."""
    if reported_usd is None:
        return None

    return _record(db, kind=kind, cost_usd=reported_usd, estimated=False, reference=reference)


def get_cost_summary(db: Session) -> dict:
    rows = db.execute(
        select(
            GenerationCost.kind,
            func.sum(GenerationCost.cost_usd),
            func.count(GenerationCost.id),
        ).group_by(GenerationCost.kind)
    ).all()

    by_kind = {kind: float(total) for kind, total, _count in rows}
    count_by_kind = {kind: int(count) for kind, _total, count in rows}

    return {
        "total_usd": sum(by_kind.values()),
        "by_kind_usd": by_kind,
        "count_by_kind": count_by_kind,
    }
