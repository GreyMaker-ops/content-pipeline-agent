"""
Monitoring module for health and performance tracking.

This module provides health monitoring, performance metrics,
and alerting capabilities for the social trend agent.
"""

import asyncio
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..trend_graph.database import get_database_health, get_stats_24h

logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """Health metrics data structure."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # System metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    
    # Application metrics
    database_healthy: bool = False
    scheduler_running: bool = False
    
    # Performance metrics
    posts_24h: int = 0
    success_rate_24h: float = 0.0
    avg_workflow_duration: Optional[float] = None
    
    # Error tracking
    recent_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "system": {
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
                "disk_percent": self.disk_percent
            },
            "application": {
                "database_healthy": self.database_healthy,
                "scheduler_running": self.scheduler_running
            },
            "performance": {
                "posts_24h": self.posts_24h,
                "success_rate_24h": self.success_rate_24h,
                "avg_workflow_duration": self.avg_workflow_duration
            },
            "errors": {
                "recent_errors": self.recent_errors,
                "error_count": len(self.recent_errors)
            }
        }


class HealthMonitor:
    """Health monitor for system and application monitoring."""
    
    def __init__(self):
        self.running = False
        self.monitor_task = None
        self.metrics_history: List[HealthMetrics] = []
        self.max_history = 100  # Keep last 100 metrics
        self.check_interval = 60  # Check every minute
        
        # Alert thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "success_rate_24h": 0.8,  # 80% minimum success rate
            "max_errors": 10  # Maximum recent errors
        }
        
        # Alert state
        self.alerts = {
            "high_cpu": False,
            "high_memory": False,
            "high_disk": False,
            "low_success_rate": False,
            "too_many_errors": False,
            "database_unhealthy": False,
            "scheduler_stopped": False
        }
    
    async def start(self) -> None:
        """Start the health monitor."""
        if self.running:
            logger.info("Health monitor is already running")
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitor started")
    
    async def stop(self) -> None:
        """Stop the health monitor."""
        if not self.running:
            logger.info("Health monitor is already stopped")
            return
        
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitor stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = await self._collect_metrics()
                
                # Store metrics
                self._store_metrics(metrics)
                
                # Check alerts
                self._check_alerts(metrics)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _collect_metrics(self) -> HealthMetrics:
        """Collect current health metrics."""
        metrics = HealthMetrics()
        
        try:
            # System metrics
            metrics.cpu_percent = psutil.cpu_percent(interval=1)
            metrics.memory_percent = psutil.virtual_memory().percent
            metrics.disk_percent = psutil.disk_usage('/').percent
            
            # Database health
            metrics.database_healthy = await get_database_health()
            
            # Scheduler status (import here to avoid circular imports)
            from .scheduler import scheduler_manager
            metrics.scheduler_running = scheduler_manager.is_running()
            
            # Performance metrics
            try:
                stats_24h = await get_stats_24h()
                metrics.posts_24h = stats_24h.get("total_posted", 0)
                metrics.success_rate_24h = stats_24h.get("posting_success_rate", 0.0)
                metrics.avg_workflow_duration = stats_24h.get("avg_workflow_duration")
            except Exception as e:
                logger.warning(f"Error collecting performance metrics: {e}")
            
            # Recent errors (simplified - in production, you'd track actual errors)
            metrics.recent_errors = self._get_recent_errors()
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
        
        return metrics
    
    def _get_recent_errors(self) -> List[str]:
        """Get recent error messages (simplified implementation)."""
        # In a real implementation, you'd collect actual error logs
        # For now, return empty list
        return []
    
    def _store_metrics(self, metrics: HealthMetrics) -> None:
        """Store metrics in history."""
        self.metrics_history.append(metrics)
        
        # Keep only recent metrics
        if len(self.metrics_history) > self.max_history:
            self.metrics_history = self.metrics_history[-self.max_history:]
    
    def _check_alerts(self, metrics: HealthMetrics) -> None:
        """Check for alert conditions."""
        # CPU alert
        if metrics.cpu_percent > self.thresholds["cpu_percent"]:
            if not self.alerts["high_cpu"]:
                self.alerts["high_cpu"] = True
                logger.warning(f"High CPU usage alert: {metrics.cpu_percent}%")
        else:
            if self.alerts["high_cpu"]:
                self.alerts["high_cpu"] = False
                logger.info("High CPU usage alert cleared")
        
        # Memory alert
        if metrics.memory_percent > self.thresholds["memory_percent"]:
            if not self.alerts["high_memory"]:
                self.alerts["high_memory"] = True
                logger.warning(f"High memory usage alert: {metrics.memory_percent}%")
        else:
            if self.alerts["high_memory"]:
                self.alerts["high_memory"] = False
                logger.info("High memory usage alert cleared")
        
        # Disk alert
        if metrics.disk_percent > self.thresholds["disk_percent"]:
            if not self.alerts["high_disk"]:
                self.alerts["high_disk"] = True
                logger.warning(f"High disk usage alert: {metrics.disk_percent}%")
        else:
            if self.alerts["high_disk"]:
                self.alerts["high_disk"] = False
                logger.info("High disk usage alert cleared")
        
        # Success rate alert
        if metrics.success_rate_24h < self.thresholds["success_rate_24h"]:
            if not self.alerts["low_success_rate"]:
                self.alerts["low_success_rate"] = True
                logger.warning(f"Low success rate alert: {metrics.success_rate_24h:.2%}")
        else:
            if self.alerts["low_success_rate"]:
                self.alerts["low_success_rate"] = False
                logger.info("Low success rate alert cleared")
        
        # Database health alert
        if not metrics.database_healthy:
            if not self.alerts["database_unhealthy"]:
                self.alerts["database_unhealthy"] = True
                logger.error("Database unhealthy alert")
        else:
            if self.alerts["database_unhealthy"]:
                self.alerts["database_unhealthy"] = False
                logger.info("Database unhealthy alert cleared")
        
        # Scheduler alert
        if not metrics.scheduler_running:
            if not self.alerts["scheduler_stopped"]:
                self.alerts["scheduler_stopped"] = True
                logger.error("Scheduler stopped alert")
        else:
            if self.alerts["scheduler_stopped"]:
                self.alerts["scheduler_stopped"] = False
                logger.info("Scheduler stopped alert cleared")
        
        # Error count alert
        error_count = len(metrics.recent_errors)
        if error_count > self.thresholds["max_errors"]:
            if not self.alerts["too_many_errors"]:
                self.alerts["too_many_errors"] = True
                logger.warning(f"Too many errors alert: {error_count} errors")
        else:
            if self.alerts["too_many_errors"]:
                self.alerts["too_many_errors"] = False
                logger.info("Too many errors alert cleared")
    
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self.running
    
    def get_current_metrics(self) -> Optional[HealthMetrics]:
        """Get the most recent metrics."""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_metrics_history(self, hours: int = 1) -> List[HealthMetrics]:
        """Get metrics history for the specified time period."""
        if not self.metrics_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            metrics for metrics in self.metrics_history
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_alerts(self) -> Dict[str, bool]:
        """Get current alert status."""
        return self.alerts.copy()
    
    def get_active_alerts(self) -> List[str]:
        """Get list of active alerts."""
        return [alert_name for alert_name, active in self.alerts.items() if active]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}"
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {"error": str(e)}
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the specified time period."""
        metrics_list = self.get_metrics_history(hours)
        
        if not metrics_list:
            return {
                "period_hours": hours,
                "data_points": 0,
                "summary": "No data available"
            }
        
        # Calculate averages
        avg_cpu = sum(m.cpu_percent for m in metrics_list) / len(metrics_list)
        avg_memory = sum(m.memory_percent for m in metrics_list) / len(metrics_list)
        avg_disk = sum(m.disk_percent for m in metrics_list) / len(metrics_list)
        
        # Calculate uptime percentage
        healthy_checks = sum(1 for m in metrics_list if m.database_healthy and m.scheduler_running)
        uptime_percentage = healthy_checks / len(metrics_list) * 100
        
        return {
            "period_hours": hours,
            "data_points": len(metrics_list),
            "averages": {
                "cpu_percent": round(avg_cpu, 2),
                "memory_percent": round(avg_memory, 2),
                "disk_percent": round(avg_disk, 2)
            },
            "uptime_percentage": round(uptime_percentage, 2),
            "alert_summary": {
                "total_alerts": len(self.get_active_alerts()),
                "active_alerts": self.get_active_alerts()
            }
        }
    
    def update_thresholds(self, new_thresholds: Dict[str, float]) -> None:
        """Update alert thresholds."""
        for key, value in new_thresholds.items():
            if key in self.thresholds:
                self.thresholds[key] = value
                logger.info(f"Updated threshold {key} to {value}")
            else:
                logger.warning(f"Unknown threshold key: {key}")


# Global health monitor instance
health_monitor = HealthMonitor()


# Utility functions
async def start_health_monitor() -> Dict[str, Any]:
    """Start the health monitor."""
    try:
        await health_monitor.start()
        return {
            "success": True,
            "message": "Health monitor started successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


async def stop_health_monitor() -> Dict[str, Any]:
    """Stop the health monitor."""
    try:
        await health_monitor.stop()
        return {
            "success": True,
            "message": "Health monitor stopped successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


def get_health_status() -> Dict[str, Any]:
    """Get current health status."""
    current_metrics = health_monitor.get_current_metrics()
    
    if not current_metrics:
        return {
            "status": "unknown",
            "message": "No metrics available"
        }
    
    active_alerts = health_monitor.get_active_alerts()
    
    if active_alerts:
        status = "unhealthy"
        message = f"Active alerts: {', '.join(active_alerts)}"
    else:
        status = "healthy"
        message = "All systems operational"
    
    return {
        "status": status,
        "message": message,
        "metrics": current_metrics.to_dict(),
        "alerts": health_monitor.get_alerts(),
        "system_info": health_monitor.get_system_info()
    }


def get_performance_report(hours: int = 24) -> Dict[str, Any]:
    """Get performance report."""
    return health_monitor.get_performance_summary(hours)


def update_alert_thresholds(thresholds: Dict[str, float]) -> Dict[str, Any]:
    """Update alert thresholds."""
    try:
        health_monitor.update_thresholds(thresholds)
        return {
            "success": True,
            "message": "Thresholds updated successfully",
            "new_thresholds": health_monitor.thresholds
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

