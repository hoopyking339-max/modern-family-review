"""Configuration management for Modern Family Review Tool."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Load .env
load_dotenv(PROJECT_ROOT / ".env")

# API (DeepSeek - OpenAI compatible)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# TTS
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "TxGEqnHWrfWFTfGW9XjX")  # Josh — deep male voice

# Paths
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
SESSIONS_DIR = DATA_DIR / "sessions"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
SAMPLE_DIR = PROJECT_ROOT / "sample"

# Default watch directory (OneDrive GoodNotes)
DEFAULT_WATCH_DIR = os.path.expanduser(
    os.getenv(
        "GOODNOTES_WATCH_DIR",
        "~/Library/CloudStorage/OneDrive-个人/GoodNotes",
    )
)

# Episode detection patterns
EPISODE_PATTERNS = [
    r"Season\s+(\d+)\s*[,xX]\s*Episode\s+(\d+)",  # Season 1, Episode 3
    r"S(\d+)E(\d+)",  # S01E03
    r"(\d+)x(\d+)",  # 1x03
    r"Episode\s+(\d+)[:\s-]+(.+?)(?:\n|$)",  # Episode 3: Pilot
]

# Ensure directories exist
for d in [DATA_DIR, OUTPUT_DIR, SESSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
