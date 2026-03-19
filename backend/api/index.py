import sys
from pathlib import Path

# Ensure the backend root is on sys.path so "app" package resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402, F401 — re-export for Vercel
