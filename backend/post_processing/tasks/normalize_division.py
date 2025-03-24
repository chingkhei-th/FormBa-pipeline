# tasks/normalize_division.py
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DivisionNormalizer:
    DIVISION_MAPPINGS = {
        # Word format
        "first": "1st division",
        "second": "2nd division",
        "third": "3rd division",
        # Roman numerals (both cases)
        "i": "1st division",
        "ii": "2nd division",
        "iii": "3rd division",
        "I": "1st division",
        "II": "2nd division",
        "III": "3rd division",
        # Numeric with suffix
        "1st": "1st division",
        "2nd": "2nd division",
        "3rd": "3rd division",
        # Just numbers
        "1": "1st division",
        "2": "2nd division",
        "3": "3rd division",
    }

    @staticmethod
    def is_cgpa(value: str) -> bool:
        value = value.strip()
        try:
            num = float(value.replace(" ", "."))
            return 0 <= num <= 10
        except ValueError:
            return False

    @staticmethod
    def normalize_division(value: str) -> str:
        if not isinstance(value, str):
            value = str(value)

        original_value = value.strip()

        # First check if it's in DIVISION_MAPPINGS (before any transformations)
        if original_value in DivisionNormalizer.DIVISION_MAPPINGS:
            return DivisionNormalizer.DIVISION_MAPPINGS[original_value]

        # Then check for CGPA
        if DivisionNormalizer.is_cgpa(original_value):
            try:
                num = float(original_value.replace(" ", "."))
                return f"{num:.1f} CGPA"
            except ValueError:
                pass

        # For remaining cases, do case-insensitive matching
        value = value.lower().strip()
        value = re.sub(r"[,\s]+", " ", value)
        value = value.replace("division", "").strip()

        if value in DivisionNormalizer.DIVISION_MAPPINGS:
            return DivisionNormalizer.DIVISION_MAPPINGS[value]

        for key in DivisionNormalizer.DIVISION_MAPPINGS:
            if key in value:
                return DivisionNormalizer.DIVISION_MAPPINGS[key]

        logger.warning(f"Could not normalize division value: {original_value}")
        return original_value


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    mask = df["Field"] == "division"
    if mask.any():
        df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
            lambda x: DivisionNormalizer.normalize_division(x) if pd.notna(x) else None
        )
    return df
