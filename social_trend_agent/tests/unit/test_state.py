"""
Unit tests for state management components.
"""

import pytest
from datetime import datetime
from trend_graph.state import (
    PostData, PostResult, PostStatus, TrendState,
    create_post_result_from_data
)


class TestPostData:
    """Test PostData dataclass."""
    
    def test_post_data_creation(self, sample_post_data):
        """Test PostData creation."""
        assert sample_post_data.reddit_id == "test123"
        assert sample_post_data.title == "Test Post Title"
        assert sample_post_data.upvotes == 500
        assert sample_post_data.subreddit == "test"
    
    def test_post_data_to_dict(self, sample_post_data):
        """Test PostData to_dict method."""
        data_dict = sample_post_data.to_dict()
        
        assert isinstance(data_dict, dict)
        assert data_dict["reddit_id"] == "test123"
        assert data_dict["title"] == "Test Post Title"
        assert data_dict["upvotes"] == 500
        assert data_dict["subreddit"] == "test"
    
    def test_post_data_age_calculation(self, sample_post_data):
        """Test age calculation."""
        # Mock current time to be 1 hour after creation
        current_time = sample_post_data.created_utc + 3600
        age_hours = sample_post_data.get_age_hours(current_time)
        
        assert age_hours == 1.0
    
    def test_post_data_velocity_calculation(self, sample_post_data):
        """Test upvote velocity calculation."""
        # Mock current time to be 2 hours after creation
        current_time = sample_post_data.created_utc + 7200
        velocity = sample_post_data.get_upvote_velocity(current_time)
        
        # 500 upvotes / 2 hours = 250 upvotes per hour
        assert velocity == 250.0


class TestPostResult:
    """Test PostResult dataclass."""
    
    def test_post_result_creation(self, sample_post_result):
        """Test PostResult creation."""
        assert sample_post_result.reddit_id == "test123"
        assert sample_post_result.virality_score == 75.5
        assert sample_post_result.meets_threshold is True
        assert sample_post_result.status == PostStatus.GENERATED
    
    def test_post_result_to_dict(self, sample_post_result):
        """Test PostResult to_dict method."""
        result_dict = sample_post_result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["reddit_id"] == "test123"
        assert result_dict["virality_score"] == 75.5
        assert result_dict["status"] == "generated"
    
    def test_post_result_update_status(self, sample_post_result):
        """Test status update."""
        sample_post_result.update_status(PostStatus.POSTED)
        assert sample_post_result.status == PostStatus.POSTED
    
    def test_post_result_set_tweet_info(self, sample_post_result):
        """Test setting tweet information."""
        tweet_id = "1234567890"
        tweet_url = "https://twitter.com/user/status/1234567890"
        
        sample_post_result.set_tweet_info(tweet_id, tweet_url)
        
        assert sample_post_result.tweet_id == tweet_id
        assert sample_post_result.tweet_url == tweet_url
        assert sample_post_result.posted_at is not None
        assert sample_post_result.status == PostStatus.POSTED
    
    def test_post_result_set_metrics(self, sample_post_result):
        """Test setting engagement metrics."""
        sample_post_result.set_metrics(likes=25, retweets=8, replies=3)
        
        assert sample_post_result.likes == 25
        assert sample_post_result.retweets == 8
        assert sample_post_result.replies == 3


class TestPostStatus:
    """Test PostStatus enum."""
    
    def test_post_status_values(self):
        """Test PostStatus enum values."""
        assert PostStatus.SCRAPED.value == "scraped"
        assert PostStatus.SCORED.value == "scored"
        assert PostStatus.GENERATED.value == "generated"
        assert PostStatus.POSTED.value == "posted"
        assert PostStatus.FAILED.value == "failed"
    
    def test_post_status_from_string(self):
        """Test creating PostStatus from string."""
        assert PostStatus("scraped") == PostStatus.SCRAPED
        assert PostStatus("posted") == PostStatus.POSTED


class TestTrendState:
    """Test TrendState dataclass."""
    
    def test_trend_state_creation(self, sample_trend_state):
        """Test TrendState creation."""
        assert sample_trend_state.workflow_id == "test_workflow_123"
        assert len(sample_trend_state.scraped_posts) == 1
        assert sample_trend_state.current_step == "scrape_sources"
        assert sample_trend_state.start_time == 1640995200
    
    def test_trend_state_to_dict(self, sample_trend_state):
        """Test TrendState to_dict method."""
        state_dict = sample_trend_state.to_dict()
        
        assert isinstance(state_dict, dict)
        assert state_dict["workflow_id"] == "test_workflow_123"
        assert len(state_dict["scraped_posts"]) == 1
        assert state_dict["current_step"] == "scrape_sources"
    
    def test_add_scraped_post(self, sample_trend_state, sample_post_data):
        """Test adding scraped post."""
        new_post = PostData(
            reddit_id="test456",
            title="Another Test Post",
            url="https://reddit.com/r/test/comments/test456",
            subreddit="test",
            upvotes=300,
            created_utc=1640995300,
            author="another_author",
            selftext="Another test post content.",
            num_comments=15,
            permalink="/r/test/comments/test456/another_test_post/"
        )
        
        sample_trend_state.add_scraped_post(new_post)
        
        assert len(sample_trend_state.scraped_posts) == 2
        assert sample_trend_state.scraped_posts[1].reddit_id == "test456"
    
    def test_add_scored_post(self, sample_trend_state, sample_post_result):
        """Test adding scored post."""
        sample_trend_state.add_scored_post(sample_post_result)
        
        assert len(sample_trend_state.scored_posts) == 1
        assert sample_trend_state.scored_posts[0].reddit_id == "test123"
    
    def test_add_generated_post(self, sample_trend_state, sample_post_result):
        """Test adding generated post."""
        sample_trend_state.add_generated_post(sample_post_result)
        
        assert len(sample_trend_state.generated_posts) == 1
        assert sample_trend_state.generated_posts[0].reddit_id == "test123"
    
    def test_add_posted_result(self, sample_trend_state, sample_post_result):
        """Test adding posted result."""
        sample_post_result.status = PostStatus.POSTED
        sample_trend_state.add_posted_result(sample_post_result)
        
        assert len(sample_trend_state.posted_results) == 1
        assert sample_trend_state.posted_results[0].reddit_id == "test123"
    
    def test_add_error(self, sample_trend_state):
        """Test adding error."""
        error_msg = "Test error message"
        sample_trend_state.add_error(error_msg)
        
        assert len(sample_trend_state.errors) == 1
        assert sample_trend_state.errors[0] == error_msg
    
    def test_update_step(self, sample_trend_state):
        """Test updating current step."""
        sample_trend_state.update_step("score_virality")
        
        assert sample_trend_state.current_step == "score_virality"
        assert "scrape_sources" in sample_trend_state.completed_steps
    
    def test_get_summary(self, sample_trend_state):
        """Test getting state summary."""
        summary = sample_trend_state.get_summary()
        
        assert isinstance(summary, dict)
        assert summary["workflow_id"] == "test_workflow_123"
        assert summary["scraped_count"] == 1
        assert summary["scored_count"] == 0
        assert summary["generated_count"] == 0
        assert summary["posted_count"] == 0
        assert summary["error_count"] == 0
        assert summary["current_step"] == "scrape_sources"
    
    def test_is_complete(self, sample_trend_state):
        """Test workflow completion check."""
        # Initially not complete
        assert not sample_trend_state.is_complete()
        
        # Mark as complete
        sample_trend_state.current_step = "END"
        assert sample_trend_state.is_complete()
    
    def test_get_duration(self, sample_trend_state):
        """Test duration calculation."""
        # Mock current time to be 1 hour after start
        current_time = sample_trend_state.start_time + 3600
        duration = sample_trend_state.get_duration(current_time)
        
        assert duration == 3600.0


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_post_result_from_data(self, sample_post_data):
        """Test creating PostResult from PostData."""
        result = create_post_result_from_data(sample_post_data)
        
        assert isinstance(result, PostResult)
        assert result.reddit_id == sample_post_data.reddit_id
        assert result.title == sample_post_data.title
        assert result.upvotes == sample_post_data.upvotes
        assert result.status == PostStatus.SCRAPED
        assert result.virality_score is None
        assert result.meets_threshold is None
    
    def test_create_post_result_with_score(self, sample_post_data):
        """Test creating PostResult with virality score."""
        result = create_post_result_from_data(
            sample_post_data,
            virality_score=85.5,
            meets_threshold=True
        )
        
        assert result.virality_score == 85.5
        assert result.meets_threshold is True
        assert result.status == PostStatus.SCORED


class TestDataValidation:
    """Test data validation and edge cases."""
    
    def test_post_data_with_missing_fields(self):
        """Test PostData with minimal required fields."""
        post = PostData(
            reddit_id="minimal123",
            title="Minimal Post",
            url="https://reddit.com/minimal",
            subreddit="test",
            upvotes=0,
            created_utc=1640995200,
            author="test_user",
            selftext="",
            num_comments=0,
            permalink="/minimal"
        )
        
        assert post.reddit_id == "minimal123"
        assert post.upvotes == 0
        assert post.selftext == ""
        assert post.num_comments == 0
    
    def test_post_result_status_transitions(self):
        """Test valid status transitions."""
        result = PostResult(
            reddit_id="test123",
            title="Test",
            url="https://test.com",
            subreddit="test",
            upvotes=100,
            created_utc=1640995200,
            author="test",
            selftext="test",
            num_comments=5,
            permalink="/test",
            status=PostStatus.SCRAPED
        )
        
        # Valid transitions
        result.update_status(PostStatus.SCORED)
        assert result.status == PostStatus.SCORED
        
        result.update_status(PostStatus.GENERATED)
        assert result.status == PostStatus.GENERATED
        
        result.update_status(PostStatus.POSTED)
        assert result.status == PostStatus.POSTED
    
    def test_trend_state_empty_initialization(self):
        """Test TrendState with minimal initialization."""
        state = TrendState(
            workflow_id="empty_test",
            scraped_posts=[],
            scored_posts=[],
            generated_posts=[],
            posted_results=[],
            errors=[],
            current_step="start",
            completed_steps=[],
            start_time=1640995200,
            config={}
        )
        
        assert state.workflow_id == "empty_test"
        assert len(state.scraped_posts) == 0
        assert len(state.errors) == 0
        assert state.config == {}
    
    def test_post_data_edge_cases(self):
        """Test PostData with edge case values."""
        post = PostData(
            reddit_id="edge123",
            title="",  # Empty title
            url="https://reddit.com/edge",
            subreddit="test",
            upvotes=-5,  # Negative upvotes (possible with downvotes)
            created_utc=0,  # Unix epoch
            author="[deleted]",  # Deleted author
            selftext=None,  # None selftext
            num_comments=0,
            permalink="/edge"
        )
        
        assert post.title == ""
        assert post.upvotes == -5
        assert post.created_utc == 0
        assert post.author == "[deleted]"
        assert post.selftext is None

