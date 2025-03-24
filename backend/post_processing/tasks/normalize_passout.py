# tasks/normalize_passout.py
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define character to number mappings
CHAR_TO_NUM = {
    "!": "1",
    "I": "1",
    "l": "1",
    "i": "1",
    "S": "5",
    "s": "5",
    "O": "0",
    "o": "0",
}


def clean_year_string(year_str: str) -> str:
    """Clean and standardize the year string."""
    if not isinstance(year_str, str):
        return str(year_str)
    return str(year_str).strip()


def substitute_characters(year_str: str) -> str:
    """Replace look-alike characters with their numeric equivalents."""
    for char, num in CHAR_TO_NUM.items():
        year_str = year_str.replace(char, num)
    return year_str


def normalize_year(year_str: str) -> str:
    """
    Normalize year by:
    1. Substituting look-alike characters with numbers
    2. Extracting and formatting the year

    Args:
        year_str: Input year string

    Returns:
        str: Normalized year in YYYY format
    """
    try:
        year_str = clean_year_string(year_str)

        # First substitute characters that look like numbers
        year_str = substitute_characters(year_str)

        # Extract all numbers from the string
        numbers = re.findall(r"\d+", year_str)
        if not numbers:
            logger.warning(f"No numeric values found after substitution in: {year_str}")
            return year_str

        # Case: "2010 - 12)" → last number is short year
        if len(numbers) >= 2:
            last_num = numbers[-1]
            if len(last_num) <= 2:
                return "20" + last_num.zfill(2)

        # Extract last 4 digits if present
        digits = "".join(numbers)
        if len(digits) >= 4:
            return digits[-4:]

        # Handle 3-digit years
        if len(digits) == 3:
            return f"2{digits}"

        # If 2 digits or less, assume 2000s
        if len(digits) <= 2:
            return f"20{digits.zfill(2)}"

        logger.warning(f"Could not normalize year: {year_str}")
        return year_str

    except Exception as e:
        logger.error(f"Error normalizing year '{year_str}': {str(e)}")
        return year_str


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Process the DataFrame to normalize passout years."""
    mask = df["Field"] == "passout"
    if mask.any():
        df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
            lambda x: normalize_year(x) if pd.notna(x) else None
        )
        logger.info("Normalized passout years with character substitutions")
    return df
