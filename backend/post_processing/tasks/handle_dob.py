# tasks/handle_dob.py
import re
import pandas as pd
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str:
    """Parse date string into dd-mm-yyyy format."""
    if not isinstance(date_str, str):
        date_str = str(date_str)

    date_str = date_str.strip()
    date_str = re.sub(r"[,.\n\t\r]+", " ", date_str)
    date_str = re.sub(r"\s+", " ", date_str)
    date_str = re.sub(r"(\d+)(st|nd|rd|th|ª)", r"\1", date_str)

    # Try different date formats
    date_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue

    # Handle special case for dates with month names
    try:
        # For formats like "23/Feb/1993" or "23-Feb-1993"
        match = re.search(r"(\d{1,2})[-/]([a-zA-Z]{3,})[-/](\d{2,4})", date_str)
        if match:
            day, month, year = match.groups()
            month_dict = {
                "jan": "01",
                "feb": "02",
                "mar": "03",
                "apr": "04",
                "may": "05",
                "jun": "06",
                "jul": "07",
                "aug": "08",
                "sep": "09",
                "oct": "10",
                "nov": "11",
                "dec": "12",
            }
            month_num = month_dict.get(month[:3].lower())
            if month_num:
                if len(year) == 2:
                    year = "19" + year if int(year) > 50 else "20" + year
                return f"{day.zfill(2)}-{month_num}-{year}"
    except Exception:
        pass

    logger.warning(f"Could not parse date: {date_str}")
    return date_str


def process(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Process the DataFrame to handle DOB field based on Aadhaar presence."""
    # Check if both 'dob' and 'aadhaarno' fields exist
    has_dob = (df["Field"] == "dob").any()
    has_aadhaar = (df["Field"] == "aadhaarno").any()

    if has_dob:
        if has_aadhaar:
            # Format DOB if Aadhaar is present
            mask = df["Field"] == "dob"
            df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
                lambda x: parse_date(x) if pd.notna(x) else None
            )
        else:
            # Remove DOB if Aadhaar is not present
            df = df[df["Field"] != "dob"]

    return df
