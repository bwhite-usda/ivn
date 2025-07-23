# pdf_component_extractor.py is a command-line tool for extracting structured components from PDF documents and saving them as a CSV file. It is designed to run on Android (or other platforms) using pure Python.

#!/usr/bin/env python3
# PDF Component Extractor (pdf_component_extractor.py)
# Pure Python solution for Android with text-based file browser
# Usage: python pdf_component_extractor.py

import re
import csv
import os
import sys
from pathlib import Path
import PyPDF2

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
        # Get directory contents
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
        
        # Sort directories and files
        dirs.sort()
        files.sort()
        
        # Create menu options
        options = dirs + files
        if not options:
            options = ["No PDF files found"]
        
        # Show menu
        choice = show_menu(f"Current Directory: {current_dir}", options, current_dir != start_dir)
        
        # Handle back command
        if choice == '0' and current_dir != start_dir:
            current_dir = current_dir.parent
            continue
        elif choice == '0':
            return None, "Operation cancelled"
        
        # Handle selection
        try:
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(options):
                selected = options[choice_index]
                selected_path = current_dir / selected.rstrip('/')
                
                if selected.endswith('/'):  # Directory
                    current_dir = selected_path
                else:  # File
                    return selected_path, None
            else:
                input("\nInvalid choice. Press Enter to try again...")
        except ValueError:
            input("\nPlease enter a number. Press Enter to continue...")

def extract_pdf_text(pdf_path):
    """Extract text from PDF using PyPDF2"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n"
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")
    
    return text

def parse_sections(text):
    """
    Parse text into sections based on heading patterns.
    Improved to match USDA Strategic Plan structure and manual spreadsheet.
    """
    # Patterns for Strategic Goals and Objectives
    goal_pattern = re.compile(r'^(Strategic Goal \d+)(.*)$', re.IGNORECASE)
    objective_pattern = re.compile(r'^(Objective \d+\.\d+)(.*)$', re.IGNORECASE)

    sections = []
    current_goal = None
    current_section = None

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        goal_match = goal_pattern.match(line)
        obj_match = objective_pattern.match(line)

        if goal_match:
            # Save previous section if exists
            if current_section:
                sections.append(current_section)
                current_section = None
            # Start new goal section
            current_goal = goal_match.group(1).strip()
            goal_title = goal_match.group(2).strip()
            heading = current_goal
            if goal_title:
                heading += " " + goal_title
            current_section = {
                "heading": heading,
                "content": []
            }
        elif obj_match:
            # Save previous section if exists
            if current_section:
                sections.append(current_section)
            # Start new objective section, include parent goal in heading
            obj_heading = obj_match.group(1).strip()
            obj_title = obj_match.group(2).strip()
            heading = f"{current_goal} - {obj_heading}"
            if obj_title:
                heading += " " + obj_title
            current_section = {
                "heading": heading,
                "content": []
            }
        else:
            if current_section:
                current_section["content"].append(line)

    # Add last section
    if current_section:
        sections.append(current_section)

    # Clean up content
    for section in sections:
        section["content"] = "\n".join(section["content"]).strip()

    return sections

def normalize_text(text):
    """Clean and normalize text content with all required replacements"""
    replacements = [
        (r'—', '--'),          # Em-dash to two en-dashes
        (r'‘', "'"),            # Left single smart quote
        (r'’', "'"),            # Right single smart quote
        (r'“', '"'),            # Left double smart quote
        (r'”', '"'),            # Right double smart quote
        (r'\t', ' '),           # Tabs to spaces
        (r'\s+', ' '),          # Multiple spaces to single space
        (r'•\s*', '- '),        # Bullets to dashes
        (r'\s*-\s+', '-'),      # Fix hyphenated words
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    
    return text.strip()

def main():
    clear_screen()
    print("\n📄 PDF Component Extractor for Android")
    print("=" * 50)
    print("This tool extracts sections from PDFs and saves them as CSV")
    print("with text normalization for compatibility.")
    
    # Start with common Android directories
    start_dir = "/sdcard"
    if not Path(start_dir).exists():
        start_dir = "/storage/emulated/0"
    if not Path(start_dir).exists():
        start_dir = os.getcwd()
    
    # Select PDF file
    pdf_path, error = browse_files(start_dir)
    if error:
        print(f"\nError: {error}")
        input("Press Enter to exit...")
        return
    
    print(f"\nSelected PDF: {pdf_path}")
    
    # Get output path
    output_csv = pdf_path.with_suffix('.csv')
    output_path, error = browse_files(output_csv.parent)
    if error:
        print(f"\nError: {error}")
        input("Press Enter to exit...")
        return
    
    # Confirm output filename
    if output_path.suffix.lower() != '.csv':
        output_csv = output_path.with_suffix('.csv')
    else:
        output_csv = output_path
    
    # Get URL
    url = input("\nEnter source URL (press Enter to skip): ").strip()
    
    try:
        # Extract text from PDF
        print(f"\nExtracting text from PDF...")
        text = extract_pdf_text(pdf_path)
        
        # Parse sections
        print("Parsing sections...")
        sections = parse_sections(text)
        
        # Prepare CSV output
        source_name = pdf_path.stem
        print(f"Found {len(sections)} components")
        print(f"Saving to: {output_csv}")
        
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Source Name",
                "Component Name",
                "Component Description",
                "Component URL"
            ])
            writer.writeheader()
            
            for section in sections:
                writer.writerow({
                    "Source Name": source_name,
                    "Component Name": section["heading"],
                    "Component Description": normalize_text(section["content"]),
                    "Component URL": url
                })
        
        print("\n✅ Processing completed successfully!")
        print(f"Output saved to: {output_csv}")
        input("\nPress Enter to exit...")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    # Install PyPDF2 if missing
    try:
        import PyPDF2
    except ImportError:
        print("Installing required PyPDF2 library...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2"])
        import PyPDF2
        
    main()
