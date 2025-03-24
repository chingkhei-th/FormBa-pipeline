# tasks/clean_roll.py
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_roll_number(value: str) -> str:
    """
    Remove dots from roll number values.

    Args:
        value: The roll number value to clean

    Returns:
        str: Cleaned roll number with dots removed
    """
    if not isinstance(value, str):
        value = str(value)
    return value.replace(".", "")


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """
    Process the DataFrame to remove dots from roll number values.

    Args:
        df: Input DataFrame with Field and Value columns
        model_name: Name of the extraction model

    Returns:
        pd.DataFrame: Processed DataFrame
    """
    mask = df["Field"] == "roll_number"
    if mask.any():
        df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
            lambda x: clean_roll_number(x) if pd.notna(x) else None
        )
        logger.info("Cleaned roll numbers by removing dots")

    return df
