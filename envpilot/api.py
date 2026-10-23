from datetime import datetime
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from envpilot.config import settings
from envpilot.db import get_session
from envpilot.models import Environment, Event
from envpilot.workflow import enqueue, transition

app = FastAPI(title="EnvPilot", version="0.1.0")


class RequestIn(BaseModel):
    template_id: str = "ec2_sandbox"
    template_version: str = "v1"
    ttl_hours: int = Field(ge=1)
    model_config = ConfigDict(extra="forbid")


class EnvironmentOut(BaseModel):
    id: str
    requester_id: str
    template_id: str
    template_version: str
    ttl_hours: int
    status: str
    expires_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


def actor(x_actor_id: str = Header(...)) -> str:
    if not x_actor_id.strip() or len(x_actor_id) > 128:
        raise HTTPException(401, detail={"code": "invalid_actor"})
    return x_actor_id


def visible(env: Environment | None, user: str) -> Environment:
    if env is None or (env.requester_id != user and user not in settings.envpilot_approver_ids.split(",")):
        raise HTTPException(404, detail={"code": "not_found"})
    return env


def get_env(db: Session, env_id: UUID, user: str) -> Environment:
    return visible(db.get(Environment, str(env_id)), user)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/environments", response_model=EnvironmentOut, status_code=201)
def create_environment(body: RequestIn, idempotency_key: str = Header(..., alias="Idempotency-Key"),
                       user: str = Depends(actor), db: Session = Depends(get_session)):
    if body.template_id != "ec2_sandbox" or body.template_version != "v1":
        raise HTTPException(422, detail={"code": "unsupported_template"})
    if body.ttl_hours > settings.envpilot_max_ttl_hours:
        raise HTTPException(422, detail={"code": "ttl_exceeds_limit"})
    if not 1 <= len(idempotency_key) <= 128:
        raise HTTPException(422, detail={"code": "invalid_idempotency_key"})
    existing = db.scalar(select(Environment).where(Environment.idempotency_key == idempotency_key))
    if existing:
        if (existing.requester_id, existing.template_id, existing.template_version, existing.ttl_hours) != (user, body.template_id, body.template_version, body.ttl_hours):
            raise HTTPException(409, detail={"code": "idempotency_conflict"})
        return existing
    env = Environment(requester_id=user, idempotency_key=idempotency_key,
                      template_id=body.template_id, template_version=body.template_version,
                      ttl_hours=body.ttl_hours)
    db.add(env)
    db.flush()
    db.add(Event(environment_id=env.id, event_type="requested", actor_id=user, details={}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "idempotency_conflict"}) from None
    return env


@app.get("/api/environments", response_model=list[EnvironmentOut])
def list_environments(user: str = Depends(actor), db: Session = Depends(get_session)):
    query = select(Environment).order_by(Environment.created_at.desc())
    if user not in settings.envpilot_approver_ids.split(","):
        query = query.where(Environment.requester_id == user)
    return db.scalars(query).all()


@app.get("/api/environments/{env_id}", response_model=EnvironmentOut)
def read_environment(env_id: UUID, user: str = Depends(actor), db: Session = Depends(get_session)):
    return get_env(db, env_id, user)


@app.get("/api/environments/{env_id}/events")
def read_events(env_id: UUID, user: str = Depends(actor), db: Session = Depends(get_session)):
    env = get_env(db, env_id, user)
    events = db.scalars(select(Event).where(Event.environment_id == env.id).order_by(Event.created_at, Event.id)).all()
    return [{"event_type": e.event_type, "actor_id": e.actor_id, "details": e.details,
             "created_at": e.created_at} for e in events]


@app.post("/api/environments/{env_id}/approve", response_model=EnvironmentOut)
def approve(env_id: UUID, user: str = Depends(actor), db: Session = Depends(get_session)):
    env = get_env(db, env_id, user)
    if user == env.requester_id or user not in settings.envpilot_approver_ids.split(","):
        raise HTTPException(403, detail={"code": "not_approver"})
    transition(db, env, "approved", user)
    transition(db, env, "queued", "system")
    enqueue(db, env, "provision")
    db.commit()
    return env


@app.post("/api/environments/{env_id}/reject", response_model=EnvironmentOut)
def reject(env_id: UUID, user: str = Depends(actor), db: Session = Depends(get_session)):
    env = get_env(db, env_id, user)
    if user == env.requester_id or user not in settings.envpilot_approver_ids.split(","):
        raise HTTPException(403, detail={"code": "not_approver"})
    transition(db, env, "rejected", user)
    db.commit()
    return env


@app.post("/api/environments/{env_id}/destroy", response_model=EnvironmentOut)
def destroy(env_id: UUID, user: str = Depends(actor), db: Session = Depends(get_session)):
    env = get_env(db, env_id, user)
    if env.status == "destroy_queued":
        return env
    transition(db, env, "destroy_queued", user)
    enqueue(db, env, "destroy")
    db.commit()
    return env
