# pdf_component_extractor.py is a command-line tool for extracting structured components from PDF documents and saving them as a TSV file. It is designed to run on Android (or other platforms) using pure Python.

#!/usr/bin/env python3
# PDF Component Extractor (pdf_component_extractor.py)
# Pure Python solution for Android with text-based file browser
# Usage: python pdf_component_extractor.py

import re
import csv
import os
import sys
from pathlib import Path
import fitz  # PyMuPDF
import string
from datetime import datetime

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_menu(title, options, back=True):
    """Display a menu and get user selection"""
    clear_screen()
    print(f"\n{title}")
    print("=" * 40)
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    if back:
        print("0. Back")
    return input("\nEnter your choice: ").strip()

def browse_files(start_dir):
    """Text-based file browser for directory navigation"""
    current_dir = Path(start_dir)
    while True:
        dirs = []
        files = []
        try:
            for item in current_dir.iterdir():
                if item.is_dir():
                    dirs.append(f"{item.name}/")
                elif item.suffix.lower() == '.pdf':
                    files.append(item.name)
        except Exception as e:
            return None, f"Error accessing directory: {str(e)}"
        dirs.sort()
        files.sort()
        options = dirs + files
        if not options:
            options = ["No PDF files found"]
        choice = show_menu(f"Current Directory: {current_dir}", options, current_dir != start_dir)
        if choice == '0' and current_dir != start_dir:
            current_dir = current_dir.parent
            continue
        elif choice == '0':
            return None, "Operation cancelled"
        try:
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(options):
                selected = options[choice_index]
                selected_path = current_dir / selected.rstrip('/')
                if selected.endswith('/'):
                    current_dir = selected_path
                else:
                    return selected_path, None
            else:
                input("\nInvalid choice. Press Enter to try again...")
        except ValueError:
            input("\nPlease enter a number. Press Enter to continue...")

def get_pdf_title(pdf_path):
    doc = fitz.open(pdf_path)
    title = doc.metadata.get("title", Path(pdf_path).stem)
    return title.strip()

def get_bookmarks(doc):
    bookmarks = []
    toc = doc.get_toc(simple=True)
    for entry in toc:
        level, title, page = entry
        bookmarks.append((title, page - 1))  # PyMuPDF pages are 0-based
    return bookmarks

def extract_sections_by_bookmarks(pdf_path):
    doc = fitz.open(pdf_path)
    text_pages = [doc.load_page(i).get_text("text").replace('\t', ' ') for i in range(doc.page_count)]
    bookmarks = get_bookmarks(doc)
    sections = []
    for i, (title, start_page) in enumerate(bookmarks):
        end_page = bookmarks[i+1][1] if i+1 < len(bookmarks) else len(text_pages)
        section_text = "\n".join(text_pages[start_page:end_page]).strip()
        sections.append({
            "heading": title,
            "content": section_text
        })
    return sections

def extract_sections_by_headings(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for i in range(doc.page_count):
        page_text = doc.load_page(i).get_text("text")
        if page_text:
            page_text = page_text.replace('\t', ' ')
            full_text += page_text + "\n"
    # Use regex to find section headings
    section_regex = re.compile(r'(\d{3}\.\d{3,}\s+[A-Z][^\n]+)')
    matches = list(section_regex.finditer(full_text))
    sections = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx+1].start() if idx+1 < len(matches) else len(full_text)
        heading = match.group(1).strip()
        content = full_text[start+len(heading):end].strip()
        sections.append({
            "heading": heading,
            "content": content
        })
    return sections

def normalize_heading(heading):
    """Trim, remove control characters, and title-case the heading."""
    heading = ''.join(ch for ch in heading if ch in string.printable)
    heading = heading.strip()
    heading = heading.title()
    return heading

def normalize_text(text):
    """Clean and normalize text content with all required replacements and enhancements"""
    replacements = [
        (r'—', '--'),
        (r'‘', "'"),
        (r'’', "'"),
        (r'â€™', "'"),
        (r'“', '"'),
        (r'”', '"'),
        (r'\t', ' '),
        (r'•\s*', '- '),
        (r'\s*-\s+', '-'),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_structured_sections(pdf_path):
    """
    Extract sections using bookmarks, numbered headings, formatting cues, and subsections.
    Returns a list of dicts with 'heading' and 'content'.
    """
    doc = fitz.open(pdf_path)
    # Get bookmarks (TOC)
    bookmarks = get_bookmarks(doc)
    # Get all text blocks with formatting info
    sections = []
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join([span["text"] for span in line["spans"]]).strip()
                # Detect section headings by numbering and formatting
                # Example: 401.000, 401.101, 401.104-1, etc.
                if re.match(r'^\d{3}\.\d{3,}(-\d+)?(\s+[A-Z][^\n]+)?$', text):
                    # Formatting cues: large font or bold
                    font_size = max(span["size"] for span in line["spans"])
                    is_bold = any("Bold" in span["font"] for span in line["spans"])
                    if font_size > 10 or is_bold or len(text) < 80:
                        sections.append({
                            "heading": text,
                            "page": page_num,
                            "font_size": font_size,
                            "is_bold": is_bold
                        })
    # Merge bookmarks and detected headings
    all_sections = []
    text_pages = [doc.load_page(i).get_text("text").replace('\t', ' ') for i in range(doc.page_count)]
    # Use both bookmarks and detected headings to define section boundaries
    section_indices = []
    # Add bookmarks
    for title, page in bookmarks:
        section_indices.append((normalize_heading(title), page))
    # Add detected headings
    for sec in sections:
        section_indices.append((normalize_heading(sec["heading"]), sec["page"]))
    # Remove duplicates and sort by page
    section_indices = sorted(set(section_indices), key=lambda x: x[1])
    # Extract section text
    for i, (heading, start_page) in enumerate(section_indices):
        end_page = section_indices[i+1][1] if i+1 < len(section_indices) else len(text_pages)
        section_text = "\n".join(text_pages[start_page:end_page]).strip()
        # Extract subsections (e.g., (a), (b), etc.)
        subsection_regex = re.compile(r'^\([a-z]\)\s+', re.MULTILINE)
        subsections = subsection_regex.split(section_text)
        if len(subsections) > 1:
            for idx, sub in enumerate(subsections[1:], start=1):
                sub_heading = f"{heading} ({chr(96+idx)})"
                all_sections.append({
                    "heading": sub_heading,
                    "content": normalize_text(sub)
                })
            # Add main section text (before first subsection)
            all_sections.append({
                "heading": heading,
                "content": normalize_text(subsections[0])
            })
        else:
            all_sections.append({
                "heading": heading,
                "content": normalize_text(section_text)
            })
    return all_sections

def main():
    clear_screen()
    print("\n📄 PDF Component Extractor for Android")
    print("=" * 50)
    print("This tool extracts sections from PDFs and saves them as TSV")
    print("with text normalization for compatibility.")
    start_dir = "/sdcard"
    if not Path(start_dir).exists():
        start_dir = "/storage/emulated/0"
    if not Path(start_dir).exists():
        start_dir = os.getcwd()
    pdf_path, error = browse_files(start_dir)
    if error:
        print(f"\nError: {error}")
        input("Press Enter to exit...")
        return
    print(f"\nSelected PDF: {pdf_path}")
    output_tsv = pdf_path.with_suffix('.tsv')
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    output_tsv = output_tsv.with_name(f"{output_tsv.stem}_{timestamp}{output_tsv.suffix}")
    output_path, error = browse_files(output_tsv.parent)
    if error:
        print(f"\nError: {error}")
        input("Press Enter to exit...")
        return
    if output_path.suffix.lower() != '.tsv':
        output_tsv = output_path.with_suffix('.tsv')
    else:
        output_tsv = output_path
    if not output_tsv.stem.endswith(timestamp):
        output_tsv = output_tsv.with_name(f"{output_tsv.stem}_{timestamp}{output_tsv.suffix}")
    url = input("\nEnter source URL (press Enter to skip): ").strip()
    try:
        print(f"\nExtracting structured sections from PDF...")
        sections = extract_structured_sections(pdf_path)
        source_name = get_pdf_title(pdf_path)
        print(f"Found {len(sections)} components")
        print(f"Saving to: {output_tsv}")
        with open(output_tsv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Source Name",
                    "Component Name",
                    "Component Description",
                    "Component URL"
                ],
                delimiter='\t'
            )
            writer.writeheader()
            for section in sections:
                writer.writerow({
                    "Source Name": source_name,
                    "Component Name": section["heading"],
                    "Component Description": section["content"],
                    "Component URL": url
                })
        print("\n✅ Processing completed successfully!")
        print(f"Output saved to: {output_tsv}")
        input("\nPress Enter to exit...")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
