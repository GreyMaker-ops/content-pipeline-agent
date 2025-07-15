"""
Integration tests for the complete workflow.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from trend_graph.graph import TrendWorkflow, run_trend_analysis
from trend_graph.state import TrendState, PostData, PostStatus


class TestTrendWorkflow:
    """Test TrendWorkflow integration."""
    
    @pytest.mark.asyncio
    async def test_workflow_initialization(self):
        """Test workflow initialization."""
        workflow = TrendWorkflow()
        
        assert workflow.graph is not None
        assert hasattr(workflow, 'workflow_id')
    
    @pytest.mark.asyncio
    async def test_workflow_execution_success(self, mock_workflow_dependencies, temp_db):
        """Test successful workflow execution."""
        # Mock all external dependencies
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            
            workflow = TrendWorkflow()
            
            # Create initial state
            initial_state = TrendState(
                workflow_id=workflow.workflow_id,
                scraped_posts=[],
                scored_posts=[],
                generated_posts=[],
                posted_results=[],
                errors=[],
                current_step="scrape_sources",
                completed_steps=[],
                start_time=1640995200,
                config={
                    "min_score": 50,  # Low threshold for testing
                    "subreddits": ["test"]
                }
            )
            
            # Execute workflow
            result = await workflow.execute(initial_state)
            
            # Verify workflow completed
            assert result is not None
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_workflow_with_no_posts(self, mock_workflow_dependencies, temp_db):
        """Test workflow when no posts are scraped."""
        # Mock Reddit client to return no posts
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_subreddit.hot.return_value = []  # No posts
        
        with patch('trend_graph.nodes.scrape.reddit_client', mock_reddit):
            workflow = TrendWorkflow()
            
            initial_state = TrendState(
                workflow_id=workflow.workflow_id,
                scraped_posts=[],
                scored_posts=[],
                generated_posts=[],
                posted_results=[],
                errors=[],
                current_step="scrape_sources",
                completed_steps=[],
                start_time=1640995200,
                config={
                    "min_score": 100,
                    "subreddits": ["empty_subreddit"]
                }
            )
            
            result = await workflow.execute(initial_state)
            
            # Should complete but with no posts processed
            assert result is not None
            assert len(result.get("posted_results", [])) == 0
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, temp_db):
        """Test workflow error handling."""
        # Mock Reddit client to raise an exception
        mock_reddit = MagicMock()
        mock_reddit.subreddit.side_effect = Exception("Reddit API error")
        
        with patch('trend_graph.nodes.scrape.reddit_client', mock_reddit):
            workflow = TrendWorkflow()
            
            initial_state = TrendState(
                workflow_id=workflow.workflow_id,
                scraped_posts=[],
                scored_posts=[],
                generated_posts=[],
                posted_results=[],
                errors=[],
                current_step="scrape_sources",
                completed_steps=[],
                start_time=1640995200,
                config={
                    "min_score": 100,
                    "subreddits": ["test"]
                }
            )
            
            result = await workflow.execute(initial_state)
            
            # Should handle error gracefully
            assert result is not None
            assert len(result.get("errors", [])) > 0


class TestRunTrendAnalysis:
    """Test run_trend_analysis function."""
    
    @pytest.mark.asyncio
    async def test_run_trend_analysis_success(self, mock_workflow_dependencies, temp_db):
        """Test successful trend analysis run."""
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            
            result = await run_trend_analysis(
                min_score=50,
                subreddits=["test"]
            )
            
            assert isinstance(result, dict)
            assert "success" in result
            assert "workflow_id" in result
            assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_run_trend_analysis_with_defaults(self, mock_workflow_dependencies, temp_db):
        """Test trend analysis with default parameters."""
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            
            result = await run_trend_analysis()
            
            assert isinstance(result, dict)
            assert "success" in result
    
    @pytest.mark.asyncio
    async def test_run_trend_analysis_error_handling(self, temp_db):
        """Test error handling in trend analysis."""
        # Mock a critical component to fail
        with patch('trend_graph.database.create_workflow_record', side_effect=Exception("Database error")):
            result = await run_trend_analysis()
            
            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result


class TestWorkflowSteps:
    """Test individual workflow steps in integration."""
    
    @pytest.mark.asyncio
    async def test_scrape_to_score_integration(self, mock_workflow_dependencies, temp_db):
        """Test integration between scrape and score steps."""
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']):
            from trend_graph.nodes.scrape import scrape_sources_node
            from trend_graph.nodes.score import score_virality_node
            
            # Create initial state
            state = TrendState(
                workflow_id="integration_test",
                scraped_posts=[],
                scored_posts=[],
                generated_posts=[],
                posted_results=[],
                errors=[],
                current_step="scrape_sources",
                completed_steps=[],
                start_time=1640995200,
                config={
                    "min_score": 50,
                    "subreddits": ["test"]
                }
            )
            
            # Execute scrape step
            scraped_state = await scrape_sources_node(state)
            
            # Verify posts were scraped
            assert len(scraped_state.scraped_posts) > 0
            assert scraped_state.current_step == "scrape_sources"
            
            # Execute score step
            scored_state = await score_virality_node(scraped_state)
            
            # Verify posts were scored
            assert len(scored_state.scored_posts) > 0
            assert scored_state.current_step == "score_virality"
            
            # Verify data consistency
            for scored_post in scored_state.scored_posts:
                assert scored_post.virality_score is not None
                assert scored_post.meets_threshold is not None
                assert scored_post.status == PostStatus.SCORED
    
    @pytest.mark.asyncio
    async def test_score_to_generate_integration(self, mock_workflow_dependencies, temp_db):
        """Test integration between score and generate steps."""
        with patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']):
            from trend_graph.nodes.score import score_virality_node
            from trend_graph.nodes.generate import generate_content_node
            from trend_graph.state import PostResult
            
            # Create state with scored posts
            scored_post = PostResult(
                reddit_id="test123",
                title="Test Post Title",
                url="https://reddit.com/test123",
                subreddit="test",
                upvotes=500,
                created_utc=1640995200,
                author="test_author",
                selftext="Test content",
                num_comments=25,
                permalink="/test123",
                virality_score=75.5,
                meets_threshold=True,
                status=PostStatus.SCORED
            )
            
            state = TrendState(
                workflow_id="integration_test",
                scraped_posts=[],
                scored_posts=[scored_post],
                generated_posts=[],
                posted_results=[],
                errors=[],
                current_step="score_virality",
                completed_steps=["scrape_sources"],
                start_time=1640995200,
                config={"min_score": 50}
            )
            
            # Execute generate step
            generated_state = await generate_content_node(state)
            
            # Verify content was generated
            assert len(generated_state.generated_posts) > 0
            assert generated_state.current_step == "generate_content"
            
            # Verify generated content
            for generated_post in generated_state.generated_posts:
                assert generated_post.generated_content is not None
                assert len(generated_post.generated_content) > 0
                assert generated_post.status == PostStatus.GENERATED
    
    @pytest.mark.asyncio
    async def test_generate_to_post_integration(self, mock_workflow_dependencies, temp_db):
        """Test integration between generate and post steps."""
        with patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            from trend_graph.nodes.generate import generate_content_node
            from trend_graph.nodes.post import post_content_node
            from trend_graph.state import PostResult
            
            # Create state with generated posts
            generated_post = PostResult(
                reddit_id="test123",
                title="Test Post Title",
                url="https://reddit.com/test123",
                subreddit="test",
                upvotes=500,
                created_utc=1640995200,
                author="test_author",
                selftext="Test content",
                num_comments=25,
                permalink="/test123",
                virality_score=75.5,
                meets_threshold=True,
                generated_content="This is a test tweet! #trending",
                status=PostStatus.GENERATED
            )
            
            state = TrendState(
                workflow_id="integration_test",
                scraped_posts=[],
                scored_posts=[],
                generated_posts=[generated_post],
                posted_results=[],
                errors=[],
                current_step="generate_content",
                completed_steps=["scrape_sources", "score_virality"],
                start_time=1640995200,
                config={"min_score": 50}
            )
            
            # Execute post step
            posted_state = await post_content_node(state)
            
            # Verify posts were posted
            assert len(posted_state.posted_results) > 0
            assert posted_state.current_step == "post_content"
            
            # Verify posted content
            for posted_post in posted_state.posted_results:
                assert posted_post.tweet_id is not None
                assert posted_post.tweet_url is not None
                assert posted_post.posted_at is not None
                assert posted_post.status == PostStatus.POSTED


class TestWorkflowPerformance:
    """Test workflow performance and scalability."""
    
    @pytest.mark.asyncio
    async def test_workflow_performance_timing(self, mock_workflow_dependencies, temp_db, performance_timer):
        """Test workflow execution timing."""
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            
            performance_timer.start()
            
            result = await run_trend_analysis(
                min_score=50,
                subreddits=["test"]
            )
            
            performance_timer.stop()
            
            # Verify workflow completed successfully
            assert result.get("success") is True
            
            # Performance should be reasonable (less than 30 seconds)
            assert performance_timer.duration < 30.0
    
    @pytest.mark.asyncio
    async def test_workflow_memory_usage(self, mock_workflow_dependencies, temp_db):
        """Test workflow memory usage with large datasets."""
        # Create a mock Reddit client that returns many posts
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit
        
        # Create many mock submissions
        mock_submissions = []
        for i in range(50):  # Large number of posts
            mock_submission = MagicMock()
            mock_submission.id = f"test{i}"
            mock_submission.title = f"Test Post {i}"
            mock_submission.url = f"https://reddit.com/test{i}"
            mock_submission.subreddit.display_name = "test"
            mock_submission.score = 100 + i * 10
            mock_submission.created_utc = 1640995200
            mock_submission.author.name = f"author{i}"
            mock_submission.selftext = f"Content {i}"
            mock_submission.num_comments = 10 + i
            mock_submission.permalink = f"/test{i}"
            mock_submissions.append(mock_submission)
        
        mock_subreddit.hot.return_value = mock_submissions
        
        with patch('trend_graph.nodes.scrape.reddit_client', mock_reddit), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_workflow_dependencies['twitter_client']):
            
            result = await run_trend_analysis(
                min_score=50,
                subreddits=["test"]
            )
            
            # Should handle large datasets without issues
            assert result.get("success") is True
            assert "summary" in result


class TestWorkflowErrorRecovery:
    """Test workflow error recovery and resilience."""
    
    @pytest.mark.asyncio
    async def test_workflow_partial_failure_recovery(self, mock_workflow_dependencies, temp_db):
        """Test workflow recovery from partial failures."""
        # Mock Twitter client to fail on first attempt, succeed on retry
        mock_twitter = MagicMock()
        call_count = 0
        
        def mock_create_tweet(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Twitter API error")
            else:
                mock_response = MagicMock()
                mock_response.data = {"id": "1234567890", "text": "Test tweet"}
                return mock_response
        
        mock_twitter.create_tweet.side_effect = mock_create_tweet
        
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.nodes.generate.openai_client', mock_workflow_dependencies['openai_client']), \
             patch('trend_graph.nodes.post.twitter_client', mock_twitter):
            
            result = await run_trend_analysis(
                min_score=50,
                subreddits=["test"]
            )
            
            # Should complete despite initial failure
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_workflow_database_error_handling(self, mock_workflow_dependencies):
        """Test workflow handling of database errors."""
        with patch('trend_graph.nodes.scrape.reddit_client', mock_workflow_dependencies['reddit_client']), \
             patch('trend_graph.database.create_workflow_record', side_effect=Exception("DB error")):
            
            result = await run_trend_analysis()
            
            # Should handle database errors gracefully
            assert isinstance(result, dict)
            assert result.get("success") is False

