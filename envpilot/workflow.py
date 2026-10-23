from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from envpilot.models import Environment, Event, Job, now


TRANSITIONS = {
    "pending_approval": {"approved", "rejected"},
    "approved": {"queued"},
    "queued": {"provisioning"},
    "provisioning": {"active", "provisioning_failed"},
    "provisioning_failed": {"destroy_queued"},
    "active": {"destroy_queued"},
    "destroy_queued": {"destroying"},
    "destroying": {"destroyed", "cleanup_failed"},
}


def transition(db: Session, env: Environment, target: str, actor: str, details: dict | None = None):
    if target not in TRANSITIONS.get(env.status, set()):
        raise HTTPException(409, detail={"code": "invalid_transition", "state": env.status})
    previous = env.status
    env.status = target
    if target == "active":
        env.expires_at = now() + timedelta(hours=env.ttl_hours)
    db.add(Event(environment_id=env.id, event_type=target, actor_id=actor,
                 details={"from": previous, **(details or {})}))


def enqueue(db: Session, env: Environment, action: str):
    job = Job(environment_id=env.id, action=action)
    db.add(job)
    return job
