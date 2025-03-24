# config.py
from typing import List, Dict

# Task configurations with required fields
TASK_CONFIGS = {
    "handle_special_chars": {"required_fields": None},  # Apply to all fields
    "handle_null_values": {"required_fields": None},
    "normalize_gender": {"required_fields": ["gender"]},
    "handle_aadhaar": {"required_fields": ["aadhaarno"]},
    "handle_dob": {"required_fields": ["dob"]},
    "clean_school_name": {"required_fields": ["school"]},
    "remove_marks": {"required_fields": ["marks"]},
    "normalize_division": {"required_fields": ["division"]},
    "clean_names": {
        "required_fields": [
            "fathername",
            "name",
            "relative",
            "mother_name",
            "father_name",
            "exam_name",
            "degree",
        ]
    },
    "standardize_caste_name": {"required_fields": ["caste_name"]},
    "map_caste_category": {"required_fields": ["caste_name", "caste"]},
    "normalize_passout": {"required_fields": ["passout"]},
    "clean_roll": {"required_fields": ["roll_number"]},
}

# Order of task execution
PROCESS_TASKS: List[str] = [
    "handle_null_values",
    "clean_names",
    "handle_special_chars",
    "normalize_division",
    "handle_aadhaar",
    "normalize_gender",
    "handle_dob",
    "clean_school_name",
    "remove_marks",
    "standardize_caste_name",
    "map_caste_category",
    "normalize_passout",
    "clean_roll",
]
