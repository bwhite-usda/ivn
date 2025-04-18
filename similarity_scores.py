# This is similarity_scores_2025-03-17.py
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import product  # Used to generate combinations

# Load the Excel file
input_file = "ivntest.xlsx"
output_file = "similarity_scores_filtered.xlsx"

# Read the Excel file into a DataFrame
df = pd.read_excel(input_file)

# Check if required columns exist
if "Enabling Component Description" not in df.columns or "Dependent Component Description" not in df.columns:
    raise ValueError("The input file must contain columns 'Enabling Component Description' and 'Dependent Component Description'.")

# Fill missing values with an empty string to avoid issues with NaN
df = df.fillna("")

# Separate Enabling and Dependent components
enabling_df = df[[
    "Enabling Component Description",
    "Enabling Component",
    "Enabling Source",
    "Enabling Component URL",
    "Enabling Source Agency"
]].drop_duplicates()

dependent_df = df[[
    "Dependent Component Description",
    "Dependent Component",
    "Dependent Source",
    "Dependent Component URL",
    "Dependent Source Agency"
]].drop_duplicates()

# Function to calculate cosine similarity
def calculate_similarity(text1, text2):
    if not text1 or not text2:  # Avoid processing empty text
        return 0
    vectorizer = CountVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    return cosine_similarity(vectors)[0, 1]

# Generate all possible combinations and calculate similarity
filtered_data = []
for enabling, dependent in product(enabling_df.itertuples(index=False), dependent_df.itertuples(index=False)):
    # Skip if the sources are the same
    if enabling[2] == dependent[2]:
        continue
    similarity = calculate_similarity(enabling[0], dependent[0])  # Compare descriptions
    if similarity >= 0.6:  # Only add rows where similarity >= 0.6
        filtered_data.append({
            "Enabling Source": enabling[2],
            "Enabling Component": enabling[1],
            "Enabling Component Description": enabling[0],
            "Dependent Component": dependent[1],
            "Dependent Component Description": dependent[0],
            "Dependent Source": dependent[2],
            "Linkage mandated by what US Code or OMB policy?": "",
            "Enabling Component URL": enabling[3],
            "Dependent Component URL": dependent[3],
            "Enabling Source Agency": enabling[4],
            "Dependent Source Agency": dependent[4],
            "Notes and keywords": "",
            "Keywords Tab Items Found": "",
            "Enabling Component Responsible Office": "",
            "Dependent Component Responsible Office": "",
            "Edits": "",
            "Similarity": similarity  # Add similarity score for reference
        })

# Create a DataFrame from the filtered data
filtered_df = pd.DataFrame(filtered_data)

# Ensure the columns match the sequence in the original `ivntest.xlsx`
original_columns = [
    "Enabling Source",
    "Enabling Component",
    "Enabling Component Description",
    "Dependent Component",
    "Dependent Component Description",
    "Dependent Source",
    "Linkage mandated by what US Code or OMB policy?",
    "Enabling Component URL",
    "Dependent Component URL",
    "Enabling Source Agency",
    "Dependent Source Agency",
    "Notes and keywords",
    "Keywords Tab Items Found",
    "Enabling Component Responsible Office",
    "Dependent Component Responsible Office",
    "Edits",
    "Similarity"  # Include similarity for visibility
]

# Reorder columns and save to Excel
filtered_df = filtered_df[original_columns]
filtered_df.to_excel(output_file, index=False, float_format="%.4f")

print(f"Filtered similarity scores (>= 0.6) saved to {output_file}")


