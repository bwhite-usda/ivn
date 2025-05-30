# This is ivn_generate_unique_IDs_for_components.py
# # Last updated: 2025-05-30  🕒 Fills missing IVN Component IDs using SHA-256

import pandas as pd
import hashlib
import re
from tqdm import tqdm
import time

def normalize(text):
    if pd.isna(text):
        return ''
    return re.sub(r'[^a-zA-Z0-9]', '', str(text).lower())

def generate_id(source, component):
    combo = normalize(source) + normalize(component)
    return hashlib.sha256(combo.encode('utf-8')).hexdigest()

# Load the Excel file
input_file = "IVN-public-version.xlsx"
df = pd.read_excel(input_file)

# Fill missing Enabling Component ID
print("🔄 Filling missing Enabling Component IDs...")
start_time = time.time()
for i, row in tqdm(df.iterrows(), total=len(df), desc="Enabling IDs", unit="row"):
    if pd.isna(row.get("Enabling Component ID", None)) or str(row.get("Enabling Component ID", "")).strip() == "":
        df.at[i, "Enabling Component ID"] = generate_id(
            row.get("Enabling Source", ""), row.get("Enabling Component Description", "")
        )
elapsed_time = time.time() - start_time
print(f"✅ Completed Enabling Component IDs in {elapsed_time:.2f} seconds.")

# Fill missing Dependent Component ID
print("🔄 Filling missing Dependent Component IDs...")
start_time = time.time()
for i, row in tqdm(df.iterrows(), total=len(df), desc="Dependent IDs", unit="row"):
    if pd.isna(row.get("Dependent Component ID", None)) or str(row.get("Dependent Component ID", "")).strip() == "":
        df.at[i, "Dependent Component ID"] = generate_id(
            row.get("Dependent Source", ""), row.get("Dependent Component Description", "")
        )
elapsed_time = time.time() - start_time
print(f"✅ Completed Dependent Component IDs in {elapsed_time:.2f} seconds.")

# Save updated Excel
output_file = "IVN-public-with-IDs.xlsx"
df.to_excel(output_file, index=False)
print(f"✅ Filled missing IDs and saved to: {output_file}")

