"""
Metrics collection node for gathering Twitter engagement data.

This module collects likes, retweets, and other engagement metrics
from posted tweets after they've been live for a specified time.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import tweepy
from tweepy.errors import TweepyException

from ..state import PostResult, PostStatus
from ..config import get_twitter_config
from ..database import update_post_metrics, get_posts_needing_metrics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Metrics collector for Twitter engagement data."""
    
    def __init__(self):
        self.twitter_config = get_twitter_config()
        self.client = None
        self._init_client()
    
    def _init_client(self) -> None:
        """Initialize Twitter API client."""
        try:
            self.client = tweepy.Client(
                bearer_token=self.twitter_config.bearer_token,
                consumer_key=self.twitter_config.api_key,
                consumer_secret=self.twitter_config.api_secret,
                access_token=self.twitter_config.access_token,
                access_token_secret=self.twitter_config.access_token_secret,
                wait_on_rate_limit=True
            )
            
            logger.info("Twitter client initialized for metrics collection")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client for metrics: {e}")
            self.client = None
    
    async def collect_tweet_metrics(self, tweet_id: str) -> Optional[Dict[str, int]]:
        """
        Collect engagement metrics for a specific tweet.
        
        Args:
            tweet_id: Twitter tweet ID
            
        Returns:
            Optional[Dict]: Metrics data or None if collection fails
        """
        if not self.client:
            logger.error("Twitter client not initialized")
            return None
        
        try:
            # Get tweet with public metrics
            tweet = self.client.get_tweet(
                id=tweet_id,
                tweet_fields=['public_metrics', 'created_at']
            )
            
            if tweet.data and tweet.data.public_metrics:
                metrics = tweet.data.public_metrics
                
                return {
                    'likes': metrics.get('like_count', 0),
                    'retweets': metrics.get('retweet_count', 0),
                    'replies': metrics.get('reply_count', 0),
                    'quotes': metrics.get('quote_count', 0),
                    'impressions': metrics.get('impression_count', 0)
                }
            else:
                logger.warning(f"No metrics data found for tweet {tweet_id}")
                return None
                
        except TweepyException as e:
            if "Not Found" in str(e):
                logger.warning(f"Tweet {tweet_id} not found (may be deleted)")
            else:
                logger.error(f"Twitter API error collecting metrics for {tweet_id}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error collecting metrics for {tweet_id}: {e}")
            return None
    
    async def collect_metrics_batch(self, tweet_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Collect metrics for multiple tweets.
        
        Args:
            tweet_ids: List of Twitter tweet IDs
            
        Returns:
            Dict: Mapping of tweet_id to metrics data
        """
        results = {}
        
        for i, tweet_id in enumerate(tweet_ids):
            try:
                metrics = await self.collect_tweet_metrics(tweet_id)
                if metrics:
                    results[tweet_id] = metrics
                    logger.debug(f"Collected metrics for tweet {tweet_id}: {metrics}")
                
                # Rate limiting: Twitter API v2 allows 75 requests per 15 minutes
                # That's 1 request every 12 seconds to be safe
                if i < len(tweet_ids) - 1:  # Don't wait after the last request
                    await asyncio.sleep(12)
                
            except Exception as e:
                logger.error(f"Error collecting metrics for tweet {tweet_id}: {e}")
                continue
        
        logger.info(f"Collected metrics for {len(results)}/{len(tweet_ids)} tweets")
        return results
    
    async def update_post_metrics_in_db(self, reddit_id: str, metrics: Dict[str, int]) -> None:
        """
        Update post metrics in the database.
        
        Args:
            reddit_id: Reddit post ID
            metrics: Metrics data from Twitter
        """
        try:
            await update_post_metrics(
                reddit_id=reddit_id,
                likes=metrics.get('likes', 0),
                retweets=metrics.get('retweets', 0),
                replies=metrics.get('replies', 0)
            )
            logger.debug(f"Updated metrics in database for {reddit_id}")
            
        except Exception as e:
            logger.error(f"Error updating metrics in database for {reddit_id}: {e}")
    
    async def collect_pending_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics for all posts that need metrics collection.
        
        This function finds posts that were posted more than 1 hour ago
        but haven't had their metrics collected yet.
        
        Returns:
            Dict: Summary of metrics collection results
        """
        try:
            # Get posts that need metrics collection
            posts_needing_metrics = await get_posts_needing_metrics()
            
            if not posts_needing_metrics:
                logger.info("No posts need metrics collection")
                return {
                    "posts_processed": 0,
                    "metrics_collected": 0,
                    "errors": 0
                }
            
            logger.info(f"Collecting metrics for {len(posts_needing_metrics)} posts")
            
            # Extract tweet IDs and create mapping
            tweet_id_to_post = {}
            tweet_ids = []
            
            for post in posts_needing_metrics:
                if post.tweet_id:
                    tweet_ids.append(post.tweet_id)
                    tweet_id_to_post[post.tweet_id] = post
            
            if not tweet_ids:
                logger.warning("No valid tweet IDs found for metrics collection")
                return {
                    "posts_processed": len(posts_needing_metrics),
                    "metrics_collected": 0,
                    "errors": len(posts_needing_metrics)
                }
            
            # Collect metrics for all tweets
            metrics_results = await self.collect_metrics_batch(tweet_ids)
            
            # Update database with collected metrics
            metrics_collected = 0
            errors = 0
            
            for tweet_id, metrics in metrics_results.items():
                post = tweet_id_to_post[tweet_id]
                try:
                    await self.update_post_metrics_in_db(post.reddit_id, metrics)
                    metrics_collected += 1
                except Exception as e:
                    logger.error(f"Error updating metrics for {post.reddit_id}: {e}")
                    errors += 1
            
            # Handle posts where metrics collection failed
            failed_tweet_ids = set(tweet_ids) - set(metrics_results.keys())
            for tweet_id in failed_tweet_ids:
                post = tweet_id_to_post[tweet_id]
                logger.warning(f"Failed to collect metrics for tweet {tweet_id} (post {post.reddit_id})")
                errors += 1
            
            summary = {
                "posts_processed": len(posts_needing_metrics),
                "metrics_collected": metrics_collected,
                "errors": errors,
                "success_rate": metrics_collected / len(posts_needing_metrics) if posts_needing_metrics else 0
            }
            
            logger.info(f"Metrics collection completed: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Error in collect_pending_metrics: {e}")
            return {
                "posts_processed": 0,
                "metrics_collected": 0,
                "errors": 1,
                "error_message": str(e)
            }
    
    def calculate_engagement_score(self, metrics: Dict[str, int]) -> float:
        """
        Calculate an engagement score based on metrics.
        
        Args:
            metrics: Dictionary with likes, retweets, replies, etc.
            
        Returns:
            float: Engagement score
        """
        likes = metrics.get('likes', 0)
        retweets = metrics.get('retweets', 0)
        replies = metrics.get('replies', 0)
        quotes = metrics.get('quotes', 0)
        
        # Weighted engagement score
        # Retweets and quotes are worth more than likes
        # Replies indicate high engagement
        score = (
            likes * 1.0 +
            retweets * 3.0 +
            replies * 2.0 +
            quotes * 2.5
        )
        
        return score
    
    async def get_engagement_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get engagement analytics for recent posts.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dict: Analytics data
        """
        try:
            from ..database import get_recent_posts
            
            # Get recent posts with metrics
            recent_posts = await get_recent_posts(hours=hours)
            posts_with_metrics = [
                post for post in recent_posts 
                if post.likes is not None and post.retweets is not None
            ]
            
            if not posts_with_metrics:
                return {
                    "total_posts": 0,
                    "posts_with_metrics": 0,
                    "avg_likes": 0,
                    "avg_retweets": 0,
                    "avg_engagement_score": 0,
                    "top_performing_post": None
                }
            
            # Calculate statistics
            total_likes = sum(post.likes for post in posts_with_metrics)
            total_retweets = sum(post.retweets for post in posts_with_metrics)
            
            avg_likes = total_likes / len(posts_with_metrics)
            avg_retweets = total_retweets / len(posts_with_metrics)
            
            # Calculate engagement scores
            engagement_scores = []
            for post in posts_with_metrics:
                metrics = {
                    'likes': post.likes,
                    'retweets': post.retweets,
                    'replies': post.replies or 0
                }
                score = self.calculate_engagement_score(metrics)
                engagement_scores.append((post, score))
            
            avg_engagement_score = sum(score for _, score in engagement_scores) / len(engagement_scores)
            
            # Find top performing post
            top_post, top_score = max(engagement_scores, key=lambda x: x[1])
            
            return {
                "total_posts": len(recent_posts),
                "posts_with_metrics": len(posts_with_metrics),
                "avg_likes": avg_likes,
                "avg_retweets": avg_retweets,
                "avg_engagement_score": avg_engagement_score,
                "top_performing_post": {
                    "reddit_id": top_post.reddit_id,
                    "title": top_post.title[:100],
                    "tweet_url": top_post.tweet_url,
                    "likes": top_post.likes,
                    "retweets": top_post.retweets,
                    "engagement_score": top_score
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting engagement analytics: {e}")
            return {"error": str(e)}


# Global metrics collector instance
collector = MetricsCollector()


async def collect_metrics_node() -> Dict[str, Any]:
    """
    Standalone function for collecting metrics (not part of main workflow).
    
    This function is called periodically to collect metrics for tweets
    that have been posted for at least 1 hour.
    
    Returns:
        Dict: Results of metrics collection
    """
    logger.info("Starting metrics collection")
    
    try:
        results = await collector.collect_pending_metrics()
        logger.info(f"Metrics collection completed: {results}")
        return results
        
    except Exception as e:
        error_msg = f"Error in metrics collection: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error_message": error_msg
        }


# Utility functions for testing and monitoring
async def test_metrics_collection(tweet_id: str) -> Dict[str, Any]:
    """Test function to collect metrics for a specific tweet."""
    metrics = await collector.collect_tweet_metrics(tweet_id)
    
    if metrics:
        engagement_score = collector.calculate_engagement_score(metrics)
        return {
            "success": True,
            "tweet_id": tweet_id,
            "metrics": metrics,
            "engagement_score": engagement_score
        }
    else:
        return {
            "success": False,
            "tweet_id": tweet_id,
            "error": "Failed to collect metrics"
        }


async def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of recent metrics collection activity."""
    try:
        analytics = await collector.get_engagement_analytics(hours=24)
        pending_count = len(await get_posts_needing_metrics())
        
        return {
            "pending_metrics_collection": pending_count,
            "last_24h_analytics": analytics,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        return {"error": str(e)}


async def force_metrics_collection() -> Dict[str, Any]:
    """Force metrics collection for all pending posts."""
    return await collect_metrics_node()

