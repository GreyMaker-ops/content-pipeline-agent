"""
Database models for the social trend agent.

This module defines Tortoise ORM models for persisting posts, tweets,
and metrics data to SQLite database.
"""

from tortoise.models import Model
from tortoise import fields
from datetime import datetime
from typing import Optional, Dict, Any
from .state import PostStatus


class PostRecord(Model):
    """
    Database model for storing post processing records.
    
    This model stores the complete lifecycle of a post from Reddit
    scraping through Twitter posting and metrics collection.
    """
    
    # Primary key
    id = fields.IntField(primary_key=True)
    
    # Reddit post data
    reddit_id = fields.CharField(max_length=50, unique=True, index=True)
    title = fields.CharField(max_length=500)
    url = fields.CharField(max_length=1000)
    subreddit = fields.CharField(max_length=50, index=True)
    permalink = fields.CharField(max_length=500)
    
    # Reddit metrics
    upvotes = fields.IntField()
    num_comments = fields.IntField()
    upvote_ratio = fields.FloatField()
    created_utc = fields.FloatField()
    
    # Virality scoring
    virality_score = fields.FloatField(null=True)
    meets_threshold = fields.BooleanField(default=False)
    min_score_used = fields.FloatField(null=True)
    
    # Generated content
    tweet_text = fields.CharField(max_length=280, null=True)
    
    # Twitter posting
    tweet_id = fields.CharField(max_length=50, null=True, index=True)
    tweet_url = fields.CharField(max_length=500, null=True)
    
    # Twitter metrics
    likes = fields.IntField(null=True)
    retweets = fields.IntField(null=True)
    replies = fields.IntField(null=True)
    
    # Processing status
    status = fields.CharEnumField(PostStatus, default=PostStatus.RAW, index=True)
    error_message = fields.TextField(null=True)
    
    # Timestamps
    scraped_at = fields.DatetimeField(auto_now_add=True, index=True)
    scored_at = fields.DatetimeField(null=True)
    generated_at = fields.DatetimeField(null=True)
    posted_at = fields.DatetimeField(null=True)
    metrics_collected_at = fields.DatetimeField(null=True)
    
    # Workflow tracking
    workflow_id = fields.CharField(max_length=100, null=True, index=True)
    
    class Meta:
        table = "post_records"
        ordering = ["-scraped_at"]
    
    def __str__(self) -> str:
        return f"PostRecord({self.reddit_id}: {self.title[:50]}...)"
    
    @property
    def age_minutes(self) -> float:
        """Calculate age of post in minutes from creation time."""
        now = datetime.utcnow().timestamp()
        return (now - self.created_utc) / 60.0
    
    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Calculate total processing duration in seconds."""
        if self.posted_at:
            return (self.posted_at - self.scraped_at).total_seconds()
        return None
    
    @property
    def engagement_rate(self) -> Optional[float]:
        """Calculate engagement rate (likes + retweets) if metrics available."""
        if self.likes is not None and self.retweets is not None:
            return self.likes + self.retweets
        return None
    
    def mark_scored(self, score: float, meets_threshold: bool, min_score: float) -> None:
        """Mark post as scored."""
        self.virality_score = score
        self.meets_threshold = meets_threshold
        self.min_score_used = min_score
        self.scored_at = datetime.utcnow()
        if meets_threshold:
            self.status = PostStatus.SCORED
    
    def mark_generated(self, tweet_text: str) -> None:
        """Mark post as having generated content."""
        self.tweet_text = tweet_text
        self.generated_at = datetime.utcnow()
        self.status = PostStatus.GENERATED
    
    def mark_posted(self, tweet_id: str, tweet_url: str) -> None:
        """Mark post as successfully posted to Twitter."""
        self.tweet_id = tweet_id
        self.tweet_url = tweet_url
        self.posted_at = datetime.utcnow()
        self.status = PostStatus.POSTED
    
    def mark_metrics_collected(self, likes: int, retweets: int, replies: int = 0) -> None:
        """Mark metrics as collected."""
        self.likes = likes
        self.retweets = retweets
        self.replies = replies
        self.metrics_collected_at = datetime.utcnow()
        self.status = PostStatus.METRICS_COLLECTED
    
    def mark_failed(self, error_message: str) -> None:
        """Mark post as failed."""
        self.error_message = error_message
        self.status = PostStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "reddit_id": self.reddit_id,
            "title": self.title,
            "url": self.url,
            "subreddit": self.subreddit,
            "permalink": self.permalink,
            "upvotes": self.upvotes,
            "num_comments": self.num_comments,
            "upvote_ratio": self.upvote_ratio,
            "created_utc": self.created_utc,
            "age_minutes": self.age_minutes,
            "virality_score": self.virality_score,
            "meets_threshold": self.meets_threshold,
            "min_score_used": self.min_score_used,
            "tweet_text": self.tweet_text,
            "tweet_id": self.tweet_id,
            "tweet_url": self.tweet_url,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "status": self.status.value if self.status else None,
            "error_message": self.error_message,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "metrics_collected_at": self.metrics_collected_at.isoformat() if self.metrics_collected_at else None,
            "workflow_id": self.workflow_id,
            "processing_duration_seconds": self.processing_duration_seconds,
            "engagement_rate": self.engagement_rate
        }


class WorkflowRecord(Model):
    """
    Database model for storing workflow execution records.
    
    This model tracks each execution of the trend analysis workflow,
    including timing, statistics, and error information.
    """
    
    # Primary key
    id = fields.IntField(primary_key=True)
    
    # Workflow identification
    workflow_id = fields.CharField(max_length=100, unique=True, index=True)
    
    # Timing
    started_at = fields.DatetimeField(auto_now_add=True, index=True)
    completed_at = fields.DatetimeField(null=True)
    duration_seconds = fields.FloatField(null=True)
    
    # Configuration
    min_score = fields.FloatField()
    subreddits = fields.JSONField()  # List of subreddit names
    
    # Statistics
    total_scraped = fields.IntField(default=0)
    total_scored = fields.IntField(default=0)
    total_generated = fields.IntField(default=0)
    total_posted = fields.IntField(default=0)
    total_failed = fields.IntField(default=0)
    
    # Status
    current_step = fields.CharField(max_length=50, default="starting")
    error_message = fields.TextField(null=True)
    success = fields.BooleanField(default=False)
    
    class Meta:
        table = "workflow_records"
        ordering = ["-started_at"]
    
    def __str__(self) -> str:
        return f"WorkflowRecord({self.workflow_id}: {self.current_step})"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of posted tweets."""
        total_attempts = self.total_posted + self.total_failed
        if total_attempts == 0:
            return 0.0
        return self.total_posted / total_attempts
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.completed_at is None
    
    def complete_workflow(self, success: bool = True) -> None:
        """Mark workflow as completed."""
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.success = success
        self.current_step = "completed" if success else "failed"
    
    def update_step(self, step_name: str) -> None:
        """Update current workflow step."""
        self.current_step = step_name
    
    def update_stats(self, scraped: int = 0, scored: int = 0, generated: int = 0, 
                    posted: int = 0, failed: int = 0) -> None:
        """Update workflow statistics."""
        self.total_scraped += scraped
        self.total_scored += scored
        self.total_generated += generated
        self.total_posted += posted
        self.total_failed += failed
    
    def fail_workflow(self, error_message: str) -> None:
        """Mark workflow as failed."""
        self.error_message = error_message
        self.complete_workflow(success=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "min_score": self.min_score,
            "subreddits": self.subreddits,
            "total_scraped": self.total_scraped,
            "total_scored": self.total_scored,
            "total_generated": self.total_generated,
            "total_posted": self.total_posted,
            "total_failed": self.total_failed,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "success": self.success,
            "success_rate": self.success_rate,
            "is_running": self.is_running
        }


class MetricsSnapshot(Model):
    """
    Database model for storing periodic metrics snapshots.
    
    This model stores aggregated metrics for monitoring and analysis.
    """
    
    # Primary key
    id = fields.IntField(primary_key=True)
    
    # Timestamp
    timestamp = fields.DatetimeField(auto_now_add=True, index=True)
    
    # Aggregated metrics (last 24 hours)
    posts_scraped_24h = fields.IntField(default=0)
    posts_posted_24h = fields.IntField(default=0)
    posts_failed_24h = fields.IntField(default=0)
    avg_virality_score_24h = fields.FloatField(null=True)
    avg_engagement_24h = fields.FloatField(null=True)
    
    # System metrics
    workflow_runs_24h = fields.IntField(default=0)
    avg_workflow_duration_24h = fields.FloatField(null=True)
    
    # Success rates
    posting_success_rate_24h = fields.FloatField(null=True)
    threshold_pass_rate_24h = fields.FloatField(null=True)
    
    class Meta:
        table = "metrics_snapshots"
        ordering = ["-timestamp"]
    
    def __str__(self) -> str:
        return f"MetricsSnapshot({self.timestamp}: {self.posts_posted_24h} posted)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "posts_scraped_24h": self.posts_scraped_24h,
            "posts_posted_24h": self.posts_posted_24h,
            "posts_failed_24h": self.posts_failed_24h,
            "avg_virality_score_24h": self.avg_virality_score_24h,
            "avg_engagement_24h": self.avg_engagement_24h,
            "workflow_runs_24h": self.workflow_runs_24h,
            "avg_workflow_duration_24h": self.avg_workflow_duration_24h,
            "posting_success_rate_24h": self.posting_success_rate_24h,
            "threshold_pass_rate_24h": self.threshold_pass_rate_24h
        }

