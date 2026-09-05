import uuid
from concurrent.futures import ThreadPoolExecutor

from app.agents.planner import PlannerAgent
from app.agents.coverage import CoverageAgent
from app.agents.generator import GeneratorAgent
from app.agents.prd_gap import PRDGapAgent
from app.browser.explorer import BrowserExplorer
from app.browser.executor import TestExecutor
from app.config import settings
from app.orchestration.cache import ExecutionCache
from app.models.schemas import QualityReport,TestCredentials,TestScenario,CoverageAnalysis


class AIVAROrchestrator:
    def __init__(self): self.explorer=BrowserExplorer(); self.planner=PlannerAgent(); self.coverage=CoverageAgent(); self.generator=GeneratorAgent(); self.executor=TestExecutor(); self.prd_gap=PRDGapAgent()

    def run(self,url,credentials=None,prd_text=None,intent=None,parallel=True):
        cache = ExecutionCache(url)
        obs = self.explorer.explore(url)
        fingerprint = cache.compute_fingerprint(obs)
        old_meta = cache.load_metadata()
        cache_hit = old_meta is not None
        changed = cache.website_changed(old_meta, fingerprint)

        planner_executed = coverage_executed = generator_executed = True
        tests_reused = tests_skipped = tests_reexecuted = llm_calls_saved = 0
        cov = None
        gen_tests = None
        plan = None
        reuse_possible = cache_hit and not changed

        if reuse_possible:
            plan = cache.load_plan()
            cached_tests = cache.load_tests()
            prev_results = cache.load_results()
            if plan is not None and cached_tests and prev_results is not None:
                # ---- Cache hit + website unchanged: skip Planner/Coverage/Generator ----
                planner_executed = False
                coverage_executed = False
                generator_executed = False
                llm_calls_saved = 3  # planner + coverage + generator avoided

                gen_tests = cached_tests
                creds_available = credentials is not None
                rerun_ids, reused_results = ExecutionCache.scenarios_to_rerun(prev_results, creds_available)
                tests_reused = sum(1 for r in reused_results if r.status == "PASSED")
                tests_skipped = sum(1 for r in reused_results if r.status == "BLOCKED")
                tests_to_run = [t for t in gen_tests if t.id in rerun_ids]
                tests_reexecuted = len(tests_to_run)

                new_results = self._execute(tests_to_run, parallel, artifact_root=str(cache.dir))

                by_id = {r.test_id: r for r in reused_results}
                by_id.update({r.test_id: r for r in new_results})
                order = [t.id for t in gen_tests]
                results = [by_id[tid] for tid in order if tid in by_id]

                cov = CoverageAnalysis(score=1.0, covered_areas=[], gaps=[], should_replan=False, reasoning="Reused from cache (website unchanged).")
            else:
                reuse_possible = False

        if not reuse_possible:
            # ---- Full pipeline: Planner -> Coverage -> Generator -> Executor ----
            plan=self.planner.plan(obs,prd_text=prd_text,intent=intent)
            cov=self.coverage.evaluate(plan); attempts=0
            while cov.should_replan and attempts<settings.MAX_REPLAN_ATTEMPTS:
                attempts+=1; plan=self._replan(plan,cov); cov=self.coverage.evaluate(plan)
            gen=self.generator.generate(plan, obs, credentials)
            gen_tests = gen.tests
            results = self._execute(gen_tests, parallel, artifact_root=str(cache.dir))
            tests_reexecuted = len(results)

            cache.save_plan(plan)
            cache.save_tests(gen_tests)

        cache.save_results(results)
        cache.save_metadata(fingerprint, gen_tests)

        gap=self.prd_gap.analyze(plan,prd_text) if prd_text else None
        actions=[f"{r.test_id}: {r.healing_action}" for r in results if r.healing_action]
        passed=sum(r.status=="PASSED" for r in results); healed=sum(r.status=="HEALED" for r in results); failed=sum(r.status=="FAILED" for r in results); esc=sum(r.status=="ESCALATED" for r in results); blocked=sum(r.status=="BLOCKED" for r in results)
        risk="HIGH" if (failed or esc or blocked) else ("MEDIUM" if cov.score<settings.COVERAGE_THRESHOLD else "LOW")

        credit_saving = "0%"
        if not planner_executed and not generator_executed and gen_tests:
            credit_saving = f"~{round(100 * tests_reused / max(1, len(gen_tests)))}%"

        self._print_cache_summary(cache_hit, changed, planner_executed, generator_executed, tests_reused, tests_reexecuted, llm_calls_saved, credit_saving)

        report = QualityReport(
            run_id=uuid.uuid4().hex[:12],application_url=url,total_planned=len(plan.scenarios),total_generated=len(gen_tests),total_executed=len(results),
            passed=passed,healed=healed,failed=failed,escalated=esc,blocked=blocked,coverage_score=cov.score,coverage_gaps=cov.gaps,healer_actions=actions,risk=risk,
            scenarios=plan.scenarios,results=results,prd_gap=gap,intent=intent,
            summary=f"Planned {len(plan.scenarios)}, generated {len(gen_tests)}, executed {len(results)}, passed {passed}, healed {healed}, failed {failed}, escalated {esc}, blocked {blocked}; coverage {cov.score:.0%}.",
            cache_hit=cache_hit, website_changed=changed, planner_executed=planner_executed, coverage_executed=coverage_executed, generator_executed=generator_executed,
            tests_reused=tests_reused, tests_skipped=tests_skipped, tests_reexecuted=tests_reexecuted, llm_calls_saved=llm_calls_saved, estimated_credit_saving=credit_saving,
        )
        # Persist the report alongside this URL's other cached artifacts so it
        # remains available (e.g. across a server restart) without re-running
        # any AI models - a fresh report is always rebuilt from cheap, local
        # cached/execution data, never from a stale on-disk copy.
        cache.save_report(report.model_dump())
        return report

    def _execute(self, tests, parallel, artifact_root):
        if not tests:
            return []
        if parallel and len(tests)>1:
            with ThreadPoolExecutor(max_workers=min(4,len(tests))) as pool:
                return list(pool.map(lambda t: self.executor.run_test(t, artifact_root=artifact_root), tests))
        return [self.executor.run_test(t, artifact_root=artifact_root) for t in tests]

    def _replan(self,plan,cov):
        existing={s.name for s in plan.scenarios}; add=[]
        if "Logout" not in existing: add.append(TestScenario(id="S004",name="Logout",flow="Login then logout",category="happy_path",priority="medium",expected_outcome="User returns to login page"))
        if "Application error handling" not in existing: add.append(TestScenario(id="S005",name="Application error handling",flow="Trigger application failure",category="error_state",priority="high",expected_outcome="Error is surfaced"))
        return plan.model_copy(update={"scenarios":plan.scenarios+add})

    def _print_cache_summary(self, cache_hit, changed, planner_executed, generator_executed, tests_reused, tests_reexecuted, llm_calls_saved, credit_saving):
        print()
        print("=" * 70)
        print("[AIVAR - CACHE / INCREMENTAL EXECUTION SUMMARY]")
        print("=" * 70)
        print(f"Cache Hit: {'Yes' if cache_hit else 'No'}")
        print(f"Website Changed: {'Yes' if changed else 'No'}")
        print(f"Planner Executed: {'Yes' if planner_executed else 'No'}")
        print(f"Generator Executed: {'Yes' if generator_executed else 'No'}")
        print(f"Tests Reused: {tests_reused}")
        print(f"Tests Re-executed: {tests_reexecuted}")
        print(f"LLM Calls Saved: {llm_calls_saved}")
        print(f"Estimated Credit Saving: {credit_saving}")
        print("=" * 70)
