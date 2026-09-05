from types import SimpleNamespace

from app.agents.failure_analyzer import FailureAnalyzer


def test_strict_mode_failure_is_not_classified_as_locator_healing():
    analyzer = FailureAnalyzer.__new__(FailureAnalyzer)
    analyzer.llm = SimpleNamespace(provider="sarvam")

    diagnosis = analyzer.diagnose(
        {
            "test_id": "TC-S001",
            "error": 'strict mode violation: get_by_role("heading") resolved to 2 elements',
            "failed_step": {
                "action": "assert_visible",
                "target": {"role": "heading"},
            },
        }
    )

    assert diagnosis.failure_type == "UNKNOWN"
    assert diagnosis.healing_candidate is None
    assert diagnosis.safe_to_heal is False
