"""
Content generation node for creating tweets from Reddit posts.

This module uses GPT-4o to generate engaging, concise tweets
based on viral Reddit posts.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import openai
from openai import AsyncOpenAI

from ..state import TrendState, ScoredPost, GeneratedPost
from ..config import get_openai_config
from ..database import update_post_content

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Content generator using GPT-4o for tweet creation."""
    
    def __init__(self):
        self.openai_config = get_openai_config()
        self.client = AsyncOpenAI(api_key=self.openai_config.api_key)
        
        # Tweet generation prompt template
        self.tweet_prompt_template = """
You are a social media expert creating engaging tweets from viral Reddit content.

Reddit Post Details:
- Title: {title}
- Subreddit: r/{subreddit}
- Upvotes: {upvotes}
- Comments: {num_comments}
- URL: {url}

Instructions:
1. Create a concise, engaging tweet (max 280 characters)
2. Capture the essence of what made this post viral
3. Use appropriate hashtags (1-3 max)
4. Make it shareable and interesting to a general audience
5. Include the original URL if it adds value
6. Maintain a tone that's informative yet engaging
7. Don't use excessive emojis or clickbait language

The tweet should feel natural and authentic, not like automated content.

Tweet:"""
    
    def _create_generation_prompt(self, post: ScoredPost) -> str:
        """Create the prompt for GPT-4o based on the scored post."""
        return self.tweet_prompt_template.format(
            title=post.raw_post.title,
            subreddit=post.raw_post.subreddit,
            upvotes=post.raw_post.upvotes,
            num_comments=post.raw_post.num_comments,
            url=post.raw_post.url
        )
    
    async def generate_tweet(self, post: ScoredPost) -> Optional[str]:
        """
        Generate a tweet for a single scored post.
        
        Args:
            post: ScoredPost object with Reddit data and virality score
            
        Returns:
            Optional[str]: Generated tweet text or None if generation fails
        """
        try:
            prompt = self._create_generation_prompt(post)
            
            response = await self.client.chat.completions.create(
                model=self.openai_config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media expert who creates engaging, authentic tweets from viral content. Always stay within the 280 character limit."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=100,  # Tweets are short
                temperature=0.7,  # Some creativity but not too random
                top_p=0.9
            )
            
            tweet_text = response.choices[0].message.content.strip()
            
            # Validate tweet length
            if len(tweet_text) > 280:
                logger.warning(f"Generated tweet too long ({len(tweet_text)} chars), truncating")
                tweet_text = tweet_text[:277] + "..."
            
            logger.debug(f"Generated tweet for {post.reddit_id}: {tweet_text}")
            return tweet_text
            
        except Exception as e:
            logger.error(f"Error generating tweet for post {post.reddit_id}: {e}")
            return None
    
    async def generate_tweets_batch(self, posts: List[ScoredPost]) -> List[GeneratedPost]:
        """
        Generate tweets for multiple posts in parallel.
        
        Args:
            posts: List of ScoredPost objects
            
        Returns:
            List[GeneratedPost]: List of posts with generated content
        """
        generated_posts = []
        
        # Create tasks for parallel generation
        tasks = []
        for post in posts:
            task = self.generate_tweet(post)
            tasks.append((post, task))
        
        # Execute tasks with some concurrency control
        semaphore = asyncio.Semaphore(5)  # Limit concurrent API calls
        
        async def generate_with_semaphore(post, task):
            async with semaphore:
                tweet_text = await task
                return post, tweet_text
        
        # Wait for all generations to complete
        results = await asyncio.gather(
            *[generate_with_semaphore(post, task) for post, task in tasks],
            return_exceptions=True
        )
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch generation: {result}")
                continue
            
            post, tweet_text = result
            
            if tweet_text:
                generated_post = GeneratedPost(
                    scored_post=post,
                    tweet_text=tweet_text
                )
                generated_posts.append(generated_post)
                logger.debug(f"Successfully generated content for {post.reddit_id}")
            else:
                logger.warning(f"Failed to generate content for {post.reddit_id}")
        
        logger.info(f"Generated content for {len(generated_posts)}/{len(posts)} posts")
        return generated_posts
    
    def validate_tweet_content(self, tweet_text: str) -> Dict[str, Any]:
        """
        Validate generated tweet content.
        
        Returns:
            Dict with validation results and suggestions
        """
        validation = {
            "valid": True,
            "length": len(tweet_text),
            "issues": [],
            "suggestions": []
        }
        
        # Check length
        if len(tweet_text) > 280:
            validation["valid"] = False
            validation["issues"].append(f"Tweet too long: {len(tweet_text)} characters")
            validation["suggestions"].append("Shorten the tweet to fit 280 character limit")
        
        # Check for common issues
        if tweet_text.count('#') > 3:
            validation["issues"].append("Too many hashtags")
            validation["suggestions"].append("Limit hashtags to 3 or fewer")
        
        if tweet_text.count('http') > 1:
            validation["issues"].append("Multiple URLs detected")
            validation["suggestions"].append("Include only one URL per tweet")
        
        # Check for spam-like content
        spam_indicators = ['!!!', 'AMAZING', 'INCREDIBLE', 'YOU WON\'T BELIEVE']
        for indicator in spam_indicators:
            if indicator in tweet_text.upper():
                validation["issues"].append("Potential spam-like language detected")
                validation["suggestions"].append("Use more natural, authentic language")
                break
        
        return validation
    
    async def improve_tweet(self, original_tweet: str, issues: List[str]) -> Optional[str]:
        """
        Attempt to improve a tweet based on validation issues.
        
        Args:
            original_tweet: The original generated tweet
            issues: List of issues to address
            
        Returns:
            Optional[str]: Improved tweet or None if improvement fails
        """
        try:
            improvement_prompt = f"""
Please improve this tweet to address the following issues:
Issues: {', '.join(issues)}

Original tweet: {original_tweet}

Create an improved version that:
1. Stays under 280 characters
2. Addresses the mentioned issues
3. Maintains the core message and engagement
4. Sounds natural and authentic

Improved tweet:"""
            
            response = await self.client.chat.completions.create(
                model=self.openai_config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media expert improving tweet content to meet platform guidelines and best practices."
                    },
                    {
                        "role": "user",
                        "content": improvement_prompt
                    }
                ],
                max_tokens=100,
                temperature=0.5  # Less creative for improvements
            )
            
            improved_tweet = response.choices[0].message.content.strip()
            
            # Validate the improvement
            validation = self.validate_tweet_content(improved_tweet)
            if validation["valid"]:
                return improved_tweet
            else:
                logger.warning("Tweet improvement still has issues")
                return None
                
        except Exception as e:
            logger.error(f"Error improving tweet: {e}")
            return None


# Global content generator instance
generator = ContentGenerator()


async def generate_content_node(state: TrendState) -> TrendState:
    """
    LangGraph node for generating tweet content.
    
    This node takes scored posts that meet the virality threshold
    and generates tweet content for them.
    """
    logger.info("Starting generate content node")
    state.update_step("generating")
    
    try:
        # Get posts that meet the threshold
        posts_to_generate = state.get_posts_above_threshold()
        
        if not posts_to_generate:
            logger.info("No posts meet virality threshold, skipping content generation")
            return state
        
        logger.info(f"Generating content for {len(posts_to_generate)} posts")
        
        # Generate tweets for all qualifying posts
        generated_posts = await generator.generate_tweets_batch(posts_to_generate)
        
        # Update database with generated content
        for generated_post in generated_posts:
            try:
                await update_post_content(
                    reddit_id=generated_post.reddit_id,
                    tweet_text=generated_post.tweet_text
                )
            except Exception as e:
                logger.warning(f"Error updating post content in database: {e}")
        
        # Add generated posts to state
        state.add_generated_posts(generated_posts)
        
        logger.info(f"Generate content node completed: {len(generated_posts)} tweets generated")
        return state
        
    except Exception as e:
        error_msg = f"Error in generate content node: {e}"
        logger.error(error_msg)
        state.fail_workflow(error_msg)
        return state


# Utility functions for testing and analysis
async def test_generate_single(title: str, subreddit: str, upvotes: int, url: str) -> Optional[str]:
    """Test function to generate a tweet for given parameters."""
    from ..state import RawPost, ScoredPost
    from datetime import datetime
    
    # Create test post
    raw_post = RawPost(
        reddit_id="test",
        title=title,
        url=url,
        upvotes=upvotes,
        created_utc=datetime.utcnow().timestamp() - 3600,  # 1 hour ago
        subreddit=subreddit,
        permalink="https://reddit.com/test",
        num_comments=upvotes // 10,
        upvote_ratio=0.9
    )
    
    scored_post = ScoredPost(
        raw_post=raw_post,
        score=upvotes / 60,  # Simple score
        meets_threshold=True
    )
    
    return await generator.generate_tweet(scored_post)


async def test_batch_generation(posts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Test function for batch tweet generation."""
    from ..state import RawPost, ScoredPost
    from datetime import datetime
    
    scored_posts = []
    
    for data in posts_data:
        raw_post = RawPost(
            reddit_id=data.get("id", "test"),
            title=data.get("title", "Test Title"),
            url=data.get("url", "https://example.com"),
            upvotes=data.get("upvotes", 100),
            created_utc=datetime.utcnow().timestamp() - 3600,
            subreddit=data.get("subreddit", "test"),
            permalink="https://reddit.com/test",
            num_comments=data.get("comments", 10),
            upvote_ratio=0.9
        )
        
        scored_post = ScoredPost(
            raw_post=raw_post,
            score=data.get("upvotes", 100) / 60,
            meets_threshold=True
        )
        
        scored_posts.append(scored_post)
    
    generated_posts = await generator.generate_tweets_batch(scored_posts)
    
    return [
        {
            "reddit_id": post.reddit_id,
            "title": post.scored_post.raw_post.title,
            "tweet_text": post.tweet_text,
            "character_count": len(post.tweet_text)
        }
        for post in generated_posts
    ]


def analyze_tweet_quality(tweets: List[str]) -> Dict[str, Any]:
    """Analyze the quality of generated tweets."""
    if not tweets:
        return {"error": "No tweets to analyze"}
    
    total_tweets = len(tweets)
    valid_tweets = 0
    total_length = 0
    hashtag_counts = []
    url_counts = []
    
    for tweet in tweets:
        validation = generator.validate_tweet_content(tweet)
        if validation["valid"]:
            valid_tweets += 1
        
        total_length += len(tweet)
        hashtag_counts.append(tweet.count('#'))
        url_counts.append(tweet.count('http'))
    
    return {
        "total_tweets": total_tweets,
        "valid_tweets": valid_tweets,
        "validity_rate": valid_tweets / total_tweets,
        "avg_length": total_length / total_tweets,
        "avg_hashtags": sum(hashtag_counts) / total_tweets,
        "avg_urls": sum(url_counts) / total_tweets,
        "length_distribution": {
            "under_100": len([t for t in tweets if len(t) < 100]),
            "100_200": len([t for t in tweets if 100 <= len(t) < 200]),
            "200_280": len([t for t in tweets if 200 <= len(t) <= 280]),
            "over_280": len([t for t in tweets if len(t) > 280])
        }
    }

