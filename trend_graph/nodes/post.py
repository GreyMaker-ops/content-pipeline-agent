"""
Twitter posting node for publishing generated tweets.

This module handles posting tweets to Twitter using Tweepy
and tracking the posting results.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import tweepy
from tweepy.errors import TweepyException

from ..state import TrendState, GeneratedPost, PostResult, PostStatus
from ..config import get_twitter_config
from ..database import update_post_posted, update_post_failed

logger = logging.getLogger(__name__)


class TwitterPoster:
    """Twitter poster using Tweepy for API v2."""
    
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
                wait_on_rate_limit=True  # Automatically handle rate limits
            )
            
            # Test authentication
            try:
                me = self.client.get_me()
                logger.info(f"Twitter client initialized for user: {me.data.username}")
            except Exception as e:
                logger.warning(f"Twitter authentication test failed: {e}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self.client = None
    
    async def post_tweet(self, generated_post: GeneratedPost) -> PostResult:
        """
        Post a single tweet and return the result.
        
        Args:
            generated_post: GeneratedPost object with tweet content
            
        Returns:
            PostResult: Result of the posting attempt
        """
        result = PostResult(generated_post=generated_post)
        
        if not self.client:
            error_msg = "Twitter client not initialized"
            logger.error(error_msg)
            result.mark_failed(error_msg)
            return result
        
        try:
            # Validate tweet content
            tweet_text = generated_post.tweet_text
            if len(tweet_text) > 280:
                error_msg = f"Tweet too long: {len(tweet_text)} characters"
                logger.error(error_msg)
                result.mark_failed(error_msg)
                return result
            
            # Post the tweet
            response = self.client.create_tweet(text=tweet_text)
            
            if response.data:
                tweet_id = response.data['id']
                tweet_url = f"https://twitter.com/user/status/{tweet_id}"
                
                result.mark_posted(tweet_url, tweet_id)
                
                logger.info(f"Successfully posted tweet: {tweet_url}")
                logger.debug(f"Tweet content: {tweet_text}")
                
                # Update database
                try:
                    await update_post_posted(
                        reddit_id=generated_post.reddit_id,
                        tweet_id=tweet_id,
                        tweet_url=tweet_url
                    )
                except Exception as e:
                    logger.warning(f"Error updating database after posting: {e}")
                
            else:
                error_msg = "Twitter API returned no data"
                logger.error(error_msg)
                result.mark_failed(error_msg)
            
        except TweepyException as e:
            error_msg = f"Twitter API error: {e}"
            logger.error(error_msg)
            result.mark_failed(error_msg)
            
            # Update database with failure
            try:
                await update_post_failed(
                    reddit_id=generated_post.reddit_id,
                    error_message=error_msg
                )
            except Exception as db_e:
                logger.warning(f"Error updating database after failure: {db_e}")
        
        except Exception as e:
            error_msg = f"Unexpected error posting tweet: {e}"
            logger.error(error_msg)
            result.mark_failed(error_msg)
            
            # Update database with failure
            try:
                await update_post_failed(
                    reddit_id=generated_post.reddit_id,
                    error_message=error_msg
                )
            except Exception as db_e:
                logger.warning(f"Error updating database after failure: {db_e}")
        
        return result
    
    async def post_tweets_batch(self, generated_posts: List[GeneratedPost]) -> List[PostResult]:
        """
        Post multiple tweets with rate limiting and error handling.
        
        Args:
            generated_posts: List of GeneratedPost objects
            
        Returns:
            List[PostResult]: Results of all posting attempts
        """
        results = []
        
        for i, generated_post in enumerate(generated_posts):
            try:
                result = await self.post_tweet(generated_post)
                results.append(result)
                
                # Rate limiting: Twitter allows 300 tweets per 15 minutes
                # That's 1 tweet every 3 seconds to be safe
                if i < len(generated_posts) - 1:  # Don't wait after the last tweet
                    logger.debug("Waiting 3 seconds between tweets for rate limiting")
                    await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Error posting tweet for {generated_post.reddit_id}: {e}")
                
                # Create failed result
                result = PostResult(generated_post=generated_post)
                result.mark_failed(str(e))
                results.append(result)
                
                continue
        
        successful_posts = len([r for r in results if r.status == PostStatus.POSTED])
        failed_posts = len([r for r in results if r.status == PostStatus.FAILED])
        
        logger.info(f"Batch posting completed: {successful_posts} successful, {failed_posts} failed")
        
        return results
    
    def validate_tweet_content(self, tweet_text: str) -> Dict[str, Any]:
        """
        Validate tweet content before posting.
        
        Returns:
            Dict with validation results
        """
        validation = {
            "valid": True,
            "issues": []
        }
        
        # Check length
        if len(tweet_text) > 280:
            validation["valid"] = False
            validation["issues"].append(f"Tweet too long: {len(tweet_text)} characters")
        
        # Check for empty content
        if not tweet_text.strip():
            validation["valid"] = False
            validation["issues"].append("Tweet content is empty")
        
        # Check for potential policy violations (basic checks)
        if any(word in tweet_text.lower() for word in ['spam', 'scam', 'fake']):
            validation["issues"].append("Potential policy violation detected")
        
        return validation
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Twitter API connection and permissions.
        
        Returns:
            Dict with connection test results
        """
        if not self.client:
            return {
                "connected": False,
                "error": "Client not initialized"
            }
        
        try:
            # Test basic API access
            me = self.client.get_me()
            
            # Test tweet creation permissions (dry run)
            # Note: We can't actually test tweet creation without posting
            
            return {
                "connected": True,
                "user_id": me.data.id,
                "username": me.data.username,
                "name": me.data.name,
                "permissions": "Read/Write access confirmed"
            }
            
        except TweepyException as e:
            return {
                "connected": False,
                "error": f"Twitter API error: {e}"
            }
        except Exception as e:
            return {
                "connected": False,
                "error": f"Unexpected error: {e}"
            }


# Global poster instance
poster = TwitterPoster()


async def post_content_node(state: TrendState) -> TrendState:
    """
    LangGraph node for posting content to Twitter.
    
    This node takes generated posts and publishes them to Twitter,
    tracking the results in the state.
    """
    logger.info("Starting post content node")
    state.update_step("posting")
    
    try:
        if not state.generated_posts:
            logger.info("No generated posts to publish")
            return state
        
        logger.info(f"Posting {len(state.generated_posts)} tweets to Twitter")
        
        # Post all generated tweets
        results = await poster.post_tweets_batch(state.generated_posts)
        
        # Add results to state
        state.add_results(results)
        
        # Log summary
        successful = len([r for r in results if r.status == PostStatus.POSTED])
        failed = len([r for r in results if r.status == PostStatus.FAILED])
        
        logger.info(f"Post content node completed: {successful} posted, {failed} failed")
        
        return state
        
    except Exception as e:
        error_msg = f"Error in post content node: {e}"
        logger.error(error_msg)
        state.fail_workflow(error_msg)
        return state


# Utility functions for testing
async def test_post_single(tweet_text: str) -> Dict[str, Any]:
    """Test function to post a single tweet."""
    from ..state import RawPost, ScoredPost, GeneratedPost
    from datetime import datetime
    
    # Create test post
    raw_post = RawPost(
        reddit_id="test",
        title="Test Post",
        url="https://example.com",
        upvotes=100,
        created_utc=datetime.utcnow().timestamp() - 3600,
        subreddit="test",
        permalink="https://reddit.com/test",
        num_comments=10,
        upvote_ratio=0.9
    )
    
    scored_post = ScoredPost(
        raw_post=raw_post,
        score=100.0,
        meets_threshold=True
    )
    
    generated_post = GeneratedPost(
        scored_post=scored_post,
        tweet_text=tweet_text
    )
    
    result = await poster.post_tweet(generated_post)
    
    return {
        "success": result.status == PostStatus.POSTED,
        "tweet_url": result.tweet_url,
        "tweet_id": result.tweet_id,
        "error_message": result.error_message,
        "status": result.status.value
    }


async def test_twitter_connection() -> Dict[str, Any]:
    """Test Twitter API connection."""
    return await poster.test_connection()


def validate_tweet_for_posting(tweet_text: str) -> Dict[str, Any]:
    """Validate tweet content for posting."""
    return poster.validate_tweet_content(tweet_text)


async def get_posting_stats() -> Dict[str, Any]:
    """Get statistics about recent posting activity."""
    try:
        from ..database import get_stats_24h
        
        stats = await get_stats_24h()
        
        return {
            "posts_posted_24h": stats.get("total_posted", 0),
            "posts_failed_24h": stats.get("total_failed", 0),
            "posting_success_rate": stats.get("posting_success_rate", 0),
            "avg_engagement": stats.get("avg_engagement"),
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting posting stats: {e}")
        return {
            "error": str(e)
        }

