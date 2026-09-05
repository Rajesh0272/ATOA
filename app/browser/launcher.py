"""Shared Chromium acquisition for the explorer and executor."""

LOCAL_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]


def launch_chromium(p, headless: bool = True):
    """Return a Playwright Browser launched locally."""
    return p.chromium.launch(headless=headless, args=LOCAL_LAUNCH_ARGS)


def new_page(browser):
    """Get a usable Page from a freshly launched Browser."""
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context()
    return context.new_page()
