"""
Pytest configuration and fixtures for the social trend agent tests.
"""

import asyncio
import pytest
import tempfile
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from trend_graph.config import AppConfig
from trend_graph.database import init_database, close_database
from trend_graph.state import TrendState, PostData, PostResult, PostStatus


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_db() -> AsyncGenerator[str, None]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    # Set environment variable for test database
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    try:
        await init_database()
        yield db_path
    finally:
        await close_database()
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def mock_app_config() -> AppConfig:
    """Create a mock app configuration for testing."""
    return AppConfig(
        reddit_client_id="test_client_id",
        reddit_secret="test_secret",
        reddit_user_agent="TestBot/1.0",
        twitter_bearer_token="test_bearer",
        twitter_api_key="test_api_key",
        twitter_api_secret="test_api_secret",
        twitter_access_token="test_access_token",
        twitter_access_token_secret="test_access_secret",
        openai_api_key="test_openai_key",
        gpt_model="gpt-4o",
        min_score=100,
        subreddits=["test", "technology"],
        interval_minutes=5,
        host="localhost",
        port=8000,
        debug=True,
        log_level="DEBUG",
        log_format="text",
        database_url="sqlite:///test.db"
    )


@pytest.fixture
def sample_post_data() -> PostData:
    """Create sample post data for testing."""
    return PostData(
        reddit_id="test123",
        title="Test Post Title",
        url="https://reddit.com/r/test/comments/test123",
        subreddit="test",
        upvotes=500,
        created_utc=1640995200,  # 2022-01-01 00:00:00 UTC
        author="test_author",
        selftext="This is a test post content.",
        num_comments=25,
        permalink="/r/test/comments/test123/test_post_title/"
    )


@pytest.fixture
def sample_post_result() -> PostResult:
    """Create sample post result for testing."""
    return PostResult(
        reddit_id="test123",
        title="Test Post Title",
        url="https://reddit.com/r/test/comments/test123",
        subreddit="test",
        upvotes=500,
        created_utc=1640995200,
        author="test_author",
        selftext="This is a test post content.",
        num_comments=25,
        permalink="/r/test/comments/test123/test_post_title/",
        virality_score=75.5,
        meets_threshold=True,
        generated_content="This is a generated tweet about the test post! #trending",
        status=PostStatus.GENERATED,
        tweet_id=None,
        tweet_url=None,
        posted_at=None,
        likes=None,
        retweets=None,
        replies=None
    )


@pytest.fixture
def sample_trend_state() -> TrendState:
    """Create sample trend state for testing."""
    post_data = PostData(
        reddit_id="test123",
        title="Test Post Title",
        url="https://reddit.com/r/test/comments/test123",
        subreddit="test",
        upvotes=500,
        created_utc=1640995200,
        author="test_author",
        selftext="This is a test post content.",
        num_comments=25,
        permalink="/r/test/comments/test123/test_post_title/"
    )
    
    return TrendState(
        workflow_id="test_workflow_123",
        scraped_posts=[post_data],
        scored_posts=[],
        generated_posts=[],
        posted_results=[],
        errors=[],
        current_step="scrape_sources",
        completed_steps=[],
        start_time=1640995200,
        config={
            "min_score": 100,
            "subreddits": ["test", "technology"]
        }
    )


@pytest.fixture
def mock_reddit_client():
    """Create a mock Reddit client."""
    mock_client = MagicMock()
    
    # Mock subreddit
    mock_subreddit = MagicMock()
    mock_client.subreddit.return_value = mock_subreddit
    
    # Mock submission
    mock_submission = MagicMock()
    mock_submission.id = "test123"
    mock_submission.title = "Test Post Title"
    mock_submission.url = "https://reddit.com/r/test/comments/test123"
    mock_submission.subreddit.display_name = "test"
    mock_submission.score = 500
    mock_submission.created_utc = 1640995200
    mock_submission.author.name = "test_author"
    mock_submission.selftext = "This is a test post content."
    mock_submission.num_comments = 25
    mock_submission.permalink = "/r/test/comments/test123/test_post_title/"
    
    mock_subreddit.hot.return_value = [mock_submission]
    
    return mock_client


@pytest.fixture
def mock_twitter_client():
    """Create a mock Twitter client."""
    mock_client = MagicMock()
    
    # Mock create_tweet response
    mock_response = MagicMock()
    mock_response.data = {"id": "1234567890", "text": "Test tweet"}
    mock_client.create_tweet.return_value = mock_response
    
    # Mock get_tweet response
    mock_tweet_data = MagicMock()
    mock_tweet_data.public_metrics = {
        "like_count": 10,
        "retweet_count": 5,
        "reply_count": 2,
        "quote_count": 1
    }
    mock_tweet_response = MagicMock()
    mock_tweet_response.data = mock_tweet_data
    mock_client.get_tweet.return_value = mock_tweet_response
    
    return mock_client


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = MagicMock()
    
    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a generated tweet! #trending"
    mock_client.chat.completions.create.return_value = mock_response
    
    return mock_client


@pytest.fixture
def mock_stagehand_client():
    """Create a mock Stagehand client."""
    mock_client = AsyncMock()
    
    # Mock page navigation and extraction
    mock_client.page.goto = AsyncMock()
    mock_client.page.extract = AsyncMock(return_value={
        "posts": [
            {
                "title": "Test Post from Stagehand",
                "url": "https://example.com/post1",
                "score": 250,
                "comments": 15
            }
        ]
    })
    
    return mock_client


@pytest.fixture
def mock_workflow_dependencies(
    mock_reddit_client,
    mock_twitter_client,
    mock_openai_client,
    mock_stagehand_client
):
    """Create a bundle of mocked workflow dependencies."""
    return {
        "reddit_client": mock_reddit_client,
        "twitter_client": mock_twitter_client,
        "openai_client": mock_openai_client,
        "stagehand_client": mock_stagehand_client
    }


# Test data fixtures
@pytest.fixture
def reddit_post_json():
    """Sample Reddit post JSON data."""
    return {
        "id": "test123",
        "title": "Amazing Technology Breakthrough!",
        "url": "https://reddit.com/r/technology/comments/test123",
        "subreddit": "technology",
        "score": 1500,
        "created_utc": 1640995200,
        "author": "tech_enthusiast",
        "selftext": "Scientists have made an incredible breakthrough in quantum computing...",
        "num_comments": 150,
        "permalink": "/r/technology/comments/test123/amazing_technology_breakthrough/"
    }


@pytest.fixture
def twitter_metrics_json():
    """Sample Twitter metrics JSON data."""
    return {
        "data": {
            "id": "1234567890",
            "public_metrics": {
                "like_count": 25,
                "retweet_count": 8,
                "reply_count": 3,
                "quote_count": 2,
                "impression_count": 1000
            }
        }
    }


@pytest.fixture
def workflow_config():
    """Sample workflow configuration."""
    return {
        "min_score": 200,
        "subreddits": ["technology", "science", "programming"],
        "max_posts_per_run": 10,
        "tweet_template": "Check out this trending post: {title} {url} #trending"
    }


# Async test helpers
@pytest.fixture
async def async_mock():
    """Create an async mock for testing."""
    return AsyncMock()


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_environment():
    """Cleanup environment variables after each test."""
    original_env = os.environ.copy()
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Parametrized test data
@pytest.fixture(params=[
    {"min_score": 100, "expected_posts": 5},
    {"min_score": 500, "expected_posts": 2},
    {"min_score": 1000, "expected_posts": 1},
])
def score_threshold_data(request):
    """Parametrized data for score threshold testing."""
    return request.param


@pytest.fixture(params=["technology", "science", "programming", "artificial"])
def subreddit_names(request):
    """Parametrized subreddit names for testing."""
    return request.param

