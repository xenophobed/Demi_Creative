"""
Root test configuration.

Loads backend/.env so API keys are available for skipif guards
that evaluate at collection time.
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory before pytest collects tests.
# This ensures os.getenv("ANTHROPIC_API_KEY") etc. resolve in skipif decorators.
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)
