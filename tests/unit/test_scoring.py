"""
Unit tests for scoring functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from trend_graph.nodes.score import (
    ViralityScorer, calculate_virality_score, score_virality_node
)
from trend_graph.state import TrendState, PostData, PostResult, PostStatus


class TestViralityScorer:
    """Test ViralityScorer class."""
    
    def test_scorer_initialization(self):
        """Test ViralityScorer initialization."""
        scorer = ViralityScorer()
        
        assert scorer.weights is not None
        assert "upvote_velocity" in scorer.weights
        assert "comment_ratio" in scorer.weights
        assert "recency_factor" in scorer.weights
    
    def test_calculate_upvote_velocity(self):
        """Test upvote velocity calculation."""
        scorer = ViralityScorer()
        
        # Test case: 500 upvotes in 2 hours
        velocity = scorer.calculate_upvote_velocity(500, 2.0)
        assert velocity == 250.0
        
        # Test case: 1000 upvotes in 0.5 hours
        velocity = scorer.calculate_upvote_velocity(1000, 0.5)
        assert velocity == 2000.0
        
        # Test edge case: 0 hours (should return 0)
        velocity = scorer.calculate_upvote_velocity(100, 0.0)
        assert velocity == 0.0
    
    def test_calculate_comment_ratio(self):
        """Test comment ratio calculation."""
        scorer = ViralityScorer()
        
        # Test case: 25 comments, 500 upvotes
        ratio = scorer.calculate_comment_ratio(25, 500)
        assert ratio == 0.05
        
        # Test case: 100 comments, 200 upvotes
        ratio = scorer.calculate_comment_ratio(100, 200)
        assert ratio == 0.5
        
        # Test edge case: 0 upvotes (should return 0)
        ratio = scorer.calculate_comment_ratio(10, 0)
        assert ratio == 0.0
    
    def test_calculate_recency_factor(self):
        """Test recency factor calculation."""
        scorer = ViralityScorer()
        
        # Test case: 1 hour old (should be close to 1.0)
        factor = scorer.calculate_recency_factor(1.0)
        assert 0.9 < factor <= 1.0
        
        # Test case: 6 hours old (should be lower)
        factor = scorer.calculate_recency_factor(6.0)
        assert 0.5 < factor < 0.9
        
        # Test case: 24 hours old (should be much lower)
        factor = scorer.calculate_recency_factor(24.0)
        assert 0.0 < factor < 0.5
    
    def test_calculate_engagement_score(self):
        """Test engagement score calculation."""
        scorer = ViralityScorer()
        
        # Test case: high engagement
        score = scorer.calculate_engagement_score(
            upvote_velocity=500.0,
            comment_ratio=0.1,
            recency_factor=0.9
        )
        
        assert isinstance(score, float)
        assert score > 0
    
    def test_score_post_data(self, sample_post_data):
        """Test scoring PostData."""
        scorer = ViralityScorer()
        
        # Mock current time to be 2 hours after post creation
        current_time = sample_post_data.created_utc + 7200
        
        with patch('time.time', return_value=current_time):
            score = scorer.score_post(sample_post_data)
        
        assert isinstance(score, float)
        assert score >= 0
    
    def test_score_post_result(self, sample_post_result):
        """Test scoring PostResult."""
        scorer = ViralityScorer()
        
        # Mock current time
        current_time = sample_post_result.created_utc + 3600
        
        with patch('time.time', return_value=current_time):
            score = scorer.score_post(sample_post_result)
        
        assert isinstance(score, float)
        assert score >= 0
    
    def test_meets_threshold(self):
        """Test threshold checking."""
        scorer = ViralityScorer()
        
        assert scorer.meets_threshold(75.0, 50.0) is True
        assert scorer.meets_threshold(25.0, 50.0) is False
        assert scorer.meets_threshold(50.0, 50.0) is True  # Equal should pass


class TestCalculateViralityScore:
    """Test standalone calculate_virality_score function."""
    
    def test_calculate_virality_score_basic(self):
        """Test basic virality score calculation."""
        score = calculate_virality_score(
            upvotes=500,
            num_comments=25,
            age_hours=2.0
        )
        
        assert isinstance(score, float)
        assert score >= 0
    
    def test_calculate_virality_score_high_velocity(self):
        """Test score with high upvote velocity."""
        score_high = calculate_virality_score(
            upvotes=1000,
            num_comments=50,
            age_hours=1.0  # High velocity
        )
        
        score_low = calculate_virality_score(
            upvotes=1000,
            num_comments=50,
            age_hours=10.0  # Low velocity
        )
        
        assert score_high > score_low
    
    def test_calculate_virality_score_high_engagement(self):
        """Test score with high comment engagement."""
        score_high_comments = calculate_virality_score(
            upvotes=500,
            num_comments=100,  # High comment ratio
            age_hours=2.0
        )
        
        score_low_comments = calculate_virality_score(
            upvotes=500,
            num_comments=10,  # Low comment ratio
            age_hours=2.0
        )
        
        assert score_high_comments > score_low_comments
    
    def test_calculate_virality_score_recency(self):
        """Test score with different recency."""
        score_recent = calculate_virality_score(
            upvotes=500,
            num_comments=25,
            age_hours=1.0  # Very recent
        )
        
        score_old = calculate_virality_score(
            upvotes=500,
            num_comments=25,
            age_hours=12.0  # Older
        )
        
        assert score_recent > score_old
    
    def test_calculate_virality_score_edge_cases(self):
        """Test edge cases."""
        # Zero upvotes
        score = calculate_virality_score(0, 0, 1.0)
        assert score == 0.0
        
        # Zero age (should handle gracefully)
        score = calculate_virality_score(100, 10, 0.0)
        assert score >= 0
        
        # Very high values
        score = calculate_virality_score(10000, 1000, 0.5)
        assert score > 0


class TestScoreViralityNode:
    """Test score_virality_node function."""
    
    @pytest.mark.asyncio
    async def test_score_virality_node_success(self, sample_trend_state):
        """Test successful scoring of posts."""
        # Add some posts to score
        post1 = PostData(
            reddit_id="score1",
            title="High Score Post",
            url="https://reddit.com/score1",
            subreddit="test",
            upvotes=1000,
            created_utc=1640995200,
            author="author1",
            selftext="Content 1",
            num_comments=100,
            permalink="/score1"
        )
        
        post2 = PostData(
            reddit_id="score2",
            title="Low Score Post",
            url="https://reddit.com/score2",
            subreddit="test",
            upvotes=50,
            created_utc=1640995200,
            author="author2",
            selftext="Content 2",
            num_comments=5,
            permalink="/score2"
        )
        
        sample_trend_state.scraped_posts = [post1, post2]
        sample_trend_state.config["min_score"] = 100
        
        # Mock current time
        current_time = 1640995200 + 3600  # 1 hour later
        
        with patch('time.time', return_value=current_time):
            result_state = await score_virality_node(sample_trend_state)
        
        assert len(result_state.scored_posts) == 2
        assert result_state.current_step == "score_virality"
        
        # Check that scores were calculated
        for post in result_state.scored_posts:
            assert post.virality_score is not None
            assert post.meets_threshold is not None
            assert post.status == PostStatus.SCORED
    
    @pytest.mark.asyncio
    async def test_score_virality_node_no_posts(self):
        """Test scoring with no posts."""
        empty_state = TrendState(
            workflow_id="empty_test",
            scraped_posts=[],
            scored_posts=[],
            generated_posts=[],
            posted_results=[],
            errors=[],
            current_step="scrape_sources",
            completed_steps=[],
            start_time=1640995200,
            config={"min_score": 100}
        )
        
        result_state = await score_virality_node(empty_state)
        
        assert len(result_state.scored_posts) == 0
        assert result_state.current_step == "score_virality"
        assert len(result_state.errors) == 0
    
    @pytest.mark.asyncio
    async def test_score_virality_node_threshold_filtering(self, sample_trend_state):
        """Test that posts are filtered by threshold."""
        # Create posts with different expected scores
        high_score_post = PostData(
            reddit_id="high1",
            title="Viral Post",
            url="https://reddit.com/high1",
            subreddit="test",
            upvotes=2000,
            created_utc=1640995200,
            author="viral_author",
            selftext="Viral content",
            num_comments=200,
            permalink="/high1"
        )
        
        low_score_post = PostData(
            reddit_id="low1",
            title="Regular Post",
            url="https://reddit.com/low1",
            subreddit="test",
            upvotes=10,
            created_utc=1640995200,
            author="regular_author",
            selftext="Regular content",
            num_comments=1,
            permalink="/low1"
        )
        
        sample_trend_state.scraped_posts = [high_score_post, low_score_post]
        sample_trend_state.config["min_score"] = 100  # High threshold
        
        # Mock current time
        current_time = 1640995200 + 1800  # 30 minutes later
        
        with patch('time.time', return_value=current_time):
            result_state = await score_virality_node(sample_trend_state)
        
        # Check that both posts were scored but threshold was applied
        assert len(result_state.scored_posts) == 2
        
        # Find the high and low score posts
        high_result = next(p for p in result_state.scored_posts if p.reddit_id == "high1")
        low_result = next(p for p in result_state.scored_posts if p.reddit_id == "low1")
        
        # High score post should meet threshold
        assert high_result.meets_threshold is True
        assert high_result.virality_score > sample_trend_state.config["min_score"]
        
        # Low score post should not meet threshold
        assert low_result.meets_threshold is False
        assert low_result.virality_score < sample_trend_state.config["min_score"]
    
    @pytest.mark.asyncio
    async def test_score_virality_node_error_handling(self, sample_trend_state):
        """Test error handling in scoring."""
        # Create a post with invalid data that might cause errors
        invalid_post = PostData(
            reddit_id="invalid1",
            title="Invalid Post",
            url="https://reddit.com/invalid1",
            subreddit="test",
            upvotes=None,  # Invalid upvotes
            created_utc=1640995200,
            author="test_author",
            selftext="Test content",
            num_comments=None,  # Invalid comments
            permalink="/invalid1"
        )
        
        sample_trend_state.scraped_posts = [invalid_post]
        sample_trend_state.config["min_score"] = 100
        
        # The function should handle errors gracefully
        result_state = await score_virality_node(sample_trend_state)
        
        # Should still update the step even if scoring fails
        assert result_state.current_step == "score_virality"
        
        # Errors should be recorded
        assert len(result_state.errors) > 0
    
    @pytest.mark.asyncio
    async def test_score_virality_node_database_integration(self, sample_trend_state, temp_db):
        """Test database integration during scoring."""
        post = PostData(
            reddit_id="db_test1",
            title="Database Test Post",
            url="https://reddit.com/db_test1",
            subreddit="test",
            upvotes=500,
            created_utc=1640995200,
            author="db_author",
            selftext="Database test content",
            num_comments=25,
            permalink="/db_test1"
        )
        
        sample_trend_state.scraped_posts = [post]
        sample_trend_state.config["min_score"] = 50
        
        # Mock database functions
        with patch('trend_graph.nodes.score.update_post_score') as mock_update:
            mock_update.return_value = None
            
            current_time = 1640995200 + 3600
            with patch('time.time', return_value=current_time):
                result_state = await score_virality_node(sample_trend_state)
            
            # Verify database update was called
            assert mock_update.called
            assert len(result_state.scored_posts) == 1


class TestScoringPerformance:
    """Test scoring performance and edge cases."""
    
    @pytest.mark.asyncio
    async def test_scoring_performance_large_batch(self, performance_timer):
        """Test scoring performance with large batch of posts."""
        # Create a large batch of posts
        posts = []
        for i in range(100):
            post = PostData(
                reddit_id=f"perf_{i}",
                title=f"Performance Test Post {i}",
                url=f"https://reddit.com/perf_{i}",
                subreddit="test",
                upvotes=100 + i * 10,
                created_utc=1640995200,
                author=f"author_{i}",
                selftext=f"Content {i}",
                num_comments=5 + i,
                permalink=f"/perf_{i}"
            )
            posts.append(post)
        
        state = TrendState(
            workflow_id="perf_test",
            scraped_posts=posts,
            scored_posts=[],
            generated_posts=[],
            posted_results=[],
            errors=[],
            current_step="scrape_sources",
            completed_steps=[],
            start_time=1640995200,
            config={"min_score": 100}
        )
        
        performance_timer.start()
        
        current_time = 1640995200 + 3600
        with patch('time.time', return_value=current_time):
            result_state = await score_virality_node(state)
        
        performance_timer.stop()
        
        # Verify all posts were scored
        assert len(result_state.scored_posts) == 100
        
        # Performance should be reasonable (less than 5 seconds for 100 posts)
        assert performance_timer.duration < 5.0
    
    def test_scoring_edge_cases(self):
        """Test scoring with edge case values."""
        scorer = ViralityScorer()
        
        # Test with extreme values
        post = PostData(
            reddit_id="extreme1",
            title="Extreme Post",
            url="https://reddit.com/extreme1",
            subreddit="test",
            upvotes=1000000,  # Very high upvotes
            created_utc=1640995200,
            author="extreme_author",
            selftext="Extreme content",
            num_comments=100000,  # Very high comments
            permalink="/extreme1"
        )
        
        current_time = post.created_utc + 60  # 1 minute later (very recent)
        
        with patch('time.time', return_value=current_time):
            score = scorer.score_post(post)
        
        assert isinstance(score, float)
        assert score > 0
        assert not (score == float('inf') or score != score)  # Not infinity or NaN

