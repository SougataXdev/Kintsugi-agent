from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base project root directory
ROOT = Path(__file__).resolve().parent.parent

# Pre-load environment variables from .env into system environment
load_dotenv(ROOT / ".env")


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==============================================
    # Pinecone Configuration
    # ==============================================
    pinecone_api_key: str = Field(default="", description="Pinecone API Key")
    pinecone_index_name: str = Field(default="cloudops-agent", description="Pinecone Index Name")
    pinecone_cloud: str = Field(default="aws", description="Pinecone Cloud Provider (e.g. aws, gcp)")
    pinecone_region: str = Field(default="us-east-1", description="Pinecone Region")
    pinecone_dimension: int = Field(default=1536, description="Pinecone Vector Dimension (e.g. 1536 for OpenAI embeddings)")
    pinecone_metric: str = Field(default="cosine", description="Pinecone Distance Metric (e.g. cosine, euclidean)")

    # ==============================================
    # LLM & Embedding Providers
    # ==============================================
    openai_api_key: str = Field(default="", description="OpenAI API Key")

    # ==============================================
    # Web Search & Tool Integrations
    # ==============================================
    tavily_api_key: str = Field(default="", description="Tavily Search API Key")

    # ==============================================
    # LangSmith / Observability
    # ==============================================
    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith Tracing")
    langchain_api_key: str = Field(default="", description="LangSmith API Key")
    langchain_project: str = Field(default="cloudops-agent", description="LangSmith Project Name")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith Endpoint")

    # ==============================================
    # Application Configuration
    # ==============================================
    host: str = Field(default="0.0.0.0", description="FastAPI Server Host")
    port: int = Field(default=8000, description="FastAPI Server Port")
    debug: bool = Field(default=False, description="Enable FastAPI Debug Mode")

    top_k: int = Field(default=5, description="Number of top documents to retrieve in vector search")
    max_support_retries: int = Field(default=2, description="Maximum support retry attempts")
    max_retrieval_rewrites: int = Field(default=2, description="Maximum query retrieval rewrites")
    max_web_rewrites: int = Field(default=2, description="Maximum web query rewrites")
    database_path: Path = Field(default=Path("data/audit.db"), description="SQLite database path")

    @property
    def resolved_database_path(self) -> Path:
        """Returns the absolute path to the SQLite audit database."""
        if self.database_path.is_absolute():
            return self.database_path
        return ROOT / self.database_path

    def ensure_directories(self) -> None:
        """Ensures that required application directories (e.g. data/) exist."""
        self.resolved_database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton instance of Settings."""
    settings_instance = Settings()
    settings_instance.ensure_directories()
    return settings_instance


# Convenient module-level settings singleton
settings: Settings = get_settings()