# tasks/handle_null_values.py
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """
    Convert all null values to empty strings in the DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame with Field and Value columns
        model_name (str): Name of the OCR model used

    Returns:
        pd.DataFrame: DataFrame with null values replaced by empty strings
    """
    try:
        df["Value"] = df["Value"].fillna("")
        logger.info("Successfully converted null values to empty strings")
    except Exception as e:
        logger.error(f"Error handling null values: {str(e)}")

    return df
