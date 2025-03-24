import json
import pandas as pd
import importlib
import logging
from typing import Dict, Any, Set
from post_processing.config import PROCESS_TASKS, TASK_CONFIGS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def should_run_task(task_name: str, available_fields: Set[str]) -> bool:
    """Determine if a task should run based on available fields."""
    required_fields = TASK_CONFIGS[task_name]["required_fields"]
    # return (
    #     any(field in available_fields for field in required_fields)
    #     if required_fields
    #     else True
    # )
    
    # If no required fields specified, always run the task
    if required_fields is None:
        return True

    # Check if any required field is present
    return any(field in available_fields for field in required_fields)


def json_to_dataframe(json_data: Dict[str, Any]) -> pd.DataFrame:
    """Convert JSON data to DataFrame format required by processing tasks."""
    # return pd.DataFrame([{"Field": k, "Value": v} for k, v in json_data.items()])
    rows = []
    for field, value in json_data.items():
        rows.append({"Original Image": "", "Field": field, "Value": value})
    return pd.DataFrame(rows)


def dataframe_to_json(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert processed DataFrame back to JSON format."""
    # return df.set_index("Field")["Value"].to_dict()
    json_data = {}
    for _, row in df.iterrows():
        field = row["Field"]
        value = row["Value"]
        json_data[field] = value if pd.notna(value) else None
    return json_data


def process_extracted_data(
    extracted_data: Dict[str, Any], document_type: str
) -> Dict[str, Any]:
    """
    Process extracted data using configured tasks.

    Args:
        extracted_data: Raw extracted data from document
        document_type: Type of document (aadhaar, class10cbse, etc.)

    Returns:
        Processed data dictionary
    """
    try:
        # Convert to DataFrame
        df = json_to_dataframe(extracted_data)

        # Get available fields
        available_fields = set(df["Field"].unique())

        # Apply processing tasks
        for task_name in PROCESS_TASKS:
            if should_run_task(task_name, available_fields):
                try:
                    task_module = importlib.import_module(f"post_processing.tasks.{task_name}")
                    df = task_module.process(df, document_type)
                    logging.info(f"Applied {task_name} to {document_type} document")
                except Exception as e:
                    logging.error(f"Error in {task_name} for {document_type}: {str(e)}")

        # Convert back to JSON and return
        return dataframe_to_json(df)

    except Exception as e:
        logging.error(f"Error processing {document_type} document: {str(e)}")
        return extracted_data  # Return original data if processing fails
