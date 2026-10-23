import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite:///./test_envpilot.db"

from fastapi.testclient import TestClient  # noqa: E402
from envpilot.api import app  # noqa: E402
from envpilot.db import Base, engine  # noqa: E402
from envpilot.worker import process_one  # noqa: E402
from envpilot.config import settings  # noqa: E402


def test_request_approval_provision_destroy():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    client = TestClient(app)
    key = str(uuid4())
    headers = {"X-Actor-Id": "developer", "Idempotency-Key": key}
    body = {"template_id": "ec2_sandbox", "template_version": "v1", "ttl_hours": 2}
    first = client.post("/api/environments", json=body, headers=headers)
    assert first.status_code == 201
    env_id = first.json()["id"]
    assert client.post("/api/environments", json=body, headers=headers).json()["id"] == env_id
    assert client.post(f"/api/environments/{env_id}/approve", headers=headers).status_code == 403
    approver = {"X-Actor-Id": "approver-1"}
    assert client.post(f"/api/environments/{env_id}/approve", headers=approver).json()["status"] == "queued"
    assert process_one()
    assert client.get(f"/api/environments/{env_id}", headers=headers).json()["status"] == "active"
    assert client.post(f"/api/environments/{env_id}/destroy", headers=headers).json()["status"] == "destroy_queued"
    assert process_one()
    assert client.get(f"/api/environments/{env_id}", headers=headers).json()["status"] == "destroyed"
    events = client.get(f"/api/environments/{env_id}/events", headers=headers).json()
    assert [e["event_type"] for e in events] == ["requested", "approved", "queued", "provisioning", "active", "destroy_queued", "destroying", "destroyed"]
    assert client.get(f"/api/environments/{env_id}", headers={"X-Actor-Id": "stranger"}).status_code == 404


def test_invalid_inputs():
    client = TestClient(app)
    headers = {"X-Actor-Id": "developer", "Idempotency-Key": str(uuid4())}
    assert client.post("/api/environments", json={"ttl_hours": 100}, headers=headers).status_code == 422
    assert client.post("/api/environments", json={"ttl_hours": 1, "command": "rm -rf /"}, headers=headers).status_code == 422


def test_provision_failure_is_visible():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    client = TestClient(app)
    headers = {"X-Actor-Id": "developer", "Idempotency-Key": str(uuid4())}
    env_id = client.post("/api/environments", json={"ttl_hours": 1}, headers=headers).json()["id"]
    client.post(f"/api/environments/{env_id}/approve", headers={"X-Actor-Id": "approver-1"})
    settings.envpilot_fake_failure = "provision"
    try:
        assert process_one()
    finally:
        settings.envpilot_fake_failure = "none"
    assert client.get(f"/api/environments/{env_id}", headers=headers).json()["status"] == "provisioning_failed"
    assert client.post(f"/api/environments/{env_id}/destroy", headers=headers).json()["status"] == "destroy_queued"
    assert process_one()
    assert client.get(f"/api/environments/{env_id}", headers=headers).json()["status"] == "destroyed"
