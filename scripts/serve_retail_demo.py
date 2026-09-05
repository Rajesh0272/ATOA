from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="Serve the AIVAR retail demo.")
    parser.add_argument("--port", type=int, default=9100)
    args = parser.parse_args()

    web_root = Path(__file__).resolve().parent / "retail_demo"
    os.chdir(web_root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), SimpleHTTPRequestHandler)
    print(f"Retail demo: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
