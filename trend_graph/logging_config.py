"""
Logging configuration for the social trend agent.

This module provides structured logging with JSON output,
multiple handlers, and proper log levels.
"""

import logging
import logging.config
import sys
from datetime import datetime
from typing import Dict, Any
import json

from .config import get_app_config


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'workflow_id'):
            log_entry["workflow_id"] = record.workflow_id
        
        if hasattr(record, 'reddit_id'):
            log_entry["reddit_id"] = record.reddit_id
        
        if hasattr(record, 'tweet_id'):
            log_entry["tweet_id"] = record.tweet_id
        
        if hasattr(record, 'duration'):
            log_entry["duration"] = record.duration
        
        if hasattr(record, 'status'):
            log_entry["status"] = record.status
        
        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Custom text formatter for human-readable logs."""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging() -> None:
    """Set up logging configuration based on app config."""
    app_config = get_app_config()
    
    # Determine formatter based on config
    if app_config.log_format.lower() == 'json':
        formatter_class = JSONFormatter
    else:
        formatter_class = TextFormatter
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                '()': formatter_class,
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': app_config.log_level,
                'formatter': 'default',
                'stream': sys.stdout,
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': app_config.log_level,
                'formatter': 'default',
                'filename': '/app/logs/trend_agent.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'default',
                'filename': '/app/logs/trend_agent_errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
        },
        'loggers': {
            'trend_graph': {
                'level': app_config.log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            'backend': {
                'level': app_config.log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
        },
        'root': {
            'level': app_config.log_level,
            'handlers': ['console', 'file', 'error_file'],
        },
    }
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level {app_config.log_level} and format {app_config.log_format}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for adding context to log messages."""
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]):
        super().__init__(logger, extra)
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add extra context."""
        # Add extra fields to the log record
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        kwargs['extra'].update(self.extra)
        
        return msg, kwargs


def get_workflow_logger(workflow_id: str) -> LoggerAdapter:
    """Get a logger adapter with workflow context."""
    logger = get_logger('trend_graph.workflow')
    return LoggerAdapter(logger, {'workflow_id': workflow_id})


def get_post_logger(reddit_id: str, workflow_id: str = None) -> LoggerAdapter:
    """Get a logger adapter with post context."""
    logger = get_logger('trend_graph.post')
    extra = {'reddit_id': reddit_id}
    if workflow_id:
        extra['workflow_id'] = workflow_id
    return LoggerAdapter(logger, extra)


def log_performance(func):
    """Decorator to log function performance."""
    def wrapper(*args, **kwargs):
        import time
        
        logger = get_logger(f'{func.__module__}.{func.__name__}')
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Function {func.__name__} completed successfully",
                extra={'duration': duration, 'status': 'success'}
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Function {func.__name__} failed: {e}",
                extra={'duration': duration, 'status': 'error'},
                exc_info=True
            )
            
            raise
    
    return wrapper


def log_async_performance(func):
    """Decorator to log async function performance."""
    import asyncio
    import time
    
    async def wrapper(*args, **kwargs):
        logger = get_logger(f'{func.__module__}.{func.__name__}')
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Async function {func.__name__} completed successfully",
                extra={'duration': duration, 'status': 'success'}
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Async function {func.__name__} failed: {e}",
                extra={'duration': duration, 'status': 'error'},
                exc_info=True
            )
            
            raise
    
    return wrapper


# Convenience functions for common logging patterns
def log_workflow_start(workflow_id: str, config: Dict[str, Any]) -> None:
    """Log workflow start."""
    logger = get_workflow_logger(workflow_id)
    logger.info(f"Workflow started", extra={'config': config, 'status': 'started'})


def log_workflow_complete(workflow_id: str, stats: Dict[str, Any]) -> None:
    """Log workflow completion."""
    logger = get_workflow_logger(workflow_id)
    logger.info(f"Workflow completed", extra={'stats': stats, 'status': 'completed'})


def log_workflow_error(workflow_id: str, error: str) -> None:
    """Log workflow error."""
    logger = get_workflow_logger(workflow_id)
    logger.error(f"Workflow failed: {error}", extra={'status': 'failed'})


def log_post_scraped(reddit_id: str, title: str, subreddit: str, workflow_id: str = None) -> None:
    """Log post scraping."""
    logger = get_post_logger(reddit_id, workflow_id)
    logger.info(
        f"Post scraped from r/{subreddit}",
        extra={'title': title[:100], 'subreddit': subreddit, 'status': 'scraped'}
    )


def log_post_scored(reddit_id: str, score: float, meets_threshold: bool, workflow_id: str = None) -> None:
    """Log post scoring."""
    logger = get_post_logger(reddit_id, workflow_id)
    logger.info(
        f"Post scored: {score:.2f} (threshold: {meets_threshold})",
        extra={'score': score, 'meets_threshold': meets_threshold, 'status': 'scored'}
    )


def log_post_generated(reddit_id: str, tweet_length: int, workflow_id: str = None) -> None:
    """Log content generation."""
    logger = get_post_logger(reddit_id, workflow_id)
    logger.info(
        f"Content generated ({tweet_length} chars)",
        extra={'tweet_length': tweet_length, 'status': 'generated'}
    )


def log_post_posted(reddit_id: str, tweet_id: str, tweet_url: str, workflow_id: str = None) -> None:
    """Log tweet posting."""
    logger = get_post_logger(reddit_id, workflow_id)
    logger.info(
        f"Tweet posted: {tweet_url}",
        extra={'tweet_id': tweet_id, 'tweet_url': tweet_url, 'status': 'posted'}
    )


def log_metrics_collected(reddit_id: str, likes: int, retweets: int, workflow_id: str = None) -> None:
    """Log metrics collection."""
    logger = get_post_logger(reddit_id, workflow_id)
    logger.info(
        f"Metrics collected: {likes} likes, {retweets} retweets",
        extra={'likes': likes, 'retweets': retweets, 'status': 'metrics_collected'}
    )


# Initialize logging when module is imported
try:
    setup_logging()
except Exception as e:
    # Fallback to basic logging if setup fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.getLogger(__name__).error(f"Failed to setup logging: {e}")

