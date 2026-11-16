from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # /worker


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines); real env vars win."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    llm_provider: str = "none"  # anthropic | none
    llm_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    llm_thinking: str = "adaptive"  # adaptive | disabled
    llm_batch: bool = True
    llm_batch_min: int = 20
    llm_batch_timeout_s: int = 3000
    contact_url: str = ""
    min_interval_s: float = 1.0
    taxonomy_path: Path = field(default_factory=lambda: ROOT / "taxonomy.yaml")
    pricing_path: Path = field(default_factory=lambda: ROOT / "pricing.yaml")
    sources_path: Path = field(default_factory=lambda: ROOT / "sources.yaml")

    @property
    def user_agent(self) -> str:
        ua = "FresherJobsIndiaBot/0.1"
        return f"{ua} (+{self.contact_url})" if self.contact_url else ua

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        key = os.environ.get("LLM_API_KEY", "")
        provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
        if not provider:
            provider = "anthropic" if (key or os.environ.get("ANTHROPIC_API_KEY")) else "none"
        return cls(
            database_url=os.environ.get("DATABASE_URL", ""),
            adzuna_app_id=os.environ.get("ADZUNA_APP_ID", ""),
            adzuna_app_key=os.environ.get("ADZUNA_APP_KEY", ""),
            llm_provider=provider,
            llm_api_key=key,
            llm_model=os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
            llm_thinking=os.environ.get("LLM_THINKING", "adaptive"),
            llm_batch=_bool("LLM_BATCH", True),
            llm_batch_min=int(os.environ.get("LLM_BATCH_MIN", "20")),
            llm_batch_timeout_s=int(os.environ.get("LLM_BATCH_TIMEOUT_S", "3000")),
            contact_url=os.environ.get("CONTACT_URL", ""),
            min_interval_s=float(os.environ.get("HTTP_MIN_INTERVAL_S", "1.0")),
        )
