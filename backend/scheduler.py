"""
Scheduler module for periodic workflow execution.

This module uses APScheduler to run the trend analysis workflow
at regular intervals and collect metrics.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from ..trend_graph.config import get_app_config
from ..trend_graph.graph import run_trend_analysis
from ..trend_graph.nodes.metrics import collect_metrics_node
from ..trend_graph.database import create_metrics_snapshot, cleanup_old_records

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manager for scheduled tasks using APScheduler."""
    
    def __init__(self):
        self.scheduler = None
        self.app_config = get_app_config()
        self.running = False
        
        # Job statistics
        self.job_stats = {
            "workflow_runs": 0,
            "workflow_successes": 0,
            "workflow_failures": 0,
            "metrics_collections": 0,
            "metrics_successes": 0,
            "metrics_failures": 0,
            "last_workflow_run": None,
            "last_metrics_collection": None,
            "last_cleanup": None
        }
    
    async def start(self) -> None:
        """Start the scheduler with configured jobs."""
        if self.running:
            logger.info("Scheduler is already running")
            return
        
        try:
            # Create scheduler
            self.scheduler = AsyncIOScheduler()
            
            # Add event listeners
            self.scheduler.add_listener(
                self._job_executed_listener,
                EVENT_JOB_EXECUTED
            )
            self.scheduler.add_listener(
                self._job_error_listener,
                EVENT_JOB_ERROR
            )
            
            # Add jobs
            await self._add_jobs()
            
            # Start scheduler
            self.scheduler.start()
            self.running = True
            
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self.running:
            logger.info("Scheduler is already stopped")
            return
        
        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=True)
                self.scheduler = None
            
            self.running = False
            logger.info("Scheduler stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            raise
    
    async def _add_jobs(self) -> None:
        """Add scheduled jobs to the scheduler."""
        # Main workflow job - runs every interval_minutes
        self.scheduler.add_job(
            func=self._run_workflow_job,
            trigger=IntervalTrigger(minutes=self.app_config.interval_minutes),
            id="workflow_job",
            name="Trend Analysis Workflow",
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,    # Combine missed runs
            misfire_grace_time=300  # 5 minutes grace time
        )
        
        # Metrics collection job - runs every hour
        self.scheduler.add_job(
            func=self._collect_metrics_job,
            trigger=IntervalTrigger(hours=1),
            id="metrics_job",
            name="Metrics Collection",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600  # 10 minutes grace time
        )
        
        # Metrics snapshot job - runs every 6 hours
        self.scheduler.add_job(
            func=self._create_metrics_snapshot_job,
            trigger=IntervalTrigger(hours=6),
            id="snapshot_job",
            name="Metrics Snapshot",
            max_instances=1,
            coalesce=True
        )
        
        # Cleanup job - runs daily at 2 AM
        self.scheduler.add_job(
            func=self._cleanup_job,
            trigger=CronTrigger(hour=2, minute=0),
            id="cleanup_job",
            name="Database Cleanup",
            max_instances=1,
            coalesce=True
        )
        
        logger.info("Scheduled jobs added successfully")
    
    async def _run_workflow_job(self) -> None:
        """Scheduled job to run the trend analysis workflow."""
        job_id = "workflow_job"
        logger.info(f"Starting scheduled {job_id}")
        
        try:
            self.job_stats["workflow_runs"] += 1
            self.job_stats["last_workflow_run"] = datetime.utcnow().isoformat()
            
            # Run the workflow
            result = await run_trend_analysis()
            
            if result.get("success"):
                self.job_stats["workflow_successes"] += 1
                logger.info(f"Scheduled {job_id} completed successfully: {result}")
            else:
                self.job_stats["workflow_failures"] += 1
                logger.error(f"Scheduled {job_id} failed: {result}")
            
        except Exception as e:
            self.job_stats["workflow_failures"] += 1
            logger.error(f"Error in scheduled {job_id}: {e}")
            raise
    
    async def _collect_metrics_job(self) -> None:
        """Scheduled job to collect Twitter metrics."""
        job_id = "metrics_job"
        logger.info(f"Starting scheduled {job_id}")
        
        try:
            self.job_stats["metrics_collections"] += 1
            self.job_stats["last_metrics_collection"] = datetime.utcnow().isoformat()
            
            # Collect metrics
            result = await collect_metrics_node()
            
            if result.get("success", True):  # Default to success if not specified
                self.job_stats["metrics_successes"] += 1
                logger.info(f"Scheduled {job_id} completed successfully: {result}")
            else:
                self.job_stats["metrics_failures"] += 1
                logger.error(f"Scheduled {job_id} failed: {result}")
            
        except Exception as e:
            self.job_stats["metrics_failures"] += 1
            logger.error(f"Error in scheduled {job_id}: {e}")
            raise
    
    async def _create_metrics_snapshot_job(self) -> None:
        """Scheduled job to create metrics snapshots."""
        job_id = "snapshot_job"
        logger.info(f"Starting scheduled {job_id}")
        
        try:
            # Create metrics snapshot
            snapshot = await create_metrics_snapshot()
            logger.info(f"Scheduled {job_id} completed: created snapshot {snapshot.id}")
            
        except Exception as e:
            logger.error(f"Error in scheduled {job_id}: {e}")
            raise
    
    async def _cleanup_job(self) -> None:
        """Scheduled job to clean up old database records."""
        job_id = "cleanup_job"
        logger.info(f"Starting scheduled {job_id}")
        
        try:
            self.job_stats["last_cleanup"] = datetime.utcnow().isoformat()
            
            # Clean up old records (keep 30 days)
            await cleanup_old_records(days=30)
            logger.info(f"Scheduled {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error in scheduled {job_id}: {e}")
            raise
    
    def _job_executed_listener(self, event) -> None:
        """Listener for successful job executions."""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error_listener(self, event) -> None:
        """Listener for job execution errors."""
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.running and self.scheduler is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics."""
        if not self.scheduler:
            return {
                "running": False,
                "jobs": [],
                "statistics": self.job_stats
            }
        
        # Get job information
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
                "max_instances": job.max_instances,
                "coalesce": job.coalesce
            })
        
        return {
            "running": self.running,
            "jobs": jobs,
            "statistics": self.job_stats,
            "scheduler_state": self.scheduler.state if self.scheduler else None
        }
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get job execution statistics."""
        return self.job_stats.copy()
    
    async def run_job_now(self, job_id: str) -> Dict[str, Any]:
        """Manually trigger a specific job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler is not running")
        
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Trigger the job
            job.modify(next_run_time=datetime.now())
            
            return {
                "success": True,
                "message": f"Job {job_id} triggered successfully",
                "job_name": job.name
            }
            
        except Exception as e:
            logger.error(f"Error triggering job {job_id}: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def pause_job(self, job_id: str) -> Dict[str, Any]:
        """Pause a specific job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler is not running")
        
        try:
            self.scheduler.pause_job(job_id)
            
            return {
                "success": True,
                "message": f"Job {job_id} paused successfully"
            }
            
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def resume_job(self, job_id: str) -> Dict[str, Any]:
        """Resume a specific job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler is not running")
        
        try:
            self.scheduler.resume_job(job_id)
            
            return {
                "success": True,
                "message": f"Job {job_id} resumed successfully"
            }
            
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_next_run_times(self) -> Dict[str, Optional[str]]:
        """Get next run times for all jobs."""
        if not self.scheduler:
            return {}
        
        next_runs = {}
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            next_runs[job.id] = next_run.isoformat() if next_run else None
        
        return next_runs


# Global scheduler manager instance
scheduler_manager = SchedulerManager()


# Utility functions
async def start_scheduler() -> Dict[str, Any]:
    """Start the scheduler."""
    try:
        await scheduler_manager.start()
        return {
            "success": True,
            "message": "Scheduler started successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


async def stop_scheduler() -> Dict[str, Any]:
    """Stop the scheduler."""
    try:
        await scheduler_manager.stop()
        return {
            "success": True,
            "message": "Scheduler stopped successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


def get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status."""
    return scheduler_manager.get_status()


async def trigger_job(job_id: str) -> Dict[str, Any]:
    """Manually trigger a job."""
    return await scheduler_manager.run_job_now(job_id)


def get_job_statistics() -> Dict[str, Any]:
    """Get job execution statistics."""
    return scheduler_manager.get_job_stats()

