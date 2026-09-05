from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import os
os.chdir(Path(__file__).resolve().parents[1]/"demo_web")
print("Demo app: http://127.0.0.1:9100")
ThreadingHTTPServer(("127.0.0.1",9100),SimpleHTTPRequestHandler).serve_forever()
