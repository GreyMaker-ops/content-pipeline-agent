"""
FastAPI backend for the social trend agent.

This module provides REST API endpoints for controlling and monitoring
the social trend analysis workflow.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..trend_graph.config import get_app_config
from ..trend_graph.database import init_database, close_database, get_database_health
from ..trend_graph.graph import run_trend_analysis, get_workflow_status, workflow
from ..trend_graph.nodes.metrics import collect_metrics_node
from .scheduler import scheduler_manager
from .monitoring import health_monitor

logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class WorkflowRequest(BaseModel):
    """Request model for starting a workflow."""
    min_score: Optional[float] = None
    subreddits: Optional[List[str]] = None


class WorkflowResponse(BaseModel):
    """Response model for workflow operations."""
    success: bool
    message: str
    workflow_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    """Response model for status endpoints."""
    status: str
    timestamp: str
    data: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting social trend agent backend")
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized")
        
        # Start scheduler
        await scheduler_manager.start()
        logger.info("Scheduler started")
        
        # Start health monitor
        await health_monitor.start()
        logger.info("Health monitor started")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down social trend agent backend")
        
        # Stop health monitor
        await health_monitor.stop()
        logger.info("Health monitor stopped")
        
        # Stop scheduler
        await scheduler_manager.stop()
        logger.info("Scheduler stopped")
        
        # Close database
        await close_database()
        logger.info("Database closed")


# Create FastAPI app
app = FastAPI(
    title="Social Trend Agent API",
    description="API for controlling and monitoring the social trend analysis workflow",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=StatusResponse)
async def root():
    """Root endpoint with basic API information."""
    return StatusResponse(
        status="running",
        timestamp=datetime.utcnow().isoformat(),
        data={
            "service": "Social Trend Agent API",
            "version": "1.0.0",
            "description": "AI-powered social trend analysis and Twitter automation"
        }
    )


@app.get("/health", response_model=StatusResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check database health
        db_healthy = await get_database_health()
        
        # Check scheduler health
        scheduler_healthy = scheduler_manager.is_running()
        
        # Check health monitor
        monitor_healthy = health_monitor.is_running()
        
        overall_healthy = db_healthy and scheduler_healthy and monitor_healthy
        
        return StatusResponse(
            status="healthy" if overall_healthy else "unhealthy",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "database": "healthy" if db_healthy else "unhealthy",
                "scheduler": "running" if scheduler_healthy else "stopped",
                "monitor": "running" if monitor_healthy else "stopped",
                "overall": "healthy" if overall_healthy else "unhealthy"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return StatusResponse(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "error": str(e)
            }
        )


@app.post("/workflow/run", response_model=WorkflowResponse)
async def run_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Start a new trend analysis workflow."""
    try:
        logger.info(f"Starting workflow with request: {request}")
        
        # Run workflow in background
        background_tasks.add_task(
            _run_workflow_background,
            request.min_score,
            request.subreddits
        )
        
        return WorkflowResponse(
            success=True,
            message="Workflow started successfully",
            data={
                "min_score": request.min_score,
                "subreddits": request.subreddits,
                "started_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_workflow_background(min_score: Optional[float], subreddits: Optional[List[str]]):
    """Background task to run the workflow."""
    try:
        result = await run_trend_analysis(min_score=min_score, subreddits=subreddits)
        logger.info(f"Background workflow completed: {result}")
    except Exception as e:
        logger.error(f"Background workflow failed: {e}")


@app.get("/workflow/status/{workflow_id}", response_model=StatusResponse)
async def get_workflow_status_endpoint(workflow_id: str):
    """Get status of a specific workflow."""
    try:
        status = await get_workflow_status(workflow_id)
        
        if not status.get("found"):
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow/recent", response_model=StatusResponse)
async def get_recent_workflows():
    """Get recent workflow executions."""
    try:
        from ..trend_graph.database import get_recent_workflows
        
        workflows = await get_recent_workflows(limit=10)
        workflow_data = [workflow.to_dict() for workflow in workflows]
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "workflows": workflow_data,
                "count": len(workflow_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting recent workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/metrics/collect", response_model=WorkflowResponse)
async def collect_metrics(background_tasks: BackgroundTasks):
    """Manually trigger metrics collection."""
    try:
        # Run metrics collection in background
        background_tasks.add_task(_collect_metrics_background)
        
        return WorkflowResponse(
            success=True,
            message="Metrics collection started",
            data={
                "started_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting metrics collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _collect_metrics_background():
    """Background task to collect metrics."""
    try:
        result = await collect_metrics_node()
        logger.info(f"Background metrics collection completed: {result}")
    except Exception as e:
        logger.error(f"Background metrics collection failed: {e}")


@app.get("/metrics/summary", response_model=StatusResponse)
async def get_metrics_summary():
    """Get metrics summary."""
    try:
        from ..trend_graph.nodes.metrics import get_metrics_summary
        
        summary = await get_metrics_summary()
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=summary
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/status", response_model=StatusResponse)
async def get_scheduler_status():
    """Get scheduler status."""
    try:
        status = scheduler_manager.get_status()
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=status
        )
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/start", response_model=WorkflowResponse)
async def start_scheduler():
    """Start the scheduler."""
    try:
        if scheduler_manager.is_running():
            return WorkflowResponse(
                success=True,
                message="Scheduler is already running"
            )
        
        await scheduler_manager.start()
        
        return WorkflowResponse(
            success=True,
            message="Scheduler started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/stop", response_model=WorkflowResponse)
async def stop_scheduler():
    """Stop the scheduler."""
    try:
        if not scheduler_manager.is_running():
            return WorkflowResponse(
                success=True,
                message="Scheduler is already stopped"
            )
        
        await scheduler_manager.stop()
        
        return WorkflowResponse(
            success=True,
            message="Scheduler stopped successfully"
        )
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/24h", response_model=StatusResponse)
async def get_24h_stats():
    """Get 24-hour statistics."""
    try:
        from ..trend_graph.database import get_stats_24h
        
        stats = await get_stats_24h()
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting 24h stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/posts/recent", response_model=StatusResponse)
async def get_recent_posts():
    """Get recent posts."""
    try:
        from ..trend_graph.database import get_recent_posts
        
        posts = await get_recent_posts(hours=24, limit=50)
        post_data = [post.to_dict() for post in posts]
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "posts": post_data,
                "count": len(post_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting recent posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/posts/successful", response_model=StatusResponse)
async def get_successful_posts():
    """Get successfully posted tweets."""
    try:
        from ..trend_graph.database import get_successful_posts
        
        posts = await get_successful_posts(hours=24, limit=50)
        post_data = [post.to_dict() for post in posts]
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "posts": post_data,
                "count": len(post_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting successful posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config", response_model=StatusResponse)
async def get_config():
    """Get current configuration (excluding sensitive data)."""
    try:
        from ..trend_graph.config import get_config
        
        config = get_config()
        config_dict = config.to_dict()
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=config_dict
        )
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow/schema", response_model=StatusResponse)
async def get_workflow_schema():
    """Get workflow schema information."""
    try:
        schema = workflow.get_workflow_schema()
        
        return StatusResponse(
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            data=schema
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    config = get_app_config()
    
    uvicorn.run(
        "backend.app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )

