import json
import re

from app.llm.client import LLMClient
from app.models.schemas import PRDGapAnalysis, PRDGapItem


class PRDGapAgent:
    """Compares the generated test plan against a supplied PRD and reports
    which stated requirements are covered by a scenario and which are not."""

    def __init__(self):
        self.llm = LLMClient()

    def _extract_requirements(self, prd_text):
        lines = [line.strip(" -*\t") for line in prd_text.splitlines()]
        candidates = [
            line for line in lines
            if len(line) > 12 and re.search(r"[a-zA-Z]", line)
        ]
        # Fall back to sentence-splitting when the PRD is prose, not a list.
        if len(candidates) < 2:
            candidates = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prd_text) if len(s.strip()) > 12]
        return candidates[:25]

    def analyze(self, plan, prd_text):
        print()
        print("=" * 70)
        print("[AIVAR - BONUS] PRD-TO-TEST-PLAN GAP ANALYSIS")
        print("=" * 70)

        if not prd_text:
            return PRDGapAnalysis()

        requirements = self._extract_requirements(prd_text)
        scenario_text = "\n".join(f"{s.id}: {s.name} - {s.flow}" for s in plan.scenarios).lower()

        items = []
        for requirement in requirements:
            keywords = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", requirement)]
            hit = None
            for scenario in plan.scenarios:
                haystack = f"{scenario.name} {scenario.flow} {scenario.expected_outcome}".lower()
                if keywords and sum(1 for k in keywords if k in haystack) >= max(1, len(keywords) // 4):
                    hit = scenario
                    break
            items.append(
                PRDGapItem(
                    requirement=requirement,
                    covered=hit is not None,
                    matched_scenario_id=hit.id if hit else None,
                    note="Matched by keyword overlap with scenario flow." if hit else "No scenario references this requirement.",
                )
            )

        result = PRDGapAnalysis(
            requirements_considered=len(items),
            requirements_covered=sum(1 for i in items if i.covered),
            items=items,
        )
        print(result.model_dump_json(indent=2))
        print("=" * 70)
        return result
