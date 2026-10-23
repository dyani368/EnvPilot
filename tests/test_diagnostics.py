from envpilot.diagnostics import diagnose, sanitize


def test_supported_error_has_real_evidence():
    result = diagnose("starting\nError: AccessDenied for ec2:RunInstances")
    assert result.confidence == "medium"
    assert result.evidence[0].line_start == 2
    assert result.evidence[1].source == "runbooks/access-denied.md"


def test_unknown_error_abstains_and_redacts():
    assert diagnose("mysterious failure").confidence == "low"
    assert "AKIAABCDEFGHIJKLMNOP" not in sanitize("AKIAABCDEFGHIJKLMNOP")
