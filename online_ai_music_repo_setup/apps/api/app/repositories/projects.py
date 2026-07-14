from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(
        name=payload.name,
        slug=payload.slug,
        status="draft",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
