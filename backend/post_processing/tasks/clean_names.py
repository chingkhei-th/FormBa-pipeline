import re

# Define fields for which special character removal should apply
FIELDS_TO_PROCESS = ["fathername", "name", "relative", "mother_name", "father_name"]

# Define substrings to match and clean up
SUBSTRINGS_TO_REMOVE = ["S/O", "D/O", "W/O", "H/O"]
START_SUBSTRINGS_TO_REMOVE = [
    "DIO ",
    "SIO ",
    "WIO ",
    "HIO ",
    "MISS ",
    "MR. ",
    "MRS. ",
    "MS. ",
    "SMT. ",
    "SHRI ",
    "Km. ",
    "SO ",
    "DO ",
    "WO ",
    "HO ",
    "CO ",
    "Co "
    "MR ",
    "MRS ",
    "MS ",
    "SMT ",
    "MR.",
    "MRS.",
    "MS.",
    "SMT.",
    "Km.",
]

# Define number to letter mappings
NUMBER_TO_LETTER = {"0": "O", "1": "I", "5": "S"}


def remove_special_characters(df):
    """
    Clean names by:
    1. Mapping specific numbers to letters (0->O, 1->I, 5->S)
    2. Removing other numeric characters
    3. Removing special characters except parentheses and dots
    4. Removing specific prefixes
    5. Removing trailing dots

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: Processed DataFrame.
    """

    def clean_value(value, field):
        if field in FIELDS_TO_PROCESS:
            if not isinstance(value, str):
                value = str(value) if value is not None else ""

            # # Remove only specific substrings, preserving other special characters
            # for substring in SUBSTRINGS_TO_REMOVE:
            #     value = value.replace(substring, "").strip()

            # # Remove only specific starting substrings
            # for start_substring in START_SUBSTRINGS_TO_REMOVE:
            #     if value.startswith(start_substring):
            #         value = value[len(start_substring) :].strip()

            # Remove specific prefixes
            for substring in SUBSTRINGS_TO_REMOVE:
                value = value.replace(substring, "").strip()

            for start_substring in START_SUBSTRINGS_TO_REMOVE:
                if value.startswith(start_substring):
                    value = value[len(start_substring) :].strip()

            # Map specific numbers to letters
            for num, letter in NUMBER_TO_LETTER.items():
                value = value.replace(num, letter)

            # Remove remaining numeric characters
            value = re.sub(r"[2-46-9]", "", value)

            # Remove special characters except parentheses and dots
            # This pattern matches any character that is not:
            # - a letter (a-zA-Z)
            # - a space (\s)
            # - a parenthesis (\(\))
            # - a dot (\.)
            value = re.sub(r"[^a-zA-Z\s\(\)\.]", "", value)

            # Remove multiple spaces
            value = re.sub(r"\s+", " ", value)

            # Remove trailing dot or comma if present
            if value.endswith("."):
                value = value[:-1]
            elif value.endswith(","):
                value = value[:-1]

        return value.strip()

    # Apply cleaning logic to the 'Value' column
    df["Value"] = df.apply(lambda row: clean_value(row["Value"], row["Field"]), axis=1)
    return df


def process(df, model_name):
    """
    Process the DataFrame to remove only specific prefixes while preserving special characters.

    Args:
        df (pd.DataFrame): Input DataFrame.
        model_name (str): Name of the extraction model.

    Returns:
        pd.DataFrame: Processed DataFrame.
    """
    return remove_special_characters(df)
