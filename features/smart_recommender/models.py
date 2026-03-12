"""
Pydantic models for smart recommendations.
"""

from pydantic import BaseModel, Field


class Recommendations(BaseModel):
    """Weather-based smart recommendations."""
    outfit: str = Field(default="", description="Clothing recommendation")
    exercise: str = Field(default="", description="Exercise/activity recommendation")
    commute: str = Field(default="", description="Commute advice")
    food: str = Field(default="", description="Food suggestion")
    photo_tip: str = Field(default="", description="Photography tip")
    activity: str = Field(default="", description="General activity suggestion")
    city: str = Field(default="")
