from app.agents.planner import PlannerAgent
from app.agents.coverage import CoverageAgent
from app.agents.generator import GeneratorAgent
from app.browser.explorer import BrowserExplorer
from app.browser.executor import TestExecutor
from app.config import settings
from app.models.schemas import QualityReport,TestCredentials,TestScenario
class AIVAROrchestrator:
    def __init__(self): self.explorer=BrowserExplorer(); self.planner=PlannerAgent(); self.coverage=CoverageAgent(); self.generator=GeneratorAgent(); self.executor=TestExecutor()
    def run(self,url,credentials=None):
        obs=self.explorer.explore(url); plan=self.planner.plan(obs); cov=self.coverage.evaluate(plan); attempts=0
        while cov.should_replan and attempts<settings.MAX_REPLAN_ATTEMPTS:
            attempts+=1; plan=self._replan(plan,cov); cov=self.coverage.evaluate(plan)
        gen=self.generator.generate(plan, obs, credentials)
        results=[self.executor.run_test(t) for t in gen.tests]
        actions=[f"{r.test_id}: {r.healing_action}" for r in results if r.healing_action]
        passed=sum(r.status=="PASSED" for r in results); healed=sum(r.status=="HEALED" for r in results); failed=sum(r.status=="FAILED" for r in results); esc=sum(r.status=="ESCALATED" for r in results); blocked=sum(r.status=="BLOCKED" for r in results)
        risk="HIGH" if (failed or esc or blocked) else ("MEDIUM" if cov.score<settings.COVERAGE_THRESHOLD else "LOW")
        return QualityReport(application_url=url,total_planned=len(plan.scenarios),total_generated=len(gen.tests),total_executed=len(results),passed=passed,healed=healed,failed=failed,escalated=esc,blocked=blocked,coverage_score=cov.score,coverage_gaps=cov.gaps,healer_actions=actions,risk=risk,summary=f"Planned {len(plan.scenarios)}, generated {len(gen.tests)}, executed {len(results)}, passed {passed}, healed {healed}, failed {failed}, escalated {esc}, blocked {blocked}; coverage {cov.score:.0%}.")
    def _replan(self,plan,cov):
        existing={s.name for s in plan.scenarios}; add=[]
        if "Logout" not in existing: add.append(TestScenario(id="S004",name="Logout",flow="Login then logout",category="happy_path",priority="medium",expected_outcome="User returns to login page"))
        if "Application error handling" not in existing: add.append(TestScenario(id="S005",name="Application error handling",flow="Trigger application failure",category="error_state",priority="high",expected_outcome="Error is surfaced"))
        return plan.model_copy(update={"scenarios":plan.scenarios+add})
