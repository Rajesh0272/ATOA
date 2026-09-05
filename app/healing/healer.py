from app.config import settings
from app.agents.failure_analyzer import FailureAnalyzer
from app.healing.validator import LocatorValidator
from app.models.schemas import HealingResult
class Healer:
    def __init__(self): self.analyzer=FailureAnalyzer(); self.validator=LocatorValidator()
    def heal(self,page,evidence):
        d=self.analyzer.diagnose(evidence)
        if d.failure_type=="APPLICATION_ERROR": return HealingResult(status="ESCALATED",diagnosis=d,action="Application defect detected; no test modification attempted.")
        failed_step = evidence.get("failed_step") or {}
        expected = failed_step.get("target")
        if (
            d.failure_type == "LOCATOR_CHANGED"
            and expected
            and d.healing_candidate == expected
        ):
            return HealingResult(
                status="REJECTED",
                diagnosis=d,
                action="Healing rejected: proposed locator is identical to the failed locator.",
            )
        if d.failure_type!="LOCATOR_CHANGED" or not d.safe_to_heal or not d.business_intent_preserved or d.confidence<.90 or not d.healing_candidate: return HealingResult(status="REJECTED",diagnosis=d,action="Healing rejected by safety gates; escalate instead.")
        v=self.validator.validate(page,d.healing_candidate)
        if not v.valid: return HealingResult(status="REJECTED",diagnosis=d,validation=v,action="Candidate failed deterministic validation; escalate instead.")
        return HealingResult(status="HEALED",diagnosis=d,validation=v,action=f"Validated replacement locator: {d.healing_candidate}")
