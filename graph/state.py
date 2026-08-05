from typing import TypedDict


class ReviewState(TypedDict):
    """State passed between nodes in the review graph."""
    diff: str
    prompt: str
    result: str
