# tasks/clean_school_name.py
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_school_name(value: str) -> str:
    """
    Clean school name by:
    1. Removing numeric values
    2. Removing special characters except comma and period
    3. Removing 'from' prefix if present
    4. Preserving letters, spaces, commas, and periods
    """
    if not isinstance(value, str):
        return str(value)

    # Remove 'from' prefix if it exists (case insensitive)
    value = re.sub(r"^from+", "", value, flags=re.IGNORECASE)

    # Remove numbers
    value = re.sub(r"\d+", "", value)

    # Keep only letters, spaces, commas, periods, and parentheses with their content
    # This pattern preserves parentheses and their content while removing other special characters
    value = re.sub(r"[^a-zA-Z\s,.'()-&]+", "", value)

    # Clean up multiple spaces
    value = re.sub(r"\s+", " ", value)

    # Remove spaces around commas and periods
    # value = re.sub(r"\s*([,.])\s*", r"\1", value)
    
    # Remove trailing dot if present
    if value.endswith(","):
        value = value[:-1]

    # Trim leading/trailing whitespace
    value = value.strip()

    return value


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Process the DataFrame to clean school names."""
    mask = df["Field"] == "school"
    if mask.any():
        df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
            lambda x: clean_school_name(x) if pd.notna(x) else None
        )
        logger.info("Cleaned school names in the data")

    return df
