"""
LangGraph workflow definition for the social trend agent.

This module defines the complete workflow graph that orchestrates
the scraping, scoring, and content generation process.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from .state import TrendState
from .nodes.scrape import scrape_sources_node
from .nodes.score import score_virality_node
from .nodes.generate import generate_content_node
from .nodes.post import post_content_node
from .database import (
    create_workflow_record, 
    update_workflow_step, 
    update_workflow_stats,
    complete_workflow,
    fail_workflow
)

logger = logging.getLogger(__name__)


def should_continue_to_scoring(state: TrendState) -> str:
    """
    Conditional edge function to determine if workflow should continue to scoring.
    
    Returns:
        str: Next node name or END
    """
    if state.error_message:
        logger.info("Workflow has error, ending")
        return END
    
    if not state.raw_posts:
        logger.info("No posts scraped, ending workflow")
        return END
    
    logger.info(f"Continuing to scoring with {len(state.raw_posts)} posts")
    return "score_virality"


def should_continue_to_generation(state: TrendState) -> str:
    """
    Conditional edge function to determine if workflow should continue to generation.
    
    Returns:
        str: Next node name or END
    """
    if state.error_message:
        logger.info("Workflow has error, ending")
        return END
    
    posts_above_threshold = state.get_posts_above_threshold()
    
    if not posts_above_threshold:
        logger.info("No posts meet virality threshold, ending workflow")
        return END
    
    logger.info(f"Continuing to generation with {len(posts_above_threshold)} posts")
    return "generate_content"


def should_continue_to_posting(state: TrendState) -> str:
    """
    Conditional edge function to determine if workflow should continue to posting.
    
    Returns:
        str: Next node name or END
    """
    if state.error_message:
        logger.info("Workflow has error, ending")
        return END
    
    if not state.generated_posts:
        logger.info("No content generated, ending workflow")
        return END
    
    logger.info(f"Continuing to posting with {len(state.generated_posts)} posts")
    return "post_content"


class TrendWorkflow:
    """Social trend analysis workflow using LangGraph."""
    
    def __init__(self):
        self.graph = None
        self._build_graph()
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow."""
        # Create the state graph
        workflow = StateGraph(TrendState)
        
        # Add nodes
        workflow.add_node("scrape_sources", scrape_sources_node)
        workflow.add_node("score_virality", score_virality_node)
        workflow.add_node("generate_content", generate_content_node)
        workflow.add_node("post_content", post_content_node)
        
        # Set entry point
        workflow.set_entry_point("scrape_sources")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "scrape_sources",
            should_continue_to_scoring,
            {
                "score_virality": "score_virality",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "score_virality",
            should_continue_to_generation,
            {
                "generate_content": "generate_content",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "generate_content",
            should_continue_to_posting,
            {
                "post_content": "post_content",
                END: END
            }
        )
        
        # Post content leads to end
        workflow.add_edge("post_content", END)
        
        # Compile the graph
        self.graph = workflow.compile()
        logger.info("LangGraph workflow compiled successfully")
    
    async def run_workflow(
        self, 
        min_score: Optional[float] = None,
        subreddits: Optional[list] = None
    ) -> TrendState:
        """
        Run the complete trend analysis workflow.
        
        Args:
            min_score: Override minimum virality score threshold
            subreddits: Override list of subreddits to scrape
            
        Returns:
            TrendState: Final state after workflow completion
        """
        # Generate unique workflow ID
        workflow_id = f"trend-{uuid.uuid4().hex[:8]}-{int(datetime.utcnow().timestamp())}"
        
        logger.info(f"Starting trend workflow: {workflow_id}")
        
        # Initialize state
        state = TrendState()
        state.start_workflow(workflow_id)
        
        # Override configuration if provided
        if min_score is not None:
            state.min_score = min_score
        if subreddits is not None:
            state.subreddits = subreddits
        
        try:
            # Create workflow record in database
            await create_workflow_record(
                workflow_id=workflow_id,
                min_score=state.min_score,
                subreddits=state.subreddits
            )
            
            # Run the workflow
            final_state = await self.graph.ainvoke(state)
            
            # Update final statistics
            await update_workflow_stats(
                workflow_id=workflow_id,
                scraped=final_state.total_scraped,
                scored=final_state.total_scored,
                generated=final_state.total_generated,
                posted=final_state.total_posted,
                failed=final_state.total_failed
            )
            
            # Mark workflow as completed
            if final_state.error_message:
                await fail_workflow(workflow_id, final_state.error_message)
                final_state.fail_workflow(final_state.error_message)
            else:
                await complete_workflow(workflow_id, success=True)
                final_state.complete_workflow()
            
            logger.info(f"Workflow {workflow_id} completed successfully")
            return final_state
            
        except Exception as e:
            error_msg = f"Workflow {workflow_id} failed: {e}"
            logger.error(error_msg)
            
            # Mark workflow as failed
            try:
                await fail_workflow(workflow_id, error_msg)
            except:
                pass  # Don't fail on database update failure
            
            state.fail_workflow(error_msg)
            return state
    
    def get_workflow_schema(self) -> Dict[str, Any]:
        """Get the workflow schema for visualization or documentation."""
        if not self.graph:
            return {}
        
        # Extract graph structure
        nodes = []
        edges = []
        
        # This is a simplified representation
        # In a real implementation, you'd extract from the compiled graph
        workflow_schema = {
            "nodes": [
                {
                    "id": "scrape_sources",
                    "name": "Scrape Sources",
                    "description": "Extract posts from Reddit using PRAW and Stagehand",
                    "type": "action"
                },
                {
                    "id": "score_virality",
                    "name": "Score Virality",
                    "description": "Calculate virality scores based on upvote velocity",
                    "type": "action"
                },
                {
                    "id": "generate_content",
                    "name": "Generate Content",
                    "description": "Create tweets using GPT-4o",
                    "type": "action"
                },
                {
                    "id": "post_content",
                    "name": "Post Content",
                    "description": "Publish tweets to Twitter using Tweepy",
                    "type": "action"
                }
            ],
            "edges": [
                {
                    "from": "scrape_sources",
                    "to": "score_virality",
                    "condition": "has_posts"
                },
                {
                    "from": "score_virality",
                    "to": "generate_content",
                    "condition": "above_threshold"
                },
                {
                    "from": "generate_content",
                    "to": "post_content",
                    "condition": "has_content"
                },
                {
                    "from": "post_content",
                    "to": "END",
                    "condition": "always"
                }
            ],
            "entry_point": "scrape_sources",
            "description": "Social trend analysis workflow that scrapes Reddit, scores virality, and generates tweets"
        }
        
        return workflow_schema


# Global workflow instance
workflow = TrendWorkflow()


async def run_trend_analysis(
    min_score: Optional[float] = None,
    subreddits: Optional[list] = None
) -> Dict[str, Any]:
    """
    Convenience function to run trend analysis and return results.
    
    Args:
        min_score: Override minimum virality score threshold
        subreddits: Override list of subreddits to scrape
        
    Returns:
        Dict: Workflow results and statistics
    """
    try:
        final_state = await workflow.run_workflow(min_score, subreddits)
        
        return {
            "success": not bool(final_state.error_message),
            "workflow_id": final_state.workflow_id,
            "duration_seconds": final_state.duration_seconds,
            "statistics": {
                "total_scraped": final_state.total_scraped,
                "total_scored": final_state.total_scored,
                "total_generated": final_state.total_generated,
                "total_posted": final_state.total_posted,
                "total_failed": final_state.total_failed,
                "success_rate": final_state.success_rate
            },
            "posts_above_threshold": len(final_state.get_posts_above_threshold()),
            "generated_content": len(final_state.generated_posts),
            "error_message": final_state.error_message,
            "configuration": {
                "min_score": final_state.min_score,
                "subreddits": final_state.subreddits
            }
        }
        
    except Exception as e:
        logger.error(f"Error running trend analysis: {e}")
        return {
            "success": False,
            "error_message": str(e),
            "workflow_id": None,
            "statistics": {}
        }


async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Get the status of a specific workflow.
    
    Args:
        workflow_id: ID of the workflow to check
        
    Returns:
        Dict: Workflow status information
    """
    try:
        from .database import get_workflow_record
        
        workflow_record = await get_workflow_record(workflow_id)
        
        if not workflow_record:
            return {
                "found": False,
                "error": "Workflow not found"
            }
        
        return {
            "found": True,
            "workflow_id": workflow_record.workflow_id,
            "started_at": workflow_record.started_at.isoformat(),
            "completed_at": workflow_record.completed_at.isoformat() if workflow_record.completed_at else None,
            "current_step": workflow_record.current_step,
            "success": workflow_record.success,
            "is_running": workflow_record.is_running,
            "duration_seconds": workflow_record.duration_seconds,
            "statistics": {
                "total_scraped": workflow_record.total_scraped,
                "total_scored": workflow_record.total_scored,
                "total_generated": workflow_record.total_generated,
                "total_posted": workflow_record.total_posted,
                "total_failed": workflow_record.total_failed,
                "success_rate": workflow_record.success_rate
            },
            "configuration": {
                "min_score": workflow_record.min_score,
                "subreddits": workflow_record.subreddits
            },
            "error_message": workflow_record.error_message
        }
        
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        return {
            "found": False,
            "error": str(e)
        }


# Utility functions for testing
async def test_workflow_step(step_name: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test individual workflow steps."""
    if step_name == "scrape":
        from .nodes.scrape import test_scrape_all
        return await test_scrape_all()
    
    elif step_name == "score":
        from .nodes.score import test_score_calculation
        return {
            "score": test_score_calculation(
                upvotes=test_data.get("upvotes", 100),
                age_minutes=test_data.get("age_minutes", 60),
                subreddit=test_data.get("subreddit", "test")
            )
        }
    
    elif step_name == "generate":
        from .nodes.generate import test_generate_single
        return {
            "tweet": await test_generate_single(
                title=test_data.get("title", "Test Title"),
                subreddit=test_data.get("subreddit", "test"),
                upvotes=test_data.get("upvotes", 100),
                url=test_data.get("url", "https://example.com")
            )
        }
    
    else:
        return {"error": f"Unknown step: {step_name}"}


def get_workflow_info() -> Dict[str, Any]:
    """Get information about the workflow structure."""
    return {
        "workflow_type": "LangGraph State Machine",
        "nodes": [
            "scrape_sources",
            "score_virality", 
            "generate_content",
            "post_content"
        ],
        "entry_point": "scrape_sources",
        "conditional_logic": [
            "Posts must be scraped to continue to scoring",
            "Posts must meet virality threshold to continue to generation",
            "Content must be generated to continue to posting"
        ],
        "state_tracking": "TrendState object maintains workflow state",
        "database_integration": "All steps persist data to SQLite",
        "error_handling": "Graceful failure with error state tracking"
    }

