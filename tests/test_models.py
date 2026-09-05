from app.models.schemas import TestPlan,TestScenario,CoverageAnalysis,TestStep
def test_models():
 p=TestPlan(application_url="http://example.com",application_summary="demo",scenarios=[TestScenario(id="S001",name="Login",flow="login",category="happy_path",expected_outcome="dashboard")]); assert p.scenarios[0].category=="happy_path"
def test_coverage(): assert CoverageAnalysis(score=.75,should_replan=False,reasoning="ok").score==.75
def test_select_step_is_supported(): assert TestStep(action="select",target={"id":"category"},value="outdoor").action=="select"
