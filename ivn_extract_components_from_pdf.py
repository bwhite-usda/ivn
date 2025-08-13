# ivn_extract_components_from_pdf.py
# Updated: 2025-06-13
# Description: Extracts likely requirement components from a PDF source document,
# and exports IVN-compatible Enabling and Dependent inventories with required fields.

import re
import csv
import requests
import tempfile
import sys
from pathlib import Path
from datetime import datetime
from io import StringIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager

def is_likely_requirement(sentence: str) -> bool:
    if not isinstance(sentence, str):
        return False
    sentence = sentence.strip()
    if len(sentence.split()) < 7:
        return False
    if sentence.isupper() and len(sentence.split()) < 10:
        return False
    if not re.search(
        r'\b(is|are|was|were|be|being|been|shall|must|will|should|establish|develop|create|submit|report|coordinate|implement|modernize|digitize)\b',
        sentence, re.IGNORECASE
    ):
        return False
    if re.match(r'^(First|Second|Third|Fourth|Fifth)[\s,:]', sentence, re.IGNORECASE):
        return True
    if re.match(r'^\d{1,3}\s+(U\.?S\.?C\.?|H\.?R\.?)', sentence, re.IGNORECASE):
        return True
    if re.search(
        r'\b(establish|develop|implement|digitize|coordinate|fund|enhance|require|submit|carry out|allocate|build|deliver|modernize|report|plan|strengthen)\b',
        sentence, re.IGNORECASE
    ):
        return True
    if re.search(
        r'\b(The (Secretary|Agency|Department|Administrator|Office|Program|Director))\b.+?\b(shall|must|will|is to|is required to)\b',
        sentence, re.IGNORECASE
    ):
        return True
    return False

def download_pdf_with_browser_headers(url: str) -> Path:
    print("📥 Downloading PDF with retry support...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/pdf",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com"
    }

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        tmp_path = Path(tempfile.gettempdir()) / f"ivn_temp_{datetime.now().timestamp()}.pdf"

        with open(tmp_path, "wb") as f:
            downloaded = 0
            chunk_size = 8192
            last_percent = -1
            for chunk in response.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        if percent != last_percent:
                            print(f"  → Downloaded {percent}%")
                            last_percent = percent
        print(f"✅ PDF saved to: {tmp_path}")
        return tmp_path

    except Exception as e:
        print(f"❌ Final download error: {e}")
        return None

def ask_for_pdf_path() -> Path:
    print("Choose PDF input method:")
    print("1. Paste a URL of a PDF")
    print("2. Browse to a local PDF file")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        url = input("Paste the full URL to the PDF: ").strip()
        return download_pdf_with_browser_headers(url)
    elif choice == "2":
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.call('wm', 'attributes', '.', '-topmost', True)
            file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            root.destroy()
            if file_path:
                print(f"📂 Selected local file: {file_path}")
                return Path(file_path)
            else:
                print("❌ No file selected.")
                return None
        except Exception as e:
            print(f"❌ Failed to open file dialog: {e}")
            return None
    else:
        print("❌ Invalid choice.")
        return None

def extract_text_page_by_page(pdf_path: Path) -> str:
    print("📄 Extracting text from PDF (page by page)...")
    output = StringIO()
    with open(pdf_path, 'rb') as f:
        resource_manager = PDFResourceManager()
        laparams = LAParams()
        for i, page in enumerate(PDFPage.get_pages(f), 1):
            print(f"  → Extracting page {i}...")
            extract_text_to_fp(f, output, codec='utf-8', laparams=laparams,
                               maxpages=0, page_numbers=[page.pageid - 1],
                               caching=True, output_type='text', rsrcmgr=resource_manager)
            sys.stdout.flush()
    return output.getvalue()

def format_inventory_rows(sentences, source_label, mode_label):
    print(f"🛠️ Formatting {mode_label} component rows...")
    rows = []
    for sent in sentences:
        sent = sent.strip().replace('\n', ' ')
        component_title = sent[:50].strip().split('.')[0]
        row = {
            f"{mode_label} Source": source_label,
            f"{mode_label} Component": component_title,
            f"{mode_label} Component Description": sent,
            "Notes and keywords": "",
            "Similarity": "",
            "Confidence": "",
            "Priority": "",
            "Domain": "",
            "Lineage": "",
            "Gap Statement": "",
            "Alignment Justification": "",
            "Confidence Explanation": "",
            "QC Notes": "",
            "Tags": ""
        }
        rows.append(row)
    print(f"✅ {len(rows)} {mode_label} components ready.")
    return rows

def main():
    source_label = "USDA Strategic Plan 2022–2026"
    pdf_path = ask_for_pdf_path()
    if not pdf_path or not pdf_path.exists():
        print("❌ PDF path not valid. Exiting.")
        return

    text = extract_text_page_by_page(pdf_path)
    print("✅ PDF text extraction complete.\n🔍 Analyzing for requirement sentences...\n")

    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    print(f"🔎 Total sentences found: {len(sentences)}")
    candidates = [s for s in sentences if is_likely_requirement(s)]
    print(f"🎯 Likely requirements identified: {len(candidates)}")

    reviewed_enabling = format_inventory_rows(candidates, source_label, "Enabling")
    reviewed_dependent = format_inventory_rows(candidates, source_label, "Dependent")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    if reviewed_enabling:
        output_file_en = Path(f"ivn_enabling_components_{timestamp}.tsv").resolve()
        with open(output_file_en, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=reviewed_enabling[0].keys(), delimiter='\t')
            writer.writeheader()
            writer.writerows(reviewed_enabling)
        print(f"📤 Enabling TSV saved: {output_file_en}")

    if reviewed_dependent:
        output_file_dep = Path(f"ivn_dependent_components_{timestamp}.tsv").resolve()
        with open(output_file_dep, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=reviewed_dependent[0].keys(), delimiter='\t')
            writer.writeheader()
            writer.writerows(reviewed_dependent)
        print(f"📤 Dependent TSV saved: {output_file_dep}")

if __name__ == "__main__":
    main()
