"""
Pydantic models for climate news analysis.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class NewsArticle(BaseModel):
    """A climate news article summary."""
    title: str
    summary: str
    source: str = Field(default="")
    reliability_score: int = Field(ge=1, le=10, default=7)
    sentiment: str = Field(default="Balanced", description="Alarmist, Balanced, or Dismissive")


class ClaimVerification(BaseModel):
    """Result of a climate claim verification."""
    claim: str
    verdict: str = Field(description="Verified, Partially Verified, Unverified, or False")
    confidence: int = Field(ge=0, le=100, default=50)
    explanation: str = Field(default="")
    sources: str = Field(default="")


class ClimateNewsDigest(BaseModel):
    """Daily climate news digest."""
    articles: List[NewsArticle] = Field(default_factory=list)
    digest_summary: str = Field(default="")
