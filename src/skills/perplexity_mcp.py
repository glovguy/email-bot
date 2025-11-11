# import json
from enum import Enum
from typing import Dict, Any, List
from decouple import config
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("Perplexity Research Server")


PERPLEXITY_API_KEY: str | None = config("PERPLEXITY_API_KEY", default=None) # type: ignore
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY is not set")

class QuestionSize(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

class SearchRecencyFilter(Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

@mcp.tool()
def research_chat_completion(
    messages: List[Dict[str, str]],
    question_size: QuestionSize = QuestionSize.MEDIUM,
    search_recency_filter: SearchRecencyFilter = SearchRecencyFilter.YEAR,
    return_images: bool = False,
    return_related_questions: bool = False,
) -> Dict[str, Any]:
    if question_size == QuestionSize.SMALL:
        model = "sonar"
        max_tokens = "512"
        web_search_options_search_context_size = "low"
    elif question_size == QuestionSize.MEDIUM:
        model = "sonar-pro"
        max_tokens = "1024"
        return_related_questions = True
        web_search_options_search_context_size = "medium"
    elif question_size == QuestionSize.LARGE:
        model = "sonar-pro"
        max_tokens = "2048"
        return_related_questions = True
        web_search_options_search_context_size = "high"
    
    try:
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "return_images": return_images,
            "return_related_questions": return_related_questions,
            "search_recency_filter": search_recency_filter.value,
            "stream": False,
            "return_citations": True,
            "web_search_options": {
                "search_context_size": web_search_options_search_context_size,
            }
        }
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.request("POST", PERPLEXITY_API_URL, json=body, headers=headers)
        return {"success": True, "content": resp.json()}  # Sources are included in the response text
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="stdio")
