# tasks/handle_special_chars.py
import re
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_value(value: str) -> str:
    """
    Clean value by:
    1. Replacing newlines and tabs with spaces
    2. Preserving dots, parentheses, and brackets
    3. Standardizing whitespace without removing special characters
    4. Remove trailing comma
    """
    if not isinstance(value, str):
        return str(value)

    # Replace newlines and tabs with spaces
    value = re.sub(r"[\n\r\t]+", " ", value)

    # Replace multiple spaces with single space, being careful around special characters
    value = re.sub(r"(?<![.()\[\]])\s+(?![.()\[\]])", " ", value)

    # Clean up any doubled special characters while preserving singles
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"\({2,}", "(", value)
    value = re.sub(r"\){2,}", ")", value)

    # Trim leading/trailing whitespace
    value = value.strip()
    
    # Remove trailing comma
    value = value.rstrip(",") if value.endswith(",") else value

    return value


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Process the DataFrame to clean special characters in all values."""
    df.loc[:, "Value"] = df["Value"].apply(
        lambda x: clean_value(x) if pd.notna(x) else None
    )
    logger.info("Cleaned special characters while preserving dots and parentheses")
    return df
