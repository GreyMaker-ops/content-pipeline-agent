"""
Scrape node for extracting Reddit posts.

This module implements the scraping functionality using both Stagehand-py
for AI-powered web scraping and PRAW for Reddit API access.
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
import praw
from stagehand import Stagehand

from ..state import TrendState, RawPost
from ..config import get_reddit_config, get_stagehand_config, get_app_config
from ..database import save_post_record

logger = logging.getLogger(__name__)


class RedditScraper:
    """Reddit scraper using PRAW and Stagehand."""
    
    def __init__(self):
        self.reddit_config = get_reddit_config()
        self.stagehand_config = get_stagehand_config()
        self.app_config = get_app_config()
        self.reddit = None
        self.stagehand = None
    
    def _init_reddit(self) -> None:
        """Initialize Reddit API client."""
        if self.reddit is None:
            self.reddit = praw.Reddit(
                client_id=self.reddit_config.client_id,
                client_secret=self.reddit_config.client_secret,
                user_agent=self.reddit_config.user_agent
            )
            logger.info("Reddit API client initialized")
    
    async def _init_stagehand(self) -> None:
        """Initialize Stagehand client."""
        if self.stagehand is None:
            # Initialize Stagehand with configuration
            stagehand_kwargs = {}
            
            if self.stagehand_config.api_key:
                stagehand_kwargs['api_key'] = self.stagehand_config.api_key
            
            if self.stagehand_config.browserbase_api_key:
                stagehand_kwargs['browserbase_api_key'] = self.stagehand_config.browserbase_api_key
            
            if self.stagehand_config.browserbase_project_id:
                stagehand_kwargs['browserbase_project_id'] = self.stagehand_config.browserbase_project_id
            
            if self.stagehand_config.api_url:
                stagehand_kwargs['api_url'] = self.stagehand_config.api_url
            
            self.stagehand = Stagehand(**stagehand_kwargs)
            logger.info("Stagehand client initialized")
    
    async def scrape_subreddit_praw(self, subreddit_name: str, limit: int = 25) -> List[RawPost]:
        """Scrape subreddit using PRAW (Reddit API)."""
        self._init_reddit()
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            # Get hot posts from the subreddit
            for submission in subreddit.hot(limit=limit):
                # Skip stickied posts
                if submission.stickied:
                    continue
                
                raw_post = RawPost(
                    reddit_id=submission.id,
                    title=submission.title,
                    url=submission.url,
                    upvotes=submission.score,
                    created_utc=submission.created_utc,
                    subreddit=subreddit_name,
                    permalink=f"https://reddit.com{submission.permalink}",
                    num_comments=submission.num_comments,
                    upvote_ratio=submission.upvote_ratio
                )
                
                posts.append(raw_post)
                logger.debug(f"Scraped post: {submission.id} - {submission.title[:50]}...")
            
            logger.info(f"Scraped {len(posts)} posts from r/{subreddit_name} using PRAW")
            return posts
            
        except Exception as e:
            logger.error(f"Error scraping r/{subreddit_name} with PRAW: {e}")
            return []
    
    async def scrape_subreddit_stagehand(self, subreddit_name: str, limit: int = 25) -> List[RawPost]:
        """Scrape subreddit using Stagehand (AI-powered browser automation)."""
        await self._init_stagehand()
        
        try:
            # Navigate to subreddit
            url = f"https://www.reddit.com/r/{subreddit_name}/hot/"
            
            # Use Stagehand to extract post data
            result = await self.stagehand.extract(
                url=url,
                instruction=f"""
                Extract the top {limit} posts from this Reddit page. For each post, get:
                - Post ID (from the URL or data attributes)
                - Title
                - URL/link
                - Upvotes/score
                - Number of comments
                - Time posted (relative time like "2 hours ago")
                - Permalink to the Reddit post
                
                Return as a list of dictionaries with these fields.
                Skip any pinned/stickied posts.
                """
            )
            
            posts = []
            
            # Process Stagehand results
            if result and isinstance(result, list):
                for item in result[:limit]:
                    try:
                        # Convert relative time to UTC timestamp (approximate)
                        created_utc = self._parse_relative_time(item.get('time_posted', ''))
                        
                        raw_post = RawPost(
                            reddit_id=item.get('post_id', ''),
                            title=item.get('title', ''),
                            url=item.get('url', ''),
                            upvotes=int(item.get('upvotes', 0)),
                            created_utc=created_utc,
                            subreddit=subreddit_name,
                            permalink=item.get('permalink', ''),
                            num_comments=int(item.get('comments', 0)),
                            upvote_ratio=0.9  # Default since not available via scraping
                        )
                        
                        posts.append(raw_post)
                        logger.debug(f"Scraped post via Stagehand: {raw_post.reddit_id} - {raw_post.title[:50]}...")
                        
                    except Exception as e:
                        logger.warning(f"Error processing Stagehand result: {e}")
                        continue
            
            logger.info(f"Scraped {len(posts)} posts from r/{subreddit_name} using Stagehand")
            return posts
            
        except Exception as e:
            logger.error(f"Error scraping r/{subreddit_name} with Stagehand: {e}")
            return []
    
    def _parse_relative_time(self, time_str: str) -> float:
        """Parse relative time string to UTC timestamp (approximate)."""
        try:
            # Simple parsing for common Reddit time formats
            now = datetime.utcnow().timestamp()
            
            if 'hour' in time_str:
                hours = int(time_str.split()[0])
                return now - (hours * 3600)
            elif 'minute' in time_str:
                minutes = int(time_str.split()[0])
                return now - (minutes * 60)
            elif 'day' in time_str:
                days = int(time_str.split()[0])
                return now - (days * 86400)
            else:
                # Default to current time if can't parse
                return now
                
        except:
            # Fallback to current time
            return datetime.utcnow().timestamp()
    
    async def scrape_subreddit(self, subreddit_name: str, limit: int = 25) -> List[RawPost]:
        """
        Scrape subreddit using both PRAW and Stagehand, with PRAW as primary.
        
        This method tries PRAW first (more reliable and complete data),
        and falls back to Stagehand if PRAW fails.
        """
        logger.info(f"Starting to scrape r/{subreddit_name}")
        
        # Try PRAW first
        posts = await self.scrape_subreddit_praw(subreddit_name, limit)
        
        # If PRAW fails or returns no posts, try Stagehand
        if not posts:
            logger.info(f"PRAW failed for r/{subreddit_name}, trying Stagehand")
            posts = await self.scrape_subreddit_stagehand(subreddit_name, limit)
        
        return posts
    
    async def scrape_all_subreddits(self, workflow_id: str) -> List[RawPost]:
        """Scrape all configured subreddits."""
        all_posts = []
        
        for subreddit_name in self.app_config.subreddits:
            try:
                posts = await self.scrape_subreddit(subreddit_name)
                
                # Save posts to database
                for post in posts:
                    try:
                        await save_post_record(
                            reddit_id=post.reddit_id,
                            title=post.title,
                            url=post.url,
                            subreddit=post.subreddit,
                            permalink=post.permalink,
                            upvotes=post.upvotes,
                            num_comments=post.num_comments,
                            upvote_ratio=post.upvote_ratio,
                            created_utc=post.created_utc,
                            workflow_id=workflow_id
                        )
                    except Exception as e:
                        logger.warning(f"Error saving post {post.reddit_id}: {e}")
                
                all_posts.extend(posts)
                
                # Small delay between subreddits to be respectful
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping r/{subreddit_name}: {e}")
                continue
        
        logger.info(f"Total posts scraped: {len(all_posts)}")
        return all_posts


# Global scraper instance
scraper = RedditScraper()


async def scrape_sources_node(state: TrendState) -> TrendState:
    """
    LangGraph node for scraping Reddit sources.
    
    This node scrapes posts from configured subreddits and adds them
    to the workflow state.
    """
    logger.info("Starting scrape sources node")
    state.update_step("scraping")
    
    try:
        # Scrape all subreddits
        raw_posts = await scraper.scrape_all_subreddits(state.workflow_id)
        
        # Add posts to state
        state.add_raw_posts(raw_posts)
        
        logger.info(f"Scrape sources node completed: {len(raw_posts)} posts")
        return state
        
    except Exception as e:
        error_msg = f"Error in scrape sources node: {e}"
        logger.error(error_msg)
        state.fail_workflow(error_msg)
        return state


# Utility functions for testing
async def test_scrape_subreddit(subreddit_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Test function to scrape a single subreddit."""
    posts = await scraper.scrape_subreddit(subreddit_name, limit)
    return [post.to_dict() for post in posts]


async def test_scrape_all() -> List[Dict[str, Any]]:
    """Test function to scrape all configured subreddits."""
    posts = await scraper.scrape_all_subreddits("test-workflow")
    return [post.to_dict() for post in posts]

