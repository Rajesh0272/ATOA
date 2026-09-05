#!/bin/bash
set -e

pip install -r requirements.txt

export PLAYWRIGHT_BROWSERS_PATH=.playwright
python -m playwright install chromium
