#!/bin/bash
set -e

echo "========================================"
echo "AIVAR Vercel build starting"
echo "========================================"

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium..."
python -m playwright install chromium

echo "Checking Playwright installation..."
python -m playwright install --list

echo "========================================"
echo "AIVAR Vercel build completed"
echo "========================================"