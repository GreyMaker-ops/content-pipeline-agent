"""
Configuration management for the social trend agent.

This module handles loading and validation of environment variables
and application settings.
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class RedditConfig:
    """Reddit API configuration."""
    client_id: str
    client_secret: str
    user_agent: str
    
    @classmethod
    def from_env(cls) -> "RedditConfig":
        """Load Reddit configuration from environment variables."""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "TrendBot/0.1")
        
        if not client_id or not client_secret:
            raise ValueError("Reddit API credentials not found in environment variables")
        
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )


@dataclass
class TwitterConfig:
    """Twitter API configuration."""
    bearer_token: str
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    
    @classmethod
    def from_env(cls) -> "TwitterConfig":
        """Load Twitter configuration from environment variables."""
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        
        if not all([bearer_token, api_key, api_secret, access_token, access_token_secret]):
            raise ValueError("Twitter API credentials not found in environment variables")
        
        return cls(
            bearer_token=bearer_token,
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )


@dataclass
class StagehandConfig:
    """Stagehand/Browserbase configuration."""
    api_key: Optional[str]
    browserbase_api_key: Optional[str]
    browserbase_project_id: Optional[str]
    api_url: Optional[str]
    
    @classmethod
    def from_env(cls) -> "StagehandConfig":
        """Load Stagehand configuration from environment variables."""
        return cls(
            api_key=os.getenv("STAGEHAND_API_KEY"),
            browserbase_api_key=os.getenv("BROWSERBASE_API_KEY"),
            browserbase_project_id=os.getenv("BROWSERBASE_PROJECT_ID"),
            api_url=os.getenv("STAGEHAND_API_URL")
        )


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str
    
    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Load OpenAI configuration from environment variables."""
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("GPT_MODEL", "gpt-4o")
        
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        return cls(
            api_key=api_key,
            model=model
        )


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load database configuration from environment variables."""
        url = os.getenv("DATABASE_URL", "sqlite://db.sqlite3")
        return cls(url=url)


@dataclass
class AppConfig:
    """Application configuration."""
    min_score: float
    subreddits: List[str]
    interval_minutes: int
    host: str
    port: int
    debug: bool
    log_level: str
    log_format: str
    prometheus_port: int
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load application configuration from environment variables."""
        min_score = float(os.getenv("MIN_SCORE", "200"))
        subreddits_str = os.getenv("SUBREDDITS", "interestingasfuck,technology,pics")
        subreddits = [s.strip() for s in subreddits_str.split(",")]
        interval_minutes = int(os.getenv("INTERVAL_MINUTES", "5"))
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        debug = os.getenv("DEBUG", "false").lower() == "true"
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_format = os.getenv("LOG_FORMAT", "json")
        prometheus_port = int(os.getenv("PROMETHEUS_PORT", "8001"))
        
        return cls(
            min_score=min_score,
            subreddits=subreddits,
            interval_minutes=interval_minutes,
            host=host,
            port=port,
            debug=debug,
            log_level=log_level,
            log_format=log_format,
            prometheus_port=prometheus_port
        )


@dataclass
class Config:
    """Complete application configuration."""
    reddit: RedditConfig
    twitter: TwitterConfig
    stagehand: StagehandConfig
    openai: OpenAIConfig
    database: DatabaseConfig
    app: AppConfig
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load complete configuration from environment variables."""
        return cls(
            reddit=RedditConfig.from_env(),
            twitter=TwitterConfig.from_env(),
            stagehand=StagehandConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            database=DatabaseConfig.from_env(),
            app=AppConfig.from_env()
        )
    
    def validate(self) -> None:
        """Validate configuration and raise errors for missing required values."""
        # Reddit validation
        if not self.reddit.client_id or not self.reddit.client_secret:
            raise ValueError("Reddit API credentials are required")
        
        # Twitter validation
        if not all([
            self.twitter.bearer_token,
            self.twitter.api_key,
            self.twitter.api_secret,
            self.twitter.access_token,
            self.twitter.access_token_secret
        ]):
            raise ValueError("Twitter API credentials are required")
        
        # OpenAI validation
        if not self.openai.api_key:
            raise ValueError("OpenAI API key is required")
        
        # App validation
        if self.app.min_score <= 0:
            raise ValueError("MIN_SCORE must be positive")
        
        if not self.app.subreddits:
            raise ValueError("At least one subreddit must be specified")
        
        if self.app.interval_minutes <= 0:
            raise ValueError("INTERVAL_MINUTES must be positive")
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary (excluding sensitive data)."""
        return {
            "reddit": {
                "user_agent": self.reddit.user_agent,
                "client_id_set": bool(self.reddit.client_id)
            },
            "twitter": {
                "api_key_set": bool(self.twitter.api_key),
                "bearer_token_set": bool(self.twitter.bearer_token)
            },
            "stagehand": {
                "api_key_set": bool(self.stagehand.api_key),
                "browserbase_api_key_set": bool(self.stagehand.browserbase_api_key),
                "api_url": self.stagehand.api_url
            },
            "openai": {
                "model": self.openai.model,
                "api_key_set": bool(self.openai.api_key)
            },
            "database": {
                "url": self.database.url
            },
            "app": {
                "min_score": self.app.min_score,
                "subreddits": self.app.subreddits,
                "interval_minutes": self.app.interval_minutes,
                "host": self.app.host,
                "port": self.app.port,
                "debug": self.app.debug,
                "log_level": self.app.log_level,
                "log_format": self.app.log_format,
                "prometheus_port": self.app.prometheus_port
            }
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.validate()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment variables."""
    global _config
    _config = None
    return get_config()


# Convenience functions for accessing specific configurations
def get_reddit_config() -> RedditConfig:
    """Get Reddit configuration."""
    return get_config().reddit


def get_twitter_config() -> TwitterConfig:
    """Get Twitter configuration."""
    return get_config().twitter


def get_stagehand_config() -> StagehandConfig:
    """Get Stagehand configuration."""
    return get_config().stagehand


def get_openai_config() -> OpenAIConfig:
    """Get OpenAI configuration."""
    return get_config().openai


def get_database_config() -> DatabaseConfig:
    """Get database configuration."""
    return get_config().database


def get_app_config() -> AppConfig:
    """Get application configuration."""
    return get_config().app

