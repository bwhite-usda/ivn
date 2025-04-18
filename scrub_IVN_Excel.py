import pandas as pd
import re
import time
from fuzzywuzzy import process
from tqdm import tqdm  # For progress tracking


# ===========================
# Step 1: Load the Excel File
# ===========================


# Load the dataset into a pandas DataFrame
file_path = "ivntest.xlsx"  # Replace with your actual file name


# Use openpyxl to support .xlsx format
df = pd.read_excel(file_path, engine="openpyxl")


# Inspect the first few rows
print("Original Data Sample:")
print(df.head())


# ===================================
# Step 2: Define Cleaning Functions
# ===================================


def clean_text(text):
    """
    Cleans a given text string by:
    - Removing leading/trailing spaces
    - Standardizing spaces between words
    - Replacing en-dashes and em-dashes with hyphens
    - Ensuring consistent sentence spacing (one space after a period)
    - Standardizing quotation marks and apostrophes
    - Removing non-printable characters
    - Keeping original case (no lowercase conversion)
    """
    if not isinstance(text, str):  # Ensure input is a string
        return ""


    text = text.strip()  # Remove leading and trailing spaces
    text = re.sub(r"\s+", " ", text)  # Replace multiple spaces with a single space
    text = text.replace("–", "-").replace("—", "-")  # Replace en-dash and em-dash with hyphen
    text = text.replace("“", '"').replace("”", '"')  # Standardize double quotes
    text = text.replace("‘", "'").replace("’", "'")  # Standardize single quotes
    text = re.sub(r"\.\s+", ". ", text)  # Ensure one space after periods
    text = re.sub(r"[^a-zA-Z0-9.,;:'\"!?()\-\s]", "", text)  # Remove special characters (preserving punctuation)
    text = text.strip()  # Ensure no trailing spaces remain
    return text


# ==========================================
# Step 3: Apply Cleaning to Relevant Columns
# ==========================================


# Define the columns that need cleaning
columns_to_clean = ["Enabling Component", "Dependent Component"]


for col in columns_to_clean:
    if col in df.columns:  # Ensure the column exists
        df[col] = df[col].apply(clean_text)  # Apply cleaning function


# ===========================
# Step 4: Deduplicate Entries (With Progress Tracking)
# ===========================


def deduplicate_column(column_data):
    """
    Uses fuzzy matching to identify and replace near-duplicate component descriptions
    with a standardized version, ensuring consistent text formatting across the dataset.
    Prevents errors caused by empty or special-character-only strings.
    """
    unique_texts = {}  # Dictionary to store standardized versions of text
    cleaned_column = []  # List to store cleaned values
    total_entries = len(column_data)  # Total rows to process
    start_time = time.time()  # Track start time


    for index, text in enumerate(tqdm(column_data, desc="Deduplicating Entries", unit="entry")):
        # Skip empty or whitespace-only strings to avoid fuzzy matching errors
        if not text.strip():
            cleaned_column.append(text)
            continue


        if text in unique_texts:
            cleaned_column.append(unique_texts[text])  # Use existing standardized version
        else:
            # Ensure we're only matching against non-empty, valid texts
            non_empty_keys = [key for key in unique_texts.keys() if key.strip()]
            
            if non_empty_keys:
                result = process.extractOne(text, non_empty_keys, score_cutoff=90)
            else:
                result = None  # No valid matches available


            if result:  # Ensure extractOne() found a match
                match, score = result  # Unpack only if not None
                cleaned_column.append(unique_texts[match])  # Use closest match
            else:
                unique_texts[text] = text  # Add new unique text
                cleaned_column.append(text)


        # Progress tracking
        elapsed_time = time.time() - start_time
        avg_time_per_entry = elapsed_time / (index + 1)
        estimated_time_remaining = avg_time_per_entry * (total_entries - (index + 1))


        print(f"\rChecked: {index + 1}/{total_entries} | Remaining: {total_entries - (index + 1)} "
              f"| Estimated Time Left: {estimated_time_remaining:.2f} seconds", end="")


    return cleaned_column


# Apply deduplication to each relevant column
for col in columns_to_clean:
    if col in df.columns:
        df[col] = deduplicate_column(df[col])


# =============================
# Step 5: Ensure Consistent IDs
# =============================


if "Component ID" in df.columns:
    # Fill missing IDs with an auto-generated number
    df["Component ID"] = df["Component ID"].fillna(df.index + 1).astype(int)


# =========================
# Step 6: Save Cleaned Data
# =========================


# Save cleaned dataset to a new Excel file
output_file = "IVN_Dataset_Cleaned.xlsx"
df.to_excel(output_file, index=False, engine="openpyxl")


print(f"\n\nData cleaning complete! Cleaned file saved as: {output_file}")
