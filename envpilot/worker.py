import time

from sqlalchemy import select

from envpilot.db import SessionLocal
from envpilot.models import Environment, Job, PipelineRun, now
from envpilot.provisioner import FakeProvisioner, Provisioner
from envpilot.workflow import transition


def process_one(provisioner: Provisioner | None = None) -> bool:
    provider = provisioner or FakeProvisioner()
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.status == "queued", Job.next_attempt_at <= now()).order_by(Job.next_attempt_at).with_for_update(skip_locked=True))
        if job is None:
            return False
        env = db.get(Environment, job.environment_id)
        job.status = "running"
        job.attempts += 1
        transition(db, env, "provisioning" if job.action == "provision" else "destroying", "worker")
        run = PipelineRun(environment_id=env.id, action=job.action, status="running")
        db.add(run)
        db.commit()
        try:
            if job.action == "provision":
                provider.provision(env.id, env.template_version)
                if not provider.inspect(env.id):
                    raise RuntimeError("provisioned environment failed inspection")
                target = "active"
            else:
                provider.destroy(env.id, env.template_version)
                target = "destroyed"
            job.status = "succeeded"
            run.status = "succeeded"
        except Exception as exc:
            target = "provisioning_failed" if job.action == "provision" else "cleanup_failed"
            job.status = "failed"
            run.status = "failed"
            # Exception text may include credentials. Store only the exception class.
            transition(db, env, target, "worker", {"error_type": type(exc).__name__})
        else:
            transition(db, env, target, "worker")
        run.finished_at = now()
        db.commit()
        return True


def enqueue_expired() -> int:
    from envpilot.workflow import enqueue

    with SessionLocal() as db:
        expired = db.scalars(select(Environment).where(
            Environment.status == "active", Environment.expires_at <= now()
        ).with_for_update(skip_locked=True)).all()
        for env in expired:
            transition(db, env, "destroy_queued", "expiry-worker")
            enqueue(db, env, "destroy")
        db.commit()
        return len(expired)


def main():
    while True:
        enqueue_expired()
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
