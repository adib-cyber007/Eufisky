"""Environment-backed configuration for Eufisky."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _env_flag(name: str, default: bool = False) -> bool:
    """Read an opt-in feature flag without treating unknown values as enabled."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


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
    feature_incident_insights: bool = _env_flag("FEATURE_INCIDENT_INSIGHTS")
    feature_guardian_voice_tuning: bool = _env_flag("FEATURE_GUARDIAN_VOICE_TUNING")
    feature_spanish_monitoring: bool = _env_flag("FEATURE_SPANISH_MONITORING")
    feature_incident_export: bool = _env_flag("FEATURE_INCIDENT_EXPORT")
    feature_twilio_telephony: bool = _env_flag("FEATURE_TWILIO_TELEPHONY")


def public_feature_flags(config: Settings) -> dict[str, bool]:
    """Return only non-secret flags that browser clients are allowed to see."""

    return {
        "incident_insights": config.feature_incident_insights,
        "guardian_voice_tuning": config.feature_guardian_voice_tuning,
        "spanish_monitoring": config.feature_spanish_monitoring,
        "incident_export": config.feature_incident_export,
        "twilio_telephony": config.feature_twilio_telephony,
    }


settings = Settings()
