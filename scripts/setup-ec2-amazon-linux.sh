#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Repo root: $REPO_ROOT"

PKG_MANAGER=""
if command -v yum >/dev/null 2>&1; then
  PKG_MANAGER=yum
elif command -v dnf >/dev/null 2>&1; then
  PKG_MANAGER=dnf
elif command -v apt-get >/dev/null 2>&1; then
  PKG_MANAGER=apt
else
  echo "Unsupported package manager. This script targets Amazon Linux (yum/dnf)." >&2
  exit 1
fi

echo "Using package manager: $PKG_MANAGER"

sudo $PKG_MANAGER update -y || true

echo "Installing build and Python dependencies (may prompt for password)..."
if [ "$PKG_MANAGER" = "apt" ]; then
  sudo apt-get install -y git python3 python3-venv python3-dev python3-pip build-essential cmake libssl-dev libbz2-dev libffi-dev
else
  sudo $PKG_MANAGER install -y git python3 python3-devel python3-venv python3-pip gcc gcc-c++ make cmake openssl-devel bzip2-devel libffi-devel
fi

cd "$REPO_ROOT"

echo "Creating virtual environment (venv) if missing..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip/setuptools/wheel..."
pip install --upgrade pip setuptools wheel

echo "Installing Python requirements from requirements.txt"
if [ -f requirements.txt ]; then
  if pip install -r requirements.txt; then
    echo "All requirements installed successfully."
  else
    echo "Requirements install had failures. Attempting best-effort workarounds for dlib/face_recognition." >&2
    pip install --upgrade cmake || true
    pip install --only-binary=:all: dlib || true
    pip install --only-binary=:all: face_recognition || true
    echo "If dlib still fails to build, consider using Conda, WSL2, or a prebuilt wheel for your Python version." >&2
  fi
else
  echo "requirements.txt not found in repo root: $REPO_ROOT" >&2
fi

echo "Setup complete. To activate the environment later run:"
echo "  source $REPO_ROOT/venv/bin/activate"
echo "To run the app (example): python app.py or flask run depending on your project setup."

exit 0
