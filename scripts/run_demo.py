from pprint import pprint
from app.orchestration.orchestrator import AIVAROrchestrator
print("ATOA AUTONOMOUS TEST ORCHESTRATION AGENT DEMO")
print("Target: http://127.0.0.1:9100")
pprint(AIVAROrchestrator().run("http://127.0.0.1:9100").model_dump())
