"""Application settings.

All settings can be changed in backend/.env.  Keeping them here means the rest
of the application does not need to know where a setting came from.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / ".." / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "qualicoder.db"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http" + chr(58) + chr(47) + chr(47) + "127.0.0.1" + chr(58) + "11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:70b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
MAX_SOURCE_MB = int(os.getenv("MAX_SOURCE_MB", "500"))
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
ENCRYPTION_ENABLED = os.getenv("ENCRYPTION_ENABLED", "true").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-before-enabling-auth")
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
HF_TOKEN = os.getenv("HF_TOKEN", "")
SEMANTIC_MODEL = os.getenv("SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
