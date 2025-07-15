"""
State management for the social trend agent.

This module defines the data structures used throughout the LangGraph workflow
to track posts as they move through different stages of processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class PostStatus(Enum):
    """Status of a post in the processing pipeline."""
    RAW = "raw"
    SCORED = "scored"
    GENERATED = "generated"
    POSTED = "posted"
    METRICS_COLLECTED = "metrics_collected"
    FAILED = "failed"


@dataclass
class RawPost:
    """Raw post data scraped from Reddit."""
    reddit_id: str
    title: str
    url: str
    upvotes: int
    created_utc: float
    subreddit: str
    permalink: str
    num_comments: int
    upvote_ratio: float
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def age_minutes(self) -> float:
        """Calculate age of post in minutes."""
        now = datetime.utcnow().timestamp()
        return (now - self.created_utc) / 60.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "reddit_id": self.reddit_id,
            "title": self.title,
            "url": self.url,
            "upvotes": self.upvotes,
            "created_utc": self.created_utc,
            "subreddit": self.subreddit,
            "permalink": self.permalink,
            "num_comments": self.num_comments,
            "upvote_ratio": self.upvote_ratio,
            "scraped_at": self.scraped_at.isoformat(),
            "age_minutes": self.age_minutes
        }


@dataclass
class ScoredPost:
    """Post with calculated virality score."""
    raw_post: RawPost
    score: float
    meets_threshold: bool
    scored_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def reddit_id(self) -> str:
        """Get Reddit ID from raw post."""
        return self.raw_post.reddit_id
    
    @property
    def title(self) -> str:
        """Get title from raw post."""
        return self.raw_post.title
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "raw_post": self.raw_post.to_dict(),
            "score": self.score,
            "meets_threshold": self.meets_threshold,
            "scored_at": self.scored_at.isoformat()
        }


@dataclass
class GeneratedPost:
    """Post with generated tweet content."""
    scored_post: ScoredPost
    tweet_text: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def reddit_id(self) -> str:
        """Get Reddit ID from scored post."""
        return self.scored_post.reddit_id
    
    @property
    def title(self) -> str:
        """Get title from scored post."""
        return self.scored_post.title
    
    @property
    def score(self) -> float:
        """Get score from scored post."""
        return self.scored_post.score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scored_post": self.scored_post.to_dict(),
            "tweet_text": self.tweet_text,
            "generated_at": self.generated_at.isoformat()
        }


@dataclass
class PostResult:
    """Final result with Twitter posting information."""
    generated_post: GeneratedPost
    tweet_url: Optional[str] = None
    tweet_id: Optional[str] = None
    posted_at: Optional[datetime] = None
    likes: Optional[int] = None
    retweets: Optional[int] = None
    metrics_collected_at: Optional[datetime] = None
    status: PostStatus = PostStatus.GENERATED
    error_message: Optional[str] = None
    
    @property
    def reddit_id(self) -> str:
        """Get Reddit ID from generated post."""
        return self.generated_post.reddit_id
    
    @property
    def title(self) -> str:
        """Get title from generated post."""
        return self.generated_post.title
    
    @property
    def score(self) -> float:
        """Get score from generated post."""
        return self.generated_post.score
    
    @property
    def tweet_text(self) -> str:
        """Get tweet text from generated post."""
        return self.generated_post.tweet_text
    
    def mark_posted(self, tweet_url: str, tweet_id: str) -> None:
        """Mark post as successfully posted to Twitter."""
        self.tweet_url = tweet_url
        self.tweet_id = tweet_id
        self.posted_at = datetime.utcnow()
        self.status = PostStatus.POSTED
    
    def mark_metrics_collected(self, likes: int, retweets: int) -> None:
        """Mark metrics as collected."""
        self.likes = likes
        self.retweets = retweets
        self.metrics_collected_at = datetime.utcnow()
        self.status = PostStatus.METRICS_COLLECTED
    
    def mark_failed(self, error_message: str) -> None:
        """Mark post as failed."""
        self.error_message = error_message
        self.status = PostStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "generated_post": self.generated_post.to_dict(),
            "tweet_url": self.tweet_url,
            "tweet_id": self.tweet_id,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "likes": self.likes,
            "retweets": self.retweets,
            "metrics_collected_at": self.metrics_collected_at.isoformat() if self.metrics_collected_at else None,
            "status": self.status.value,
            "error_message": self.error_message
        }


@dataclass
class TrendState:
    """
    State object for the LangGraph workflow.
    
    This tracks the current state of the trend analysis workflow,
    including all posts being processed and workflow metadata.
    """
    # Current workflow data
    raw_posts: List[RawPost] = field(default_factory=list)
    scored_posts: List[ScoredPost] = field(default_factory=list)
    generated_posts: List[GeneratedPost] = field(default_factory=list)
    results: List[PostResult] = field(default_factory=list)
    
    # Workflow metadata
    workflow_id: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: str = ""
    error_message: Optional[str] = None
    
    # Configuration
    min_score: float = 200.0
    subreddits: List[str] = field(default_factory=lambda: ["interestingasfuck", "technology", "pics"])
    
    # Statistics
    total_scraped: int = 0
    total_scored: int = 0
    total_generated: int = 0
    total_posted: int = 0
    total_failed: int = 0
    
    def start_workflow(self, workflow_id: str) -> None:
        """Initialize workflow with ID and timestamp."""
        self.workflow_id = workflow_id
        self.started_at = datetime.utcnow()
        self.current_step = "starting"
        self.error_message = None
    
    def complete_workflow(self) -> None:
        """Mark workflow as completed."""
        self.completed_at = datetime.utcnow()
        self.current_step = "completed"
    
    def fail_workflow(self, error_message: str) -> None:
        """Mark workflow as failed."""
        self.error_message = error_message
        self.current_step = "failed"
        self.completed_at = datetime.utcnow()
    
    def update_step(self, step_name: str) -> None:
        """Update current workflow step."""
        self.current_step = step_name
    
    def add_raw_posts(self, posts: List[RawPost]) -> None:
        """Add raw posts to the state."""
        self.raw_posts.extend(posts)
        self.total_scraped += len(posts)
    
    def add_scored_posts(self, posts: List[ScoredPost]) -> None:
        """Add scored posts to the state."""
        self.scored_posts.extend(posts)
        self.total_scored += len(posts)
    
    def add_generated_posts(self, posts: List[GeneratedPost]) -> None:
        """Add generated posts to the state."""
        self.generated_posts.extend(posts)
        self.total_generated += len(posts)
    
    def add_results(self, results: List[PostResult]) -> None:
        """Add final results to the state."""
        self.results.extend(results)
        for result in results:
            if result.status == PostStatus.POSTED:
                self.total_posted += 1
            elif result.status == PostStatus.FAILED:
                self.total_failed += 1
    
    def get_posts_above_threshold(self) -> List[ScoredPost]:
        """Get posts that meet the virality threshold."""
        return [post for post in self.scored_posts if post.meets_threshold]
    
    def get_successful_posts(self) -> List[PostResult]:
        """Get successfully posted results."""
        return [result for result in self.results if result.status == PostStatus.POSTED]
    
    def get_failed_posts(self) -> List[PostResult]:
        """Get failed results."""
        return [result for result in self.results if result.status == PostStatus.FAILED]
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate workflow duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.started_at is not None and self.completed_at is None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of posted tweets."""
        total_attempts = self.total_posted + self.total_failed
        if total_attempts == 0:
            return 0.0
        return self.total_posted / total_attempts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "min_score": self.min_score,
            "subreddits": self.subreddits,
            "total_scraped": self.total_scraped,
            "total_scored": self.total_scored,
            "total_generated": self.total_generated,
            "total_posted": self.total_posted,
            "total_failed": self.total_failed,
            "duration_seconds": self.duration_seconds,
            "is_running": self.is_running,
            "success_rate": self.success_rate,
            "raw_posts_count": len(self.raw_posts),
            "scored_posts_count": len(self.scored_posts),
            "generated_posts_count": len(self.generated_posts),
            "results_count": len(self.results)
        }

