import time
from typing import Literal, Optional
from pydantic import BaseModel, Field
class ElementInfo(BaseModel):
    tag:str; text:str=""; role:Optional[str]=None; name:Optional[str]=None; label:Optional[str]=None; selector_hint:Optional[str]=None
class ApplicationObservation(BaseModel):
    url:str; title:str=""; page_text:str=""; elements:list[ElementInfo]=Field(default_factory=list); links:list[str]=Field(default_factory=list); forms:list[str]=Field(default_factory=list)
class TestCredentials(BaseModel):
    username:Optional[str]=None
    password:Optional[str]=None
class TestScenario(BaseModel):
    id:str; name:str; flow:str; category:Literal["happy_path","negative","edge_case","error_state"]; priority:Literal["high","medium","low"]="medium"; expected_outcome:str
class TestPlan(BaseModel):
    application_url:str; application_summary:str; scenarios:list[TestScenario]; assumptions:list[str]=Field(default_factory=list)
class PRDGapItem(BaseModel):
    requirement:str; covered:bool; matched_scenario_id:Optional[str]=None; note:str=""
class PRDGapAnalysis(BaseModel):
    requirements_considered:int=0; requirements_covered:int=0; items:list[PRDGapItem]=Field(default_factory=list)
class CoverageGap(BaseModel):
    category:str; missing_scenario:str; reason:str; risk:Literal["high","medium","low"]
class CoverageAnalysis(BaseModel):
    score:float=Field(ge=0,le=1); covered_areas:list[str]=Field(default_factory=list); gaps:list[CoverageGap]=Field(default_factory=list); should_replan:bool; reasoning:str
class TestStep(BaseModel):
   action:Literal["navigate","fill","select","click","check","uncheck","hover","press","assert_visible","assert_not_visible","assert_text","assert_url","assert_count","assert_checked","assert_enabled","assert_disabled"]; target:Optional[dict]=None; value:Optional[str]=None
class GeneratedTest(BaseModel):
    id:str; scenario_id:str; name:str; steps:list[TestStep]; business_assertions:list[str]=Field(default_factory=list); requires_credentials:bool=False; credentials_available:bool=True
class GenerationResult(BaseModel):
    tests:list[GeneratedTest]
class ExecutionResult(BaseModel):
    test_id:str; status:Literal["PASSED","FAILED","HEALED","ESCALATED","BLOCKED"]; duration_ms:int=0; failed_step_index:Optional[int]=None; error:Optional[str]=None; artifacts_dir:Optional[str]=None; healing_action:Optional[str]=None

class StepExecutionError(RuntimeError):
    def __init__(self, step_index:int, step:TestStep, cause:Exception):
        super().__init__(str(cause))
        self.step_index = step_index
        self.step = step
class FailureDiagnosis(BaseModel):
    failure_type:Literal["LOCATOR_CHANGED","ELEMENT_MISSING","TIMEOUT","ASSERTION_FAILED","APPLICATION_ERROR","UNKNOWN"]; confidence:float=Field(ge=0,le=1); analysis:str; expected_locator:Optional[dict]=None; healing_candidate:Optional[dict]=None; business_intent_preserved:bool=False; safe_to_heal:bool=False
class ValidationResult(BaseModel):
    valid:bool; reason:str; matched_count:int=0; visible:bool=False; enabled:bool=False
class HealingResult(BaseModel):
    status:Literal["HEALED","REJECTED","ESCALATED"]; diagnosis:FailureDiagnosis; validation:Optional[ValidationResult]=None; action:str
class QualityReport(BaseModel):
    run_id:Optional[str]=None; created_at:float=Field(default_factory=lambda:time.time()); application_url:str; total_planned:int; total_generated:int; total_executed:int; passed:int; healed:int; failed:int; escalated:int; blocked:int=0; coverage_score:float; coverage_gaps:list[CoverageGap]=Field(default_factory=list); healer_actions:list[str]=Field(default_factory=list); risk:Literal["LOW","MEDIUM","HIGH"]; summary:str; scenarios:list[TestScenario]=Field(default_factory=list); results:list[ExecutionResult]=Field(default_factory=list); prd_gap:Optional[PRDGapAnalysis]=None; intent:Optional[str]=None
    cache_hit:bool=False; website_changed:bool=True; planner_executed:bool=True; coverage_executed:bool=True; generator_executed:bool=True; tests_reused:int=0; tests_skipped:int=0; tests_reexecuted:int=0; llm_calls_saved:int=0; estimated_credit_saving:str="0%"
