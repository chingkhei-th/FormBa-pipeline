import logging
from difflib import SequenceMatcher
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the standard caste names
STANDARD_CASTE_NAMES = [
    "MEITEI",
    "MEETEI",
    "MEITEI PANGAL",
    "LOIS",
    "GANGTE",
    "KABUI",
    "RONGMEI",
    "TANGKHUL",
    "MAO",
    "THADOU",
    "Liangmai",
    "POUMAI",
    "KOM",
    "MATE",
    "VAIPHEI",
    "THADOU",
    "MARING",
    "ANAL",
    "CHOUBE",
    "Aimol",
    "KUKI",
    "HMAR",
    "PAITE",
    "DIMOL",
    "ROUMAI NAGA",
    "KHARAM",
]


def calculate_jaro_similarity(s1: str, s2: str) -> float:
    """Same Jaro similarity implementation as before"""
    # Previous implementation remains unchanged
    s1, s2 = s1.upper(), s2.upper()

    if s1 == s2:
        return 1.0

    if len(s1) == 0 or len(s2) == 0:
        return 0.0

    match_distance = (max(len(s1), len(s2)) // 2) - 1
    s1_matches = [False] * len(s1)
    s2_matches = [False] * len(s2)
    matches = 0
    transpositions = 0

    for i in range(len(s1)):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len(s2))

        for j in range(start, end):
            if not s2_matches[j] and s1[i] == s2[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len(s1)):
        if s1_matches[i]:
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

    transpositions = transpositions // 2

    return (
        matches / len(s1) + matches / len(s2) + (matches - transpositions) / matches
    ) / 3.0


def find_exact_word_match(input_name: str, standard_names: List[str]) -> str:
    """Same exact word matching implementation as before"""
    input_words = input_name.split()

    matching_standards = [
        name
        for name in standard_names
        if name in input_name
        and len(name.split()) >= len([w for w in input_words if w in name.split()])
    ]

    if matching_standards:
        return max(matching_standards, key=len)

    for word in input_words:
        if word in standard_names:
            return word

    return ""


def find_best_match(input_name: str, threshold: float = 0.70) -> Tuple[str, float]:
    """
    Find the best matching standard caste name using multiple methods.
    Lowered threshold to 0.75 for better fuzzy matching.
    """
    if not input_name:
        return ("", 0.0)

    input_name = input_name.upper().strip()

    # Log input name
    logging.info(f"Processing caste name: '{input_name}'")

    # Check exact match
    if input_name in STANDARD_CASTE_NAMES:
        logging.info(f"Found exact match: '{input_name}'")
        return (input_name, 1.0)

    # Try exact word match
    exact_match = find_exact_word_match(input_name, STANDARD_CASTE_NAMES)
    if exact_match:
        logging.info(f"Found exact word match: '{exact_match}' in '{input_name}'")
        return (exact_match, 1.0)

    # Use Jaro similarity
    best_match = ""
    best_score = 0.0

    # Log all similarity scores for debugging
    all_scores = []
    for standard_name in STANDARD_CASTE_NAMES:
        similarity = calculate_jaro_similarity(input_name, standard_name)
        all_scores.append((standard_name, similarity))
        if similarity > best_score:
            best_score = similarity
            best_match = standard_name

    # Log all similarity scores, sorted by score
    all_scores.sort(key=lambda x: x[1], reverse=True)
    logging.info("Similarity scores:")
    for name, score in all_scores[:3]:  # Show top 3 matches
        logging.info(f"  {name}: {score:.3f}")

    if best_score >= threshold:
        logging.info(
            f"Found similarity match: '{best_match}' (score: {best_score:.3f})"
        )
        return (best_match, best_score)

    logging.info(f"No good match found. Keeping original: '{input_name}'")
    return (input_name, best_score)


def process(df, model_name):
    """
    Standardize caste names in the DataFrame with logging.
    """
    logging.info(f"Starting caste name standardization for model: {model_name}")

    # Only process rows where Field is 'caste_name'
    mask = df["Field"] == "caste_name"

    # Apply standardization to matching rows
    df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
        lambda x: find_best_match(str(x))[0]
    )

    logging.info("Completed caste name standardization")
    return df
