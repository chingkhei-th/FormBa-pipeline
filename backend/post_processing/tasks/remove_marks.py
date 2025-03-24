# tasks/remove_marks.py
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Remove 'marks' field from the DataFrame if present."""
    if (df["Field"] == "marks").any():
        logger.info("Removing 'marks' field from the data")
        df = df[df["Field"] != "marks"]

    return df
