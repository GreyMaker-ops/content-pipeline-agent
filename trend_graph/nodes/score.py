"""
Scoring node for calculating post virality.

This module implements the virality scoring algorithm based on
upvote velocity (upvotes per minute) and other engagement metrics.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from ..state import TrendState, RawPost, ScoredPost
from ..config import get_app_config
from ..database import update_post_score

logger = logging.getLogger(__name__)


class ViralityScorer:
    """Virality scorer for Reddit posts."""
    
    def __init__(self):
        self.app_config = get_app_config()
    
    def calculate_virality_score(self, post: RawPost) -> float:
        """
        Calculate virality score based on upvote velocity.
        
        The primary metric is upvotes per minute since posting.
        Additional factors can be added for more sophisticated scoring.
        
        Args:
            post: RawPost object with Reddit data
            
        Returns:
            float: Virality score (upvotes per minute)
        """
        # Calculate age in minutes
        age_minutes = post.age_minutes
        
        # Avoid division by zero for very new posts
        if age_minutes < 1:
            age_minutes = 1
        
        # Basic virality score: upvotes per minute
        base_score = post.upvotes / age_minutes
        
        # Apply additional factors for more sophisticated scoring
        score = self._apply_scoring_factors(post, base_score)
        
        logger.debug(f"Post {post.reddit_id}: {post.upvotes} upvotes, {age_minutes:.1f} min old, score: {score:.2f}")
        
        return score
    
    def _apply_scoring_factors(self, post: RawPost, base_score: float) -> float:
        """
        Apply additional scoring factors to the base score.
        
        This method can be extended to include more sophisticated
        virality indicators beyond simple upvote velocity.
        """
        score = base_score
        
        # Factor 1: Comment engagement ratio
        # Posts with high comment-to-upvote ratio may be more engaging
        if post.upvotes > 0:
            comment_ratio = post.num_comments / post.upvotes
            # Boost score slightly for posts with good discussion
            if comment_ratio > 0.1:  # More than 1 comment per 10 upvotes
                score *= 1.1
        
        # Factor 2: Upvote ratio quality
        # Posts with higher upvote ratios are generally better received
        if post.upvote_ratio > 0.9:
            score *= 1.05  # 5% boost for highly upvoted posts
        elif post.upvote_ratio < 0.7:
            score *= 0.95  # 5% penalty for controversial posts
        
        # Factor 3: Subreddit-specific adjustments
        # Some subreddits may have different engagement patterns
        subreddit_multipliers = {
            'interestingasfuck': 1.0,
            'technology': 1.1,  # Tech posts might be more valuable
            'pics': 0.9,  # Image posts might have different engagement
            'programming': 1.2,  # Programming content might be more niche but valuable
            'MachineLearning': 1.3,  # Specialized content
            'artificial': 1.2
        }
        
        multiplier = subreddit_multipliers.get(post.subreddit, 1.0)
        score *= multiplier
        
        # Factor 4: Time-based adjustments
        # Posts that are too old might be less relevant
        age_hours = post.age_minutes / 60
        if age_hours > 12:
            # Gradually reduce score for posts older than 12 hours
            age_penalty = max(0.5, 1 - (age_hours - 12) / 24)
            score *= age_penalty
        
        return score
    
    def score_post(self, post: RawPost) -> ScoredPost:
        """Score a single post and return ScoredPost object."""
        score = self.calculate_virality_score(post)
        meets_threshold = score >= self.app_config.min_score
        
        scored_post = ScoredPost(
            raw_post=post,
            score=score,
            meets_threshold=meets_threshold
        )
        
        logger.debug(f"Scored post {post.reddit_id}: {score:.2f} (threshold: {meets_threshold})")
        
        return scored_post
    
    def score_posts(self, posts: List[RawPost]) -> List[ScoredPost]:
        """Score multiple posts and return list of ScoredPost objects."""
        scored_posts = []
        
        for post in posts:
            try:
                scored_post = self.score_post(post)
                scored_posts.append(scored_post)
            except Exception as e:
                logger.error(f"Error scoring post {post.reddit_id}: {e}")
                continue
        
        # Sort by score (highest first)
        scored_posts.sort(key=lambda p: p.score, reverse=True)
        
        logger.info(f"Scored {len(scored_posts)} posts")
        return scored_posts
    
    def get_posts_above_threshold(self, scored_posts: List[ScoredPost]) -> List[ScoredPost]:
        """Filter posts that meet the virality threshold."""
        above_threshold = [post for post in scored_posts if post.meets_threshold]
        
        logger.info(f"Posts above threshold ({self.app_config.min_score}): {len(above_threshold)}")
        
        return above_threshold
    
    def get_scoring_stats(self, scored_posts: List[ScoredPost]) -> Dict[str, Any]:
        """Get statistics about the scoring results."""
        if not scored_posts:
            return {
                "total_posts": 0,
                "above_threshold": 0,
                "threshold_rate": 0.0,
                "avg_score": 0.0,
                "max_score": 0.0,
                "min_score": 0.0
            }
        
        scores = [post.score for post in scored_posts]
        above_threshold = len([post for post in scored_posts if post.meets_threshold])
        
        return {
            "total_posts": len(scored_posts),
            "above_threshold": above_threshold,
            "threshold_rate": above_threshold / len(scored_posts),
            "avg_score": sum(scores) / len(scores),
            "max_score": max(scores),
            "min_score": min(scores),
            "threshold_value": self.app_config.min_score
        }


# Global scorer instance
scorer = ViralityScorer()


async def score_virality_node(state: TrendState) -> TrendState:
    """
    LangGraph node for scoring post virality.
    
    This node takes raw posts from the state, calculates virality scores,
    and adds scored posts back to the state.
    """
    logger.info("Starting score virality node")
    state.update_step("scoring")
    
    try:
        if not state.raw_posts:
            logger.warning("No raw posts to score")
            return state
        
        # Score all raw posts
        scored_posts = scorer.score_posts(state.raw_posts)
        
        # Update database with scores
        for scored_post in scored_posts:
            try:
                await update_post_score(
                    reddit_id=scored_post.reddit_id,
                    score=scored_post.score,
                    meets_threshold=scored_post.meets_threshold,
                    min_score=state.min_score
                )
            except Exception as e:
                logger.warning(f"Error updating post score in database: {e}")
        
        # Add scored posts to state
        state.add_scored_posts(scored_posts)
        
        # Log scoring statistics
        stats = scorer.get_scoring_stats(scored_posts)
        logger.info(f"Scoring stats: {stats}")
        
        # Filter posts above threshold for next steps
        above_threshold = scorer.get_posts_above_threshold(scored_posts)
        
        if not above_threshold:
            logger.info("No posts meet virality threshold, workflow will end")
        else:
            logger.info(f"Posts proceeding to content generation: {len(above_threshold)}")
        
        logger.info("Score virality node completed")
        return state
        
    except Exception as e:
        error_msg = f"Error in score virality node: {e}"
        logger.error(error_msg)
        state.fail_workflow(error_msg)
        return state


# Utility functions for testing and analysis
def test_score_calculation(upvotes: int, age_minutes: float, subreddit: str = "test") -> float:
    """Test function to calculate score for given parameters."""
    from ..state import RawPost
    from datetime import datetime
    
    # Create a test post
    test_post = RawPost(
        reddit_id="test",
        title="Test Post",
        url="https://example.com",
        upvotes=upvotes,
        created_utc=datetime.utcnow().timestamp() - (age_minutes * 60),
        subreddit=subreddit,
        permalink="https://reddit.com/test",
        num_comments=upvotes // 10,  # Assume 1 comment per 10 upvotes
        upvote_ratio=0.9
    )
    
    return scorer.calculate_virality_score(test_post)


def analyze_threshold_sensitivity(posts: List[RawPost], min_scores: List[float]) -> Dict[str, Any]:
    """Analyze how different threshold values affect post selection."""
    results = {}
    
    for min_score in min_scores:
        # Temporarily change threshold
        original_threshold = scorer.app_config.min_score
        scorer.app_config.min_score = min_score
        
        # Score posts with this threshold
        scored_posts = scorer.score_posts(posts)
        above_threshold = scorer.get_posts_above_threshold(scored_posts)
        
        results[min_score] = {
            "posts_above_threshold": len(above_threshold),
            "percentage": len(above_threshold) / len(posts) * 100 if posts else 0
        }
        
        # Restore original threshold
        scorer.app_config.min_score = original_threshold
    
    return results


def get_top_posts_by_score(posts: List[RawPost], limit: int = 10) -> List[Dict[str, Any]]:
    """Get top posts by virality score for analysis."""
    scored_posts = scorer.score_posts(posts)
    top_posts = scored_posts[:limit]
    
    return [
        {
            "reddit_id": post.reddit_id,
            "title": post.title[:100],
            "subreddit": post.raw_post.subreddit,
            "upvotes": post.raw_post.upvotes,
            "age_minutes": post.raw_post.age_minutes,
            "score": post.score,
            "meets_threshold": post.meets_threshold
        }
        for post in top_posts
    ]

