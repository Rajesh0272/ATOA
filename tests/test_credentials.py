from types import SimpleNamespace

from app.agents.generator import GeneratorAgent
from app.models.schemas import (
    ApplicationObservation,
    ElementInfo,
    TestCredentials,
    TestPlan,
    TestScenario,
)


def _plan():
    return TestPlan(
        application_url="http://example.test",
        application_summary="Login application",
        scenarios=[
            TestScenario(
                id="S001",
                name="Valid login",
                flow="Submit valid credentials",
                category="happy_path",
                expected_outcome="Logout is visible",
            )
        ],
    )


def test_mock_login_uses_supplied_credentials():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")

    result = generator.generate(
        _plan(),
        credentials=TestCredentials(username="alice", password="secret"),
    )

    assert result.tests[0].steps[1].value == "alice"
    assert result.tests[0].steps[2].value == "secret"
    assert result.tests[0].credentials_available is True


def test_mock_login_uses_observed_submit_button_name():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")
    observation = ApplicationObservation(
        url="http://example.test",
        elements=[
            ElementInfo(tag="input", name="username"),
            ElementInfo(tag="input", name="password"),
            ElementInfo(tag="button", text="Sign In"),
            ElementInfo(tag="button", text="Logout"),
        ],
    )

    result = generator.generate(
        _plan(),
        observation,
        TestCredentials(username="alice", password="secret"),
    )

    click_steps = [step for step in result.tests[0].steps if step.action == "click"]
    assert click_steps[0].target == {"role": "button", "name": "Sign In"}


def test_mock_login_can_force_legacy_rename_failure(monkeypatch):
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")
    monkeypatch.setenv("AIVAR_MOCK_LOGIN_RENAME_FAILURE", "1")
    observation = ApplicationObservation(
        url="http://example.test",
        elements=[
            ElementInfo(tag="input", name="username"),
            ElementInfo(tag="input", name="password"),
            ElementInfo(tag="button", text="Sign In"),
            ElementInfo(tag="button", text="Logout"),
        ],
    )

    result = generator.generate(
        _plan(),
        observation,
        TestCredentials(username="alice", password="secret"),
    )

    click_steps = [step for step in result.tests[0].steps if step.action == "click"]
    assert click_steps[0].target == {"role": "button", "name": "Login"}


def test_login_without_credentials_is_marked_blocked():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")

    result = generator.generate(_plan())

    assert result.tests[0].credentials_available is False
    assert result.tests[0].requires_credentials is True


def test_generated_test_gets_navigation_when_model_omits_it():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="sarvam")
    generator.llm.json_call = lambda **_: {
        "tests": [
            {
                "id": "TC-S001",
                "scenario_id": "S001",
                "name": "Search",
                "steps": [
                    {
                        "action": "fill",
                        "target": {"id": "search"},
                        "value": "mug",
                    }
                ],
            }
        ]
    }

    result = generator.generate(_plan())

    assert result.tests[0].steps[0].action == "navigate"
    assert result.tests[0].steps[0].value == "http://example.test"


def test_logout_scenario_requires_credentials():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")
    plan = _plan().model_copy(update={
        "scenarios": [
            TestScenario(
                id="S004",
                name="Logout",
                flow="Login then logout",
                category="happy_path",
                expected_outcome="Login page is visible",
            )
        ]
    })

    result = generator.generate(plan)

    assert result.tests[0].requires_credentials is True
    assert result.tests[0].credentials_available is False


def test_logout_scenario_gets_login_prerequisite():
    generator = GeneratorAgent.__new__(GeneratorAgent)
    generator.llm = SimpleNamespace(provider="mock")
    plan = _plan().model_copy(update={
        "scenarios": [
            TestScenario(
                id="S004",
                name="Logout",
                flow="Login then logout",
                category="happy_path",
                expected_outcome="Login page is visible",
            )
        ]
    })
    observation = ApplicationObservation(
        url=plan.application_url,
        elements=[
            ElementInfo(tag="input", name="username"),
            ElementInfo(tag="input", name="password"),
            ElementInfo(tag="button", text="Sign In"),
            ElementInfo(tag="button", text="Logout"),
        ],
    )

    result = generator.generate(
        plan,
        observation,
        TestCredentials(username="alice", password="secret"),
    )

    actions = [step.action for step in result.tests[0].steps]
    assert actions[:4] == ["navigate", "fill", "fill", "click"]
    assert result.tests[0].steps[3].target == {"role": "button", "name": "Sign In"}
