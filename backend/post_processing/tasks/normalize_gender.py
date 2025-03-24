# tasks/normalize_gender.py
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_gender_value(value: str) -> str:
    """
    Normalize gender value by:
    1. Converting to lowercase
    2. Removing duplicates
    3. Capitalizing first letter
    """
    if not isinstance(value, str):
        return str(value)

    # Convert to lowercase and split by common separators
    parts = re.split(r"[/,\s]+", value.lower())

    # Remove duplicates and get unique gender
    unique_genders = list(set(parts))

    # If we have a gender, capitalize it
    if unique_genders:
        return unique_genders[0].capitalize()

    return value


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Process the DataFrame to normalize gender values."""
    mask = df["Field"] == "gender"
    if mask.any():
        df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
            lambda x: normalize_gender_value(x) if pd.notna(x) else None
        )
        logger.info("Normalized gender values in the data")

    return df
