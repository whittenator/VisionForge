import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

# Ensure the server module reads a known token in tests.
os.environ.setdefault("VF_AGENT_TOKEN", "test-token")
