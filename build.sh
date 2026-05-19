#!/usr/bin/env bash
# Local build script: install Python deps + build Svelte frontend
set -e

# Python dependencies
pip install -r requirements.txt

# Build frontend
cd frontend
npm install
npm run build
cd ..
