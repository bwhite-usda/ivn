# similarity_scores.py
#
# PROMPT FOR LLM (for future maintainers and reviewers):
# ---------------------------------------------------------------------------------
# This script performs semantic similarity matching between two sets of components from an Excel file to help identify and document plausible relationships between them.
#
# How it works:
# 1. Load Data:
#    - Loads three sheets from ivntest.xlsx:
#      * Components (reference set)
#      * Unaligned-Components (components to align)
#      * Internal-Dataset (for URL lookup)
# 2. Extract Components:
#    - From Components: tuples of (component_name, component_description, source)
#    - From Unaligned-Components: tuples of (Component, Component Description, Source, Component URL)
# 3. Build URL Lookup:
#    - Builds a dictionary mapping component names to their URLs using the Internal-Dataset sheet.
# 4. Batch Similarity Calculation:
#    - Use TfidfVectorizer to vectorize all unaligned and reference component descriptions in batch (fit once).
#    - Compute the cosine similarity matrix between all unaligned and reference descriptions at once.
#    - Only keep pairs where the similarity score is greater than or equal to a user-specified threshold.
# 5. Efficient Output Construction:
#    - For each pair above the threshold, build a result dictionary with the following columns in this exact order:
#      1. Unaligned Component
#      2. Source Unaligned Component
#      3. Unaligned Component Description
#      4. Unaligned Component URL
#      5. Reference Component Source
#      6. Reference Component
#      7. Reference Component Description
#      8. Reference Component URL
#      9. Justification (e.g., "'A' and 'B' have a semantic similarity score of 0.8123.")
#      10. Similarity Score
# 6. Progress Bar:
#    - Show a progress bar in the terminal as it processes all pairs.
# 7. Output:
#    - Collect all results into a pandas DataFrame.
#    - Save the results as a timestamped CSV file in the script directory, using UTF-8-SIG encoding.
#
# Additional Guidance:
# - Performance:
#   - Do not use nested Python loops for similarity calculation; use matrix operations.
#   - Only use loops for filtering and building the output list after the similarity matrix is computed.
# - Robustness:
#   - Handle missing or empty fields gracefully.
#   - Ensure the script works even if there are zero unaligned or reference components.
# - User Input:
#   - Prompt the user for a similarity threshold, defaulting to 0.6 if not provided or invalid.
# - Column Alignment:
#   - Ensure all output columns are correctly aligned with the original data.
# - Output File:
#   - Name the output file as ivn_inferred_causal_output_<timestamp>.csv.
#
# Error Prevention and Opportunities for Improvement:
# - Do not fit the vectorizer inside a loop.
# - Do not append to a DataFrame in a loop; build a list of dicts and create the DataFrame once.
# - Use efficient NumPy or pandas operations for thresholding.
# - Validate all column names against the actual Excel sheets.
# - Add comments explaining each major step.
# - Handle exceptions for user input and file operations.
# ---------------------------------------------------------------------------------

import os
import sys
import time
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Paths and loading
script_dir = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(script_dir, 'ivntest.xlsx')

df_components = pd.read_excel(input_path, sheet_name='Components')
df_unaligned = pd.read_excel(input_path, sheet_name='Unaligned-Components')
df_internal = pd.read_excel(input_path, sheet_name='Internal-Dataset')

def extract_unaligned_components(df):
    return [
        (
            row["Component"],
            row["Component Description"],
            row.get("Source", ""),
            row.get("Component URL", "")
        )
        for _, row in df.iterrows()
        if pd.notna(row.get("Component")) and pd.notna(row.get("Component Description")) \
            and str(row.get("Component")).strip() and str(row.get("Component Description")).strip()
    ]

def extract_components(df):
    return [
        (
            row["component_name"],
            row["component_description"],
            row.get("source", "")
        )
        for _, row in df.iterrows()
        if pd.notna(row.get("component_name")) and pd.notna(row.get("component_description")) \
            and str(row.get("component_name")).strip() and str(row.get("component_description")).strip()
    ]

def build_component_url_lookup(df_internal):
    url_lookup = {}
    for _, row in df_internal.iterrows():
        # Enabling Component
        en_name = row.get("Enabling Component")
        en_url = row.get("Enabling Component URL")
        if pd.notna(en_name) and str(en_name).strip():
            url_lookup[str(en_name).strip()] = en_url if pd.notna(en_url) else ""
        # Dependent Component
        dep_name = row.get("Dependent Component")
        dep_url = row.get("Dependent Component URL")
        if pd.notna(dep_name) and str(dep_name).strip():
            url_lookup[str(dep_name).strip()] = dep_url if pd.notna(dep_url) else ""
    return url_lookup

components = extract_components(df_components)
unaligned_components = extract_unaligned_components(df_unaligned)
component_url_lookup = build_component_url_lookup(df_internal)

print(f"Components count: {len(components)}")
print(f"Unaligned Components count: {len(unaligned_components)}")

def get_similarity_threshold(default=0.6):
    try:
        user_input = input(f"Enter similarity threshold (default {default}): ")
        threshold = float(user_input) if user_input.strip() else default
        print(f"Using similarity threshold: {threshold}")
        return threshold
    except Exception:
        print(f"Invalid input. Using default threshold: {default}")
        return default

if __name__ == "__main__":
    sim_threshold = get_similarity_threshold()
    print("Comparing Unaligned Components to Components...")

    if not unaligned_components or not components:
        print("No components to compare. Exiting.")
        sys.exit(0)

    # Unpack fields
    unaligned_names, unaligned_descs, unaligned_sources, unaligned_urls = zip(*unaligned_components)
    component_names, component_descs, component_sources = zip(*components)

    # Fit vectorizer once
    vectorizer = TfidfVectorizer().fit(list(unaligned_descs) + list(component_descs))
    unaligned_vecs = vectorizer.transform(unaligned_descs)
    component_vecs = vectorizer.transform(component_descs)

    # Compute all pairwise similarities at once
    sim_matrix = cosine_similarity(unaligned_vecs, component_vecs)

    # Find all pairs above threshold
    import numpy as np
    rows, cols = np.where(sim_matrix >= sim_threshold)
    total = len(rows)
    results = []
    start_time = time.time()

    for idx, (i, j) in enumerate(zip(rows, cols), 1):
        sim = sim_matrix[i, j]
        results.append({
            "Unaligned Component": unaligned_names[i],
            "Source Unaligned Component": unaligned_sources[i],
            "Unaligned Component Description": unaligned_descs[i],
            "Unaligned Component URL": unaligned_urls[i],
            "Reference Component Source": component_sources[j],
            "Reference Component": component_names[j],
            "Reference Component Description": component_descs[j],
            "Reference Component URL": component_url_lookup.get(str(component_names[j]).strip(), ""),
            "Justification": f"'{unaligned_names[i]}' and '{component_names[j]}' have a semantic similarity score of {sim:.4f}.",
            "Similarity Score": sim
        })
        if idx % 1000 == 0 or idx == total:
            elapsed = time.time() - start_time
            rate = idx / elapsed if elapsed > 0 else 0
            left = total - idx
            eta = left / rate if rate > 0 else 0
            status = f"Processed: {idx}/{total} | Left: {left} | ETA: {int(eta)}s"
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            sys.stdout.write(status)
            sys.stdout.flush()
    print()

    output_df = pd.DataFrame(results, columns=[
        "Unaligned Component",
        "Source Unaligned Component",
        "Unaligned Component Description",
        "Unaligned Component URL",
        "Reference Component Source",
        "Reference Component",
        "Reference Component Description",
        "Reference Component URL",
        "Justification",
        "Similarity Score"
    ])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(script_dir, f'ivn_inferred_causal_output_{timestamp}.tsv')
    print("Saving output file...")
    output_df.to_csv(output_path, index=False, encoding='utf-8-sig', sep='\t')
    print(f"Output saved to: {output_path}")