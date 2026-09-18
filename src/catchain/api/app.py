"""FastAPI application factory for review queue and decision operations."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import Engine

from catchain.api.auth import ActorRole, require_actor
from catchain.domain.review import ReviewRequest
from catchain.review_queue import build_review_queue
from catchain.storage import create_schema, create_sqlite_engine
from catchain.storage.review_repository import ReviewBlocked, decide


def create_app(engine: Engine | None = None, *, database: Path | None = None) -> FastAPI:
    """Create an API bound to one database; production passes a PostgreSQL engine."""

    if engine is None:
        if database is None:
            raise ValueError("engine or database is required")
        engine = create_sqlite_engine(database)
        create_schema(engine)
    app = FastAPI(title="CATchain Review API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/review/queue")
    def review_queue(
        project_id: str | None = Query(default=None),
        field_name: str | None = Query(default=None),
        limit: int | None = Query(default=None, ge=1),
        actor: tuple[str, ActorRole] = Depends(require_actor),
    ) -> dict:
        del actor
        try:
            snapshot = build_review_queue(
                engine, project_id=project_id, field_name=field_name, limit=limit
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
            ) from error
        return snapshot.model_dump(mode="json")

    @app.post("/review/decisions", status_code=status.HTTP_201_CREATED)
    def review_decision(
        request: ReviewRequest,
        actor: tuple[str, ActorRole] = Depends(require_actor),
    ) -> dict:
        actor_id, role = actor
        if request.reviewer != actor_id:
            raise HTTPException(status_code=403, detail="reviewer must match actor")
        if request.status == "approved" and role not in {ActorRole.LEAD, ActorRole.ADMIN}:
            raise HTTPException(status_code=403, detail="lead or admin required for approval")
        try:
            return decide(engine, request)
        except ReviewBlocked as error:
            raise HTTPException(status_code=409, detail={"codes": error.codes}) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return app

