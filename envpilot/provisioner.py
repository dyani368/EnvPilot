from typing import Protocol

from envpilot.config import settings


class Provisioner(Protocol):
    def provision(self, environment_id: str, template_version: str) -> None: ...
    def inspect(self, environment_id: str) -> bool: ...
    def destroy(self, environment_id: str, template_version: str) -> None: ...


class FakeProvisioner:
    """Deterministic local adapter. No cloud resources are created."""

    def provision(self, environment_id: str, template_version: str) -> None:
        if settings.envpilot_fake_failure == "provision":
            raise RuntimeError("injected provisioning failure")

    def inspect(self, environment_id: str) -> bool:
        return True

    def destroy(self, environment_id: str, template_version: str) -> None:
        if settings.envpilot_fake_failure == "destroy":
            raise RuntimeError("injected cleanup failure")
