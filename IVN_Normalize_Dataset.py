"""
INSTRUCTION FOR LLM: You are an expert Python programmer assisting with data normalization tasks. Always follow these guidelines:

1. READ INPUT: Read the first sheet of an Excel file using pandas, using column names from the header row
2. COLUMN MAPPING: Look for these specific columns:
   - Enabling Source, Enabling Component, Enabling Component Description, Enabling Component URL
   - Dependent Component, Dependent Component Description, Dependent Component URL, Dependent Source
3. COMPONENTS EXTRACTION: Extract unique components from both Enabling and Dependent columns
4. ID GENERATION: Use SHA-256 hash to generate unique IDs for both components and sources
5. NORMALIZED STRUCTURE: Create three normalized sheets:
   a) Components: source_id (hash), component_name, component_description, component_url, component_id (hash)
   b) Alignments: enabling_component_id, enabling_source_id, enabling_source_name, enabling_component_name, enabling_component_url,
      dependent_component_id, dependent_source_id, dependent_source_name, dependent_component_name, dependent_component_url
   c) Sources: source_id (hash), source_name
6. OUTPUT: Save to a new Excel file with timestamp suffix (YYYYMMDDHHMM format)
7. FEEDBACK: Print the output filename when complete

Always validate input data, handle missing columns gracefully, and ensure unique identifiers are properly generated.
Update these instructions with any new requirements when modifying the script.
"""

import pandas as pd
from datetime import datetime
import hashlib

def generate_id(*args):
    """Generate a unique ID using SHA-256 hash of all provided arguments"""
    unique_string = "_".join(str(arg) for arg in args if arg)
    return hashlib.sha256(unique_string.encode()).hexdigest()[:16]

def normalize_excel(input_file):
    # Read the input Excel file
    df = pd.read_excel(input_file, sheet_name=0)
    
    # Create DataFrames for normalized sheets
    sources_data = []
    components_data = []
    alignments_data = []
    
    # Track unique sources and components
    sources_dict = {}  # source_name -> source_id
    components_dict = {}  # (source_id, name, description, url) -> component_id
    
    # Process each row
    for _, row in df.iterrows():
        # Process Enabling Source and Component
        enabling_source = row.get('Enabling Source', '')
        enabling_comp = row.get('Enabling Component', '')
        enabling_desc = row.get('Enabling Component Description', '')
        enabling_url = row.get('Enabling Component URL', '')
        
        if enabling_source:
            # Generate or get source_id
            if enabling_source not in sources_dict:
                source_id = generate_id(enabling_source)
                sources_dict[enabling_source] = source_id
                sources_data.append({
                    'source_id': source_id,
                    'source_name': enabling_source
                })
            else:
                source_id = sources_dict[enabling_source]
            
            if enabling_comp:
                comp_key = (source_id, enabling_comp, enabling_desc, enabling_url)
                if comp_key not in components_dict:
                    comp_id = generate_id(*comp_key)
                    components_dict[comp_key] = comp_id
                    components_data.append({
                        'source_id': source_id,
                        'component_name': enabling_comp,
                        'component_description': enabling_desc,
                        'component_url': enabling_url,
                        'component_id': comp_id
                    })
        
        # Process Dependent Source and Component
        dependent_source = row.get('Dependent Source', '')
        dependent_comp = row.get('Dependent Component', '')
        dependent_desc = row.get('Dependent Component Description', '')
        dependent_url = row.get('Dependent Component URL', '')
        
        if dependent_source:
            # Generate or get source_id
            if dependent_source not in sources_dict:
                source_id = generate_id(dependent_source)
                sources_dict[dependent_source] = source_id
                sources_data.append({
                    'source_id': source_id,
                    'source_name': dependent_source
                })
            else:
                source_id = sources_dict[dependent_source]
            
            if dependent_comp:
                comp_key = (source_id, dependent_comp, dependent_desc, dependent_url)
                if comp_key not in components_dict:
                    comp_id = generate_id(*comp_key)
                    components_dict[comp_key] = comp_id
                    components_data.append({
                        'source_id': source_id,
                        'component_name': dependent_comp,
                        'component_description': dependent_desc,
                        'component_url': dependent_url,
                        'component_id': comp_id
                    })
        
        # Create alignment if both components exist
        if (enabling_source and enabling_comp and 
            dependent_source and dependent_comp):
            enabling_source_id = sources_dict.get(enabling_source)
            dependent_source_id = sources_dict.get(dependent_source)
            
            enabling_comp_id = components_dict.get((enabling_source_id, enabling_comp, enabling_desc, enabling_url))
            dependent_comp_id = components_dict.get((dependent_source_id, dependent_comp, dependent_desc, dependent_url))
            
            if enabling_comp_id and dependent_comp_id:
                alignments_data.append({
                    'enabling_component_id': enabling_comp_id,
                    'enabling_source_id': enabling_source_id,
                    'enabling_source_name': enabling_source,
                    'enabling_component_name': enabling_comp,
                    'enabling_component_url': enabling_url,
                    'dependent_component_id': dependent_comp_id,
                    'dependent_source_id': dependent_source_id,
                    'dependent_source_name': dependent_source,
                    'dependent_component_name': dependent_comp,
                    'dependent_component_url': dependent_url
                })
    
    # Create DataFrames
    sources_df = pd.DataFrame(sources_data)
    components_df = pd.DataFrame(components_data)
    alignments_df = pd.DataFrame(alignments_data)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    output_file = f"ivntest_normalized_{timestamp}.xlsx"
    
    # Save to Excel
    with pd.ExcelWriter(output_file) as writer:
        sources_df.to_excel(writer, sheet_name='Sources', index=False)
        components_df.to_excel(writer, sheet_name='Components', index=False)
        alignments_df.to_excel(writer, sheet_name='Alignments', index=False)
    
    return output_file

if __name__ == "__main__":
    input_filename = "ivntest.xlsx"
    output_filename = normalize_excel(input_filename)
    print(f"Output file: {output_filename}")

