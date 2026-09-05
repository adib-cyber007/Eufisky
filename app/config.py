"""Environment-backed configuration for Eufisky."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True, slots=True)
class Settings:
    """Small typed view of configuration used by the Phase-0 app."""

    assemblyai_api_key: str = os.getenv("ASSEMBLYAI_API_KEY", "")
    agent_backend: str = os.getenv("AGENT_BACKEND", "auto")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    senior_name: str = os.getenv("SENIOR_NAME", "Margaret")
    family_name: str = os.getenv("FAMILY_NAME", "Sarah")
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
