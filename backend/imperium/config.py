"""Central settings, loaded from environment / .env (TDD §10 Integrations)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    imperium_env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    workspace_dir: str = "./.imperium/workspaces"

    # Postgres — RKB relational store
    postgres_dsn: str = "postgresql+psycopg://imperium:imperium@localhost:5432/imperium"

    # Qdrant — RKB embeddings
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "imperium_rkb"

    # Neo4j — RKB knowledge graph
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "imperium123"

    # Redis — cache
    redis_url: str = "redis://localhost:6379/0"

    # LLM providers (Phase 1) — NO OpenAI/OpenRouter. Per-agent routing in llm/routing.py.
    # NVIDIA Nemotron — orchestrator / business-logic / edge-case reasoning
    nvidia_api_key: str = "changeme"
    nvidia_model: str = "nvidia/llama-3.3-nemotron-super-49b-v1"
    # Groq — documentation / orchestrator fallback
    groq_api_key: str = "changeme"
    groq_model: str = "llama-3.3-70b-versatile"
    # Cerebras — structure / security / compatibility / comprehension
    cerebras_api_key: str = "changeme"
    cerebras_model: str = "llama-3.3-70b"
    # Mistral Codestral — implementation / test codegen / business-logic secondary
    mistral_api_key: str = "changeme"
    mistral_model: str = "codestral-latest"
    # Gemini — research (long-context) / fallback
    gemini_api_key: str = "changeme"
    gemini_model: str = "gemini-2.0-flash"

    # Sandbox
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
