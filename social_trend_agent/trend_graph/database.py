"""
Database initialization and management for the social trend agent.

This module handles Tortoise ORM setup, database connections,
and provides utility functions for database operations.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from tortoise import Tortoise, run_async
from tortoise.exceptions import IntegrityError

from .config import get_database_config
from .models import PostRecord, WorkflowRecord, MetricsSnapshot
from .state import PostStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database manager for handling Tortoise ORM operations."""
    
    def __init__(self):
        self.initialized = False
    
    async def init_db(self) -> None:
        """Initialize database connection and create tables."""
        if self.initialized:
            return
        
        db_config = get_database_config()
        
        await Tortoise.init(
            db_url=db_config.url,
            modules={'models': ['trend_graph.models']}
        )
        
        # Generate schemas (create tables if they don't exist)
        await Tortoise.generate_schemas()
        
        self.initialized = True
        logger.info("Database initialized successfully")
    
    async def close_db(self) -> None:
        """Close database connections."""
        if self.initialized:
            await Tortoise.close_connections()
            self.initialized = False
            logger.info("Database connections closed")
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            # Simple query to test connection
            await PostRecord.all().limit(1)
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def init_database() -> None:
    """Initialize the database."""
    await db_manager.init_db()


async def close_database() -> None:
    """Close database connections."""
    await db_manager.close_db()


async def get_database_health() -> bool:
    """Check database health."""
    return await db_manager.health_check()


# Post record operations
async def save_post_record(
    reddit_id: str,
    title: str,
    url: str,
    subreddit: str,
    permalink: str,
    upvotes: int,
    num_comments: int,
    upvote_ratio: float,
    created_utc: float,
    workflow_id: Optional[str] = None
) -> PostRecord:
    """Save a new post record to the database."""
    try:
        post_record = await PostRecord.create(
            reddit_id=reddit_id,
            title=title,
            url=url,
            subreddit=subreddit,
            permalink=permalink,
            upvotes=upvotes,
            num_comments=num_comments,
            upvote_ratio=upvote_ratio,
            created_utc=created_utc,
            workflow_id=workflow_id
        )
        logger.info(f"Saved post record: {reddit_id}")
        return post_record
    except IntegrityError:
        # Post already exists, return existing record
        post_record = await PostRecord.get(reddit_id=reddit_id)
        logger.info(f"Post record already exists: {reddit_id}")
        return post_record


async def get_post_record(reddit_id: str) -> Optional[PostRecord]:
    """Get a post record by Reddit ID."""
    try:
        return await PostRecord.get(reddit_id=reddit_id)
    except:
        return None


async def update_post_score(reddit_id: str, score: float, meets_threshold: bool, min_score: float) -> None:
    """Update post with virality score."""
    post_record = await PostRecord.get(reddit_id=reddit_id)
    post_record.mark_scored(score, meets_threshold, min_score)
    await post_record.save()
    logger.info(f"Updated post score: {reddit_id} -> {score}")


async def update_post_content(reddit_id: str, tweet_text: str) -> None:
    """Update post with generated tweet content."""
    post_record = await PostRecord.get(reddit_id=reddit_id)
    post_record.mark_generated(tweet_text)
    await post_record.save()
    logger.info(f"Updated post content: {reddit_id}")


async def update_post_posted(reddit_id: str, tweet_id: str, tweet_url: str) -> None:
    """Update post as successfully posted to Twitter."""
    post_record = await PostRecord.get(reddit_id=reddit_id)
    post_record.mark_posted(tweet_id, tweet_url)
    await post_record.save()
    logger.info(f"Updated post as posted: {reddit_id} -> {tweet_url}")


async def update_post_metrics(reddit_id: str, likes: int, retweets: int, replies: int = 0) -> None:
    """Update post with Twitter metrics."""
    post_record = await PostRecord.get(reddit_id=reddit_id)
    post_record.mark_metrics_collected(likes, retweets, replies)
    await post_record.save()
    logger.info(f"Updated post metrics: {reddit_id} -> {likes} likes, {retweets} retweets")


async def update_post_failed(reddit_id: str, error_message: str) -> None:
    """Mark post as failed."""
    post_record = await PostRecord.get(reddit_id=reddit_id)
    post_record.mark_failed(error_message)
    await post_record.save()
    logger.info(f"Marked post as failed: {reddit_id} -> {error_message}")


# Workflow record operations
async def create_workflow_record(
    workflow_id: str,
    min_score: float,
    subreddits: List[str]
) -> WorkflowRecord:
    """Create a new workflow record."""
    workflow_record = await WorkflowRecord.create(
        workflow_id=workflow_id,
        min_score=min_score,
        subreddits=subreddits
    )
    logger.info(f"Created workflow record: {workflow_id}")
    return workflow_record


async def get_workflow_record(workflow_id: str) -> Optional[WorkflowRecord]:
    """Get a workflow record by ID."""
    try:
        return await WorkflowRecord.get(workflow_id=workflow_id)
    except:
        return None


async def update_workflow_step(workflow_id: str, step_name: str) -> None:
    """Update workflow current step."""
    workflow_record = await WorkflowRecord.get(workflow_id=workflow_id)
    workflow_record.update_step(step_name)
    await workflow_record.save()


async def update_workflow_stats(
    workflow_id: str,
    scraped: int = 0,
    scored: int = 0,
    generated: int = 0,
    posted: int = 0,
    failed: int = 0
) -> None:
    """Update workflow statistics."""
    workflow_record = await WorkflowRecord.get(workflow_id=workflow_id)
    workflow_record.update_stats(scraped, scored, generated, posted, failed)
    await workflow_record.save()


async def complete_workflow(workflow_id: str, success: bool = True) -> None:
    """Mark workflow as completed."""
    workflow_record = await WorkflowRecord.get(workflow_id=workflow_id)
    workflow_record.complete_workflow(success)
    await workflow_record.save()
    logger.info(f"Completed workflow: {workflow_id} -> success: {success}")


async def fail_workflow(workflow_id: str, error_message: str) -> None:
    """Mark workflow as failed."""
    workflow_record = await WorkflowRecord.get(workflow_id=workflow_id)
    workflow_record.fail_workflow(error_message)
    await workflow_record.save()
    logger.info(f"Failed workflow: {workflow_id} -> {error_message}")


# Query operations
async def get_recent_posts(hours: int = 24, limit: int = 100) -> List[PostRecord]:
    """Get recent posts within specified hours."""
    since = datetime.utcnow() - timedelta(hours=hours)
    return await PostRecord.filter(scraped_at__gte=since).order_by('-scraped_at').limit(limit)


async def get_posts_by_status(status: PostStatus, limit: int = 100) -> List[PostRecord]:
    """Get posts by status."""
    return await PostRecord.filter(status=status).order_by('-scraped_at').limit(limit)


async def get_posts_by_subreddit(subreddit: str, hours: int = 24, limit: int = 100) -> List[PostRecord]:
    """Get posts from a specific subreddit."""
    since = datetime.utcnow() - timedelta(hours=hours)
    return await PostRecord.filter(
        subreddit=subreddit,
        scraped_at__gte=since
    ).order_by('-scraped_at').limit(limit)


async def get_successful_posts(hours: int = 24, limit: int = 100) -> List[PostRecord]:
    """Get successfully posted tweets."""
    since = datetime.utcnow() - timedelta(hours=hours)
    return await PostRecord.filter(
        status=PostStatus.POSTED,
        posted_at__gte=since
    ).order_by('-posted_at').limit(limit)


async def get_posts_needing_metrics() -> List[PostRecord]:
    """Get posts that need metrics collection (posted > 1 hour ago)."""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    return await PostRecord.filter(
        status=PostStatus.POSTED,
        posted_at__lte=one_hour_ago,
        metrics_collected_at__isnull=True
    ).order_by('posted_at')


async def get_recent_workflows(limit: int = 10) -> List[WorkflowRecord]:
    """Get recent workflow records."""
    return await WorkflowRecord.all().order_by('-started_at').limit(limit)


async def get_running_workflows() -> List[WorkflowRecord]:
    """Get currently running workflows."""
    return await WorkflowRecord.filter(completed_at__isnull=True).order_by('-started_at')


# Statistics operations
async def get_stats_24h() -> Dict[str, Any]:
    """Get 24-hour statistics."""
    since = datetime.utcnow() - timedelta(hours=24)
    
    total_scraped = await PostRecord.filter(scraped_at__gte=since).count()
    total_posted = await PostRecord.filter(
        status=PostStatus.POSTED,
        posted_at__gte=since
    ).count()
    total_failed = await PostRecord.filter(
        status=PostStatus.FAILED,
        scraped_at__gte=since
    ).count()
    
    # Average virality score
    posts_with_scores = await PostRecord.filter(
        virality_score__isnull=False,
        scored_at__gte=since
    )
    avg_score = None
    if posts_with_scores:
        avg_score = sum(p.virality_score for p in posts_with_scores) / len(posts_with_scores)
    
    # Average engagement
    posts_with_metrics = await PostRecord.filter(
        likes__isnull=False,
        retweets__isnull=False,
        metrics_collected_at__gte=since
    )
    avg_engagement = None
    if posts_with_metrics:
        avg_engagement = sum(p.engagement_rate for p in posts_with_metrics) / len(posts_with_metrics)
    
    # Workflow stats
    workflows = await WorkflowRecord.filter(started_at__gte=since)
    workflow_count = len(workflows)
    avg_duration = None
    if workflows:
        completed_workflows = [w for w in workflows if w.duration_seconds is not None]
        if completed_workflows:
            avg_duration = sum(w.duration_seconds for w in completed_workflows) / len(completed_workflows)
    
    return {
        "total_scraped": total_scraped,
        "total_posted": total_posted,
        "total_failed": total_failed,
        "avg_virality_score": avg_score,
        "avg_engagement": avg_engagement,
        "workflow_runs": workflow_count,
        "avg_workflow_duration": avg_duration,
        "posting_success_rate": total_posted / (total_posted + total_failed) if (total_posted + total_failed) > 0 else 0
    }


async def create_metrics_snapshot() -> MetricsSnapshot:
    """Create a metrics snapshot for the current time."""
    stats = await get_stats_24h()
    
    snapshot = await MetricsSnapshot.create(
        posts_scraped_24h=stats["total_scraped"],
        posts_posted_24h=stats["total_posted"],
        posts_failed_24h=stats["total_failed"],
        avg_virality_score_24h=stats["avg_virality_score"],
        avg_engagement_24h=stats["avg_engagement"],
        workflow_runs_24h=stats["workflow_runs"],
        avg_workflow_duration_24h=stats["avg_workflow_duration"],
        posting_success_rate_24h=stats["posting_success_rate"]
    )
    
    logger.info("Created metrics snapshot")
    return snapshot


# Cleanup operations
async def cleanup_old_records(days: int = 30) -> None:
    """Clean up old records to prevent database bloat."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Delete old post records
    deleted_posts = await PostRecord.filter(scraped_at__lt=cutoff).delete()
    
    # Delete old workflow records
    deleted_workflows = await WorkflowRecord.filter(started_at__lt=cutoff).delete()
    
    # Delete old metrics snapshots (keep more recent ones)
    metrics_cutoff = datetime.utcnow() - timedelta(days=7)
    deleted_metrics = await MetricsSnapshot.filter(timestamp__lt=metrics_cutoff).delete()
    
    logger.info(f"Cleaned up old records: {deleted_posts} posts, {deleted_workflows} workflows, {deleted_metrics} metrics")


# Utility function for running database operations
def run_db_operation(coro):
    """Run a database operation with proper async handling."""
    return run_async(coro)

