"""
Backend package for the social trend agent.

This package provides the FastAPI backend with scheduling,
monitoring, and API endpoints for the social trend agent.
"""

from .app import app
from .scheduler import scheduler_manager, start_scheduler, stop_scheduler
from .monitoring import health_monitor, get_health_status

__all__ = [
    "app",
    "scheduler_manager",
    "start_scheduler", 
    "stop_scheduler",
    "health_monitor",
    "get_health_status"
]

