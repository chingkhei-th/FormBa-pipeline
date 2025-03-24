import re
import pandas as pd


def process(df, model_name):
    """
    Handle Aadhaar-specific logic: Remove Aadhaar number from other fields
    and ensure Aadhaar number is correctly populated in the 'aadhaarno' field.

    Args:
        df (pd.DataFrame): Input DataFrame.
        model_name (str): Name of the extraction model.

    Returns:
        pd.DataFrame: Processed DataFrame.
    """
    if model_name != "aadhaar":
        return df  # Only apply to Aadhaar model

    # Ensure 'Value' column is treated as strings and preserve empty values as blanks
    df["Value"] = df["Value"].fillna("").astype(str)

    # Locate the existing Aadhaar number in the 'aadhaarno' field, if any
    aadhaarno_row = df[df["Field"] == "aadhaarno"]
    aadhaarno = None
    if not aadhaarno_row.empty:
        value = aadhaarno_row.iloc[0]["Value"]
        if re.match(r"^\d{4} \d{4} \d{4}$", value):
            aadhaarno = value

    # If Aadhaar number is not already in 'aadhaarno', search other fields
    if not aadhaarno:
        for idx, row in df.iterrows():
            match = re.search(r"(\d{4} \d{4} \d{4})", row["Value"])
            if match:
                aadhaarno = match.group(1)

                # Assign the Aadhaar number to the 'aadhaarno' field
                if aadhaarno_row.empty:
                    df = pd.concat(
                        [
                            df,
                            pd.DataFrame(
                                [
                                    {
                                        "Original Image": row["Original Image"],
                                        "Field": "aadhaarno",
                                        "Value": aadhaarno,
                                    }
                                ]
                            ),
                        ],
                        ignore_index=True,
                    )
                else:
                    df.loc[df["Field"] == "aadhaarno", "Value"] = aadhaarno
                break

    # Remove the Aadhaar number from other fields
    if aadhaarno:
        for idx, row in df.iterrows():
            if aadhaarno in row["Value"] and row["Field"] != "aadhaarno":
                df.at[idx, "Value"] = row["Value"].replace(aadhaarno, "").strip()

    return df
