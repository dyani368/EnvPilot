"""Evidence-first diagnosis of sanitized pipeline excerpts."""

import re
from pathlib import Path

from pydantic import BaseModel, Field


REDACTIONS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)(authorization|token|secret|password)\s*[:=]\s*\S+"), "[REDACTED_CREDENTIAL]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]+"), "[REDACTED_SLACK_TOKEN]"),
]


class Evidence(BaseModel):
    source: str
    line_start: int | None = None
    section: str | None = None


class Diagnosis(BaseModel):
    summary: str
    likely_cause: str
    evidence: list[Evidence] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    confidence: str
    requires_human_review: bool = True


RULES = [
    (re.compile(r"AccessDenied|UnauthorizedOperation|not authorized", re.I), "access-denied", "The deployment identity may lack a required permission."),
    (re.compile(r"Error acquiring the state lock|ConditionalCheckFailedException", re.I), "terraform-state-lock", "Another operation may hold the Terraform state lock."),
    (re.compile(r"InsufficientInstanceCapacity|InstanceLimitExceeded|VcpuLimitExceeded", re.I), "resource-limit", "Capacity or quota may prevent instance creation."),
]


def sanitize(log: str) -> str:
    log = log[:100_000]
    for pattern, replacement in REDACTIONS:
        log = pattern.sub(replacement, log)
    return log


def diagnose(log: str) -> Diagnosis:
    lines = sanitize(log).splitlines()
    for index, line in enumerate(lines, 1):
        for pattern, slug, cause in RULES:
            if pattern.search(line):
                runbook = Path(__file__).resolve().parent.parent / "runbooks" / f"{slug}.md"
                if not runbook.is_file():
                    continue
                return Diagnosis(summary="A known provisioning error was found in the log.", likely_cause=cause,
                                 evidence=[Evidence(source="jenkins-log", line_start=index), Evidence(source=f"runbooks/{slug}.md", section="Verification")],
                                 recommended_steps=["Review the cited log line and runbook.", "Have an authorized operator confirm the cause before retrying."],
                                 confidence="medium")
    return Diagnosis(summary="The available log does not identify a known failure.",
                     likely_cause="Unknown; more evidence is required.",
                     confidence="low", recommended_steps=["Inspect the failed Jenkins stage and collect a sanitized log excerpt."])
