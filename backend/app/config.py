from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    database_url: str
    jwt_secret: str = Field(min_length=32)
    environment: Literal['development', 'production'] = 'development'
    cookie_secure: bool = True
    trust_proxy_headers: bool = False
    cors_origins: str = 'http://localhost:5173'
    allowed_hosts: str = 'localhost,127.0.0.1,testserver'

    @property
    def origins(self) -> list[str]:
        return [value.strip().rstrip('/') for value in self.cors_origins.split(',') if value.strip()]

    @property
    def hosts(self) -> list[str]:
        return [value.strip() for value in self.allowed_hosts.split(',') if value.strip()]

    @model_validator(mode='after')
    def check_production(self):
        if self.environment == 'production' and self.jwt_secret.startswith(('replace_', 'test-')):
            raise ValueError('Set a randomly generated JWT_SECRET in production')
        if self.environment == 'production' and not self.cookie_secure:
            raise ValueError('COOKIE_SECURE must be true in production')
        if self.environment == 'production' and any(origin.startswith('http://') for origin in self.origins):
            raise ValueError('CORS_ORIGINS must use HTTPS in production')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
