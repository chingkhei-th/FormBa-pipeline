import logging
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define caste mappings
OBC_CASTES = ["MEITEI", "MEETEI", "MEITEI PANGAL"]
SC_CASTES = ["LOIS"]
# All other castes will be mapped to ST

def determine_category(caste_name: str) -> str:
    """
    Determine the caste category (OBC/SC/ST) based on the caste name.
    
    Args:
        caste_name (str): The standardized caste name
        
    Returns:
        str: The determined category (OBC, SC, or ST)
    """
    caste_name = caste_name.upper().strip()
    
    # Check for Meitei variants (OBC)
    if any(variant in caste_name for variant in OBC_CASTES):
        logger.info(f"Mapped '{caste_name}' to OBC category")
        return "OBC"
    
    # Check for SC castes
    if any(sc_caste in caste_name for sc_caste in SC_CASTES):
        logger.info(f"Mapped '{caste_name}' to SC category")
        return "Scheduled Caste"
    
    # Default to ST
    logger.info(f"Mapped '{caste_name}' to ST category (default)")
    return "Scheduled Tribe"

def process(df, model_name):
    """
    Map caste categories based on caste names in the DataFrame.
    
    Args:
        df (pd.DataFrame): Input DataFrame
        model_name (str): Name of the extraction model
        
    Returns:
        pd.DataFrame: Processed DataFrame with mapped caste categories
    """
    logger.info("Starting caste category mapping")
    
    # Check if both required fields exist
    if not (df['Field'] == 'caste_name').any() or not (df['Field'] == 'caste').any():
        logger.warning("Required fields 'caste_name' and 'caste' not found in DataFrame")
        return df
    
    # Get caste name value
    caste_name_row = df[df['Field'] == 'caste_name'].iloc[0]
    caste_name = str(caste_name_row['Value']).upper()
    
    # Determine category
    category = determine_category(caste_name)
    
    # Update caste field
    df.loc[df['Field'] == 'caste', 'Value'] = category
    
    logger.info(f"Updated caste category to {category} based on caste name: {caste_name}")
    return df
