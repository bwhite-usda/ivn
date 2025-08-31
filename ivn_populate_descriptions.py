# This script updates the "Dependent Component Description" field in an Excel file (ivntest.xlsx).
# For each row where the description is blank or matches the component name, it fetches content from the associated URL.
# The script extracts readable text from HTML and PDF URLs, caches results to avoid duplicate downloads, and writes the text to a new field: "Derived Dependent Component Description".
# Progress, estimated time remaining, and runtime statistics are printed to the console.
# The output Excel file is timestamped, and the actual runtime is saved for improved future estimates.

import requests
import pandas as pd
import time
from datetime import datetime
import os
from bs4 import BeautifulSoup
from io import BytesIO
import PyPDF2

RUNTIME_FILE = "ivn_populate_descriptions_runtime.txt"

# Load your data from Excel file
print("Loading data from ivntest.xlsx...")
df = pd.read_excel('ivntest.xlsx')

def is_placeholder(row):
    desc = str(row['Dependent Component Description']).strip()
    comp = str(row['Dependent Component']).strip()
    return desc == '' or desc == comp

def fetch_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type or url.lower().endswith('.pdf'):
            # Extract text from PDF
            pdf_file = BytesIO(response.content)
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip() if text else "No readable text found in PDF."
        elif 'html' in content_type or url.lower().endswith('.htm') or url.lower().endswith('.html'):
            # Extract text from HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        else:
            # Return raw text for other types
            return response.text
    except Exception as e:
        return f"Error fetching: {e}"

# Build array of indices needing update
print("Identifying rows needing update...")
needs_update = df[df.apply(is_placeholder, axis=1)]
total = len(needs_update)
print(f"Found {total} rows to process.")

# Load previous runtime if available
prev_runtime = None
if os.path.exists(RUNTIME_FILE):
    with open(RUNTIME_FILE, "r") as f:
        try:
            prev_runtime = float(f.read().strip())
        except Exception:
            prev_runtime = None

# Cache for URL content
url_content_cache = {}

start_time = time.time()
for i, (idx, row) in enumerate(needs_update.iterrows(), 1):
    url = row['Dependent Component URL']
    if url not in url_content_cache:
        print(f"Fetching {url} for the first time...")
        url_content_cache[url] = fetch_url_content(url)
    else:
        print(f"Using cached content for {url}.")

    df.at[idx, 'Derived Dependent Component Description'] = url_content_cache[url]

    elapsed = time.time() - start_time
    remaining = total - i

    # Use previous runtime for estimate if available
    if prev_runtime and total > 0:
        est_left = prev_runtime * (remaining / total)
    else:
        avg_time = elapsed / i if i > 0 else 0
        est_left = avg_time * remaining

    mins, secs = divmod(est_left, 60)
    print(f"Completed {i}/{total}. Estimated time left: {int(mins)}m {int(secs)}s.")

# Save updated data to Excel with timestamped filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_filename = f"ivntest_with_descriptions_{timestamp}.xlsx"
print(f"Saving updated data to {output_filename}...")
df.to_excel(output_filename, index=False)
print("Done.")

# Record actual elapsed time for future runs
actual_runtime = time.time() - start_time
with open(RUNTIME_FILE, "w") as f:
    f.write(str(actual_runtime))
print(f"Actual runtime recorded: {actual_runtime:.2f} seconds.")