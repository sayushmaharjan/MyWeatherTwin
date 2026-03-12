"""
BERT model loading — cached weather classification model.
"""

import os
import streamlit as st
import torch
from transformers import pipeline

from config import HF_TOKEN


@st.cache_resource
def load_weather_model():
    """
    Load a text-classification pipeline for weather classification.
    Uses facebook/bart-large-mnli for zero-shot classification initially,
    then falls back to a generic text-classification pipeline.
    """
    try:
        classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )

        # classifier = pipeline(
        #     "text-classification",
        #     device=0 if torch.cuda.is_available() else -1,
        # )

        return classifier
    except Exception as e:
        st.error(f"❌ Error loading BERT model: {e}")
        return None
