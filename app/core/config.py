from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Smart Document Q&A'
    app_env: str = 'local'
    api_host: str = '0.0.0.0'
    api_port: int = 8000

    database_url: str = 'postgresql+psycopg://postgres:postgres@db:5432/document_qa'
    redis_url: str = 'redis://redis:6379/0'
    celery_broker_url: str = 'redis://redis:6379/1'
    celery_result_backend: str = 'redis://redis:6379/2'

    ollama_base_url: str = 'http://ollama:11434'
    ollama_model: str = 'llama3.2:3b'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'

    upload_dir: Path = Path('/app/data/uploads')
    faiss_dir: Path = Path('/app/data/faiss')
    max_upload_mb: int = 25
    chunk_size: int = 900
    chunk_overlap: int = 160
    top_k: int = 5
    min_retrieval_score: float = 0.25
    cors_origins: str = '*'

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == '*':
            return ['*']
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.faiss_dir.mkdir(parents=True, exist_ok=True)
    return settings
