from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, AnyHttpUrl
from typing import Optional
from app.orchestration.orchestrator import AIVAROrchestrator
from app.models.schemas import TestCredentials
app=FastAPI(title="AIVAR Autonomous QA")
class RunRequest(BaseModel):
    url: AnyHttpUrl
    credentials: Optional[TestCredentials] = None
@app.get("/",response_class=HTMLResponse)
def home(): return """<!doctype html><html><head><title>AIVAR</title><style>body{font-family:Arial;max-width:900px;margin:40px auto}input{width:70%;padding:12px;margin:4px 0}button{padding:12px}pre{background:#f4f4f4;padding:15px;white-space:pre-wrap}</style></head><body><h1>AIVAR — Autonomous Test Orchestration Agent</h1><p>Enter a web application URL and run the autonomous QA lifecycle.</p><input id='url' value='http://127.0.0.1:9000'><br><input id='username' placeholder='Optional test username'><br><input id='password' type='password' placeholder='Optional test password'><br><button onclick='run()'>Run AIVAR</button><pre id='out'>Ready.</pre><script>async function run(){out.textContent='Running...';try{let credentials={username:document.getElementById('username').value||null,password:document.getElementById('password').value||null};let r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('url').value,credentials:credentials.username&&credentials.password?credentials:null})});out.textContent=JSON.stringify(await r.json(),null,2)}catch(e){out.textContent=e}}</script></body></html>"""
@app.post("/run")
def run(req:RunRequest):
    try:return AIVAROrchestrator().run(str(req.url), req.credentials).model_dump()
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))
