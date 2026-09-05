"""Shared Chromium acquisition for the explorer and executor.

On hosts that can install/persist Playwright's own Chromium binary (a
local machine, a Docker-based host, a VM), we simply launch it. On hosts
that cannot (notably Vercel's Python serverless functions, which rebuild
the Python dependency tree from requirements.txt into an ephemeral /tmp
on every cold start and never re-run `playwright install`), set
BROWSER_WS_ENDPOINT to a remote browser-as-a-service CDP websocket URL
(e.g. Browserless.io, Browserbase) and we connect to that instead.
"""
from app.config import settings

LOCAL_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]


def launch_chromium(p, headless: bool = True):
    """Return a Playwright Browser, either connected over CDP to a remote
    browser service (when settings.BROWSER_WS_ENDPOINT is configured) or
    launched locally otherwise."""
    ws_endpoint = settings.BROWSER_WS_ENDPOINT
    if ws_endpoint:
        return p.chromium.connect_over_cdp(ws_endpoint)
    return p.chromium.launch(headless=headless, args=LOCAL_LAUNCH_ARGS)


def new_page(browser):
    """Get a usable Page from a Browser, whether it was launched locally
    (no existing contexts) or obtained via connect_over_cdp (some remote
    services hand back a Browser that already has a default context that
    should be reused rather than always creating a fresh one)."""
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context()
    return context.new_page()
