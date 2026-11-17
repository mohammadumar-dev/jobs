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
    llm_provider: str = "none"  # chain | anthropic | none
    llm_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    llm_thinking: str = "adaptive"  # adaptive | disabled
    llm_batch: bool = True
    llm_batch_min: int = 20
    llm_batch_timeout_s: int = 3000
    llm_max_jobs: int = 300  # per run; the rest wait for the next run
    # free-tier chain (LLM_PROVIDER=chain)
    llm_chain: tuple[str, ...] = ("gemini", "groq", "openrouter")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_thinking_level: str = "minimal"
    gemini_interval_s: float = 6.0
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: str = "low"
    groq_interval_s: float = 15.0
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_interval_s: float = 4.0
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
        env = os.environ.get
        key = env("LLM_API_KEY", "")
        free_keys = [env("GEMINI_API_KEY"), env("GROQ_API_KEY"), env("OPENROUTER_API_KEY")]
        provider = env("LLM_PROVIDER", "").strip().lower()
        if not provider:
            if any(free_keys):
                provider = "chain"
            elif key or env("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            else:
                provider = "none"
        chain = tuple(
            p.strip().lower() for p in env("LLM_CHAIN", "gemini,groq,openrouter").split(",") if p.strip()
        )
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
            llm_max_jobs=int(env("LLM_MAX_JOBS", "300")),
            llm_chain=chain,
            gemini_api_key=env("GEMINI_API_KEY", ""),
            gemini_model=env("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            gemini_thinking_level=env("GEMINI_THINKING_LEVEL", "minimal"),
            gemini_interval_s=float(env("GEMINI_INTERVAL_S", "6")),
            groq_api_key=env("GROQ_API_KEY", ""),
            groq_model=env("GROQ_MODEL", "openai/gpt-oss-120b"),
            groq_reasoning_effort=env("GROQ_REASONING_EFFORT", "low"),
            groq_interval_s=float(env("GROQ_INTERVAL_S", "15")),
            openrouter_api_key=env("OPENROUTER_API_KEY", ""),
            openrouter_model=env("OPENROUTER_MODEL", "openrouter/free"),
            openrouter_interval_s=float(env("OPENROUTER_INTERVAL_S", "4")),
            contact_url=os.environ.get("CONTACT_URL", ""),
            min_interval_s=float(os.environ.get("HTTP_MIN_INTERVAL_S", "1.0")),
        )
