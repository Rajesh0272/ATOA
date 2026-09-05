import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.config import settings
from app.browser.launcher import launch_chromium, new_page
from app.healing.healer import Healer
from app.models.schemas import *
class TestExecutor:
    def __init__(self): self.healer=Healer()
    def run_test(self,test,artifact_root="artifacts"):
        start=time.time(); td=Path(artifact_root)/test.id; td.mkdir(parents=True,exist_ok=True)
        if test.requires_credentials and not test.credentials_available:
            return ExecutionResult(
                test_id=test.id,
                status="BLOCKED",
                duration_ms=int((time.time()-start)*1000),
                error="Credentials are required for this scenario but were not supplied.",
                artifacts_dir=str(td),
            )
        with sync_playwright() as p:
            b = launch_chromium(p); page = new_page(b)
            try:
                self._run(page,test.steps)
                self._validate_business_assertions(test)
                return ExecutionResult(test_id=test.id,status="PASSED",duration_ms=int((time.time()-start)*1000),artifacts_dir=str(td))
            except Exception as e:
                screenshot_path = td/"failure.png"
                try:
                    page.screenshot(path=str(screenshot_path),full_page=True)
                except Exception:
                    screenshot_path = None
                else:
                    if not screenshot_path.exists():
                        screenshot_path = None
                screenshot_path = str(screenshot_path) if screenshot_path else None
                dom=page.content()
                try: (td/"dom.html").write_text(dom,encoding="utf-8")
                except Exception: pass
                evidence={
                    "test_id": test.id,
                    "url": page.url,
                    "error": str(e),
                    "dom": dom[:30000],
                    "steps": [step.model_dump() for step in test.steps],
                }
                if isinstance(e, StepExecutionError):
                    evidence["failed_step_index"] = e.step_index
                    evidence["failed_step"] = e.step.model_dump()
                (td/"evidence.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
                h=self.healer.heal(page,evidence)
                if h.status=="HEALED":
                    steps=[TestStep.model_validate(x.model_dump()) for x in test.steps]
                    failed_index = evidence.get("failed_step_index")
                    if (
                        failed_index is None
                        or failed_index >= len(steps)
                        or steps[failed_index].action == "navigate"
                    ):
                        return ExecutionResult(
                            test_id=test.id,
                            status="FAILED",
                            duration_ms=int((time.time()-start)*1000),
                            error="Healing diagnosis did not identify a replaceable failed locator step.",
                            artifacts_dir=str(td),
                            healing_action=h.action,
                            screenshot_path=screenshot_path,
                        )
                    steps[failed_index].target = h.diagnosis.healing_candidate
                    try:
                        page.goto(test.steps[0].value,wait_until="domcontentloaded",timeout=15000) if test.steps and test.steps[0].action=="navigate" else None
                        self._run(page,steps)
                        self._validate_business_assertions(test.model_copy(update={"steps": steps}))
                        (td/"healing.json").write_text(h.model_dump_json(indent=2),encoding="utf-8")
                        return ExecutionResult(test_id=test.id,status="HEALED",duration_ms=int((time.time()-start)*1000),artifacts_dir=str(td),healing_action=h.action,screenshot_path=screenshot_path)
                    except Exception as re: return ExecutionResult(test_id=test.id,status="FAILED",duration_ms=int((time.time()-start)*1000),error=f"Full retest failed: {re}",artifacts_dir=str(td),screenshot_path=screenshot_path)
                if h.status=="ESCALATED":
                    (td/"healing.json").write_text(h.model_dump_json(indent=2),encoding="utf-8")
                    return ExecutionResult(test_id=test.id,status="ESCALATED",duration_ms=int((time.time()-start)*1000),error=str(e),artifacts_dir=str(td),healing_action=h.action,screenshot_path=screenshot_path)
                return ExecutionResult(test_id=test.id,status="FAILED",duration_ms=int((time.time()-start)*1000),error=str(e),artifacts_dir=str(td),healing_action=h.action,screenshot_path=screenshot_path)
            finally: b.close()
    def _validate_business_assertions(self, test):
        assertion_steps = sum(
            step.action in {"assert_visible", "assert_not_visible", "assert_text"} for step in test.steps
        )
        if test.business_assertions and assertion_steps < len(test.business_assertions):
            raise AssertionError(
                f"Test declares {len(test.business_assertions)} business assertion(s) "
                f"but contains only {assertion_steps} executable assertion step(s)"
            )

    def _run(self,page,steps):
        for step_index, st in enumerate(steps):
            try:
                if st.action=="navigate":
                    r=page.goto(st.value,wait_until="domcontentloaded",timeout=15000)
                    if r is not None and r.status>=500: raise RuntimeError(f"HTTP {r.status} Internal Server Error")
                elif st.action=="assert_url":
                    page.wait_for_url(f"**{st.value}**" if st.value and "*" not in st.value else (st.value or "**"),timeout=8000)
                else:
                    if not st.target:
                        raise ValueError(
                            f"Generated test step {st.action!r} is missing a target"
                        )
                    t=st.target
                    if "selector_hint" in t and "id" not in t and "selector" not in t:
                        hint = str(t["selector_hint"])
                        if st.action == "click" and page.locator(f"#{hint}").count() == 0:
                            t = {"selector": f'button.add-to-cart[data-product-id="{hint}"]'}
                        else:
                            t = {"id": hint}
                    s=t.get("strategy")
                    if s is None:
                        if "role" in t:
                            s = "role"
                        elif "label" in t:
                            s = "label"
                        elif "text" in t:
                            s = "text"
                        elif "id" in t:
                            s = "id"
                        elif "selector" in t:
                            s = "selector"
                    if not s:
                        raise ValueError(
                            f"Generated test step {st.action!r} has no selector strategy"
                        )
                    if s=="role":
                        role = {"select": "combobox"}.get(t["role"], t["role"])
                        loc=page.get_by_role(role,name=t.get("name"))
                        if not loc.count() and t.get("name"):
                            name = t["name"]
                            if role == "heading":
                                loc = page.get_by_text(name, exact=True)
                            elif role == "button":
                                loc = page.get_by_text(name, exact=True)
                            else:
                                loc=page.locator(f'[name="{name}"]')
                        if role == "button" and str(t.get("name", "")).strip().lower() == "add to cart" and loc.count() > 1:
                            loc = loc.first
                    elif s=="label": loc=page.get_by_label(t.get("label") or t.get("value"))
                    elif s=="text": loc=page.get_by_text(t.get("text") or t.get("value"),exact=True)
                    elif s=="id": loc=page.locator(f"#{t['id']}")
                    elif s=="selector":
                        selector = t["selector"]
                        if selector == "button[text='Add to cart']":
                            selector = "button.add-to-cart"
                        loc=page.locator(selector)
                        if selector == "button.add-to-cart" and loc.count() > 1:
                            loc = loc.first
                    else: raise ValueError(f"Unsupported selector strategy: {s}")
                    if st.action=="fill": loc.fill(st.value or "")
                    elif st.action=="select":
                        if not (st.value or "").strip():
                            st.value = "all"
                        try:
                            loc.select_option(st.value or "")
                        except Exception:
                            options = loc.locator("option")
                            wanted = (st.value or "").strip().lower()
                            match = next(
                                (
                                    option.get_attribute("value")
                                    for option in options.all()
                                    if (option.inner_text() or "").strip().lower() == wanted
                                    or (option.get_attribute("value") or "").strip().lower() == wanted
                                ),
                                None,
                            )
                            if match is None:
                                raise ValueError(
                                    f"Select option {st.value!r} is not present in the observed control"
                                )
                            loc.select_option(match)
                    elif st.action=="click": loc.click(timeout=5000)
                    elif st.action=="check": loc.check(timeout=5000)
                    elif st.action=="uncheck": loc.uncheck(timeout=5000)
                    elif st.action=="hover": loc.hover(timeout=5000)
                    elif st.action=="press": loc.press(st.value or "Enter",timeout=5000)
                    elif st.action=="assert_visible": loc.wait_for(state="visible",timeout=5000)
                    elif st.action=="assert_not_visible": loc.wait_for(state="hidden",timeout=5000)
                    elif st.action=="assert_checked":
                        if not loc.is_checked(): raise AssertionError("Expected element to be checked")
                    elif st.action=="assert_enabled":
                        if not loc.is_enabled(): raise AssertionError("Expected element to be enabled")
                    elif st.action=="assert_disabled":
                        if loc.is_enabled(): raise AssertionError("Expected element to be disabled")
                    elif st.action=="assert_count":
                        expected=int(st.value or "0")
                        if loc.count()!=expected: raise AssertionError(f"Expected {expected} matching elements, found {loc.count()}")
                    elif st.action=="assert_text":
                        if st.value not in loc.inner_text():
                            text_loc = page.get_by_text(st.value or "", exact=False)
                            text_loc.wait_for(state="visible", timeout=5000)
            except Exception as exc:
                raise StepExecutionError(step_index, st, exc) from exc
