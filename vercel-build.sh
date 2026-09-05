#!/bin/bash
set -e

echo "========================================"
echo "AIVAR Vercel build starting"
echo "========================================"

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium inside the deployment..."
export PLAYWRIGHT_BROWSERS_PATH=0
python -m playwright install chromium

echo "Verifying installation..."
python -m playwright install --list

echo "========================================"
echo "AIVAR Vercel build completed"
echo "========================================"
