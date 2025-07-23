# ivn_components_error_checker.py automates quality checks for governance datasets, helping users quickly identify and review inconsistencies or potential errors in component descriptions, URLs, and source pairings.

"""
ivn_components_error_checker.py
Description: Identifies potential errors in federal governance deliverables datasets by:
1. Flagging components with multiple non-null descriptions
2. Flagging different components with identical descriptions
3. Flagging identical components with multiple URLs
4. Flagging enabling-dependent component pairs from the same source document
"""

import pandas as pd
import numpy as np
import re
from tqdm import tqdm
from difflib import SequenceMatcher
import requests
from io import BytesIO

def normalize_text(text):
    """Normalize text for fuzzy matching without external dependencies"""
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Remove extra spaces
    return text

def similarity_ratio(a, b):
    """Pure Python implementation of similarity ratio"""
    a = normalize_text(a)
    b = normalize_text(b)
    if not a and not b:
        return 100
    return SequenceMatcher(None, a, b).ratio() * 100

def get_component_groups(df, source_col, component_col):
    """Create similarity-matched groups for (source, component) pairs"""
    groups = {}
    group_map = {}
    group_counter = 0
    
    # Create normalized versions
    df['source_norm'] = df[source_col].apply(normalize_text)
    df['component_norm'] = df[component_col].apply(normalize_text)
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Grouping components"):
        source = row['source_norm']
        component = row['component_norm']
        matched_group = None
        
        # Skip empty components
        if not component:
            continue
            
        # Check against existing groups
        for group_id, (group_source, group_component) in groups.items():
            source_sim = similarity_ratio(source, group_source)
            comp_sim = similarity_ratio(component, group_component)
            
            if source_sim >= 95 and comp_sim >= 95:
                matched_group = group_id
                break
        
        # Create new group if no match found
        if matched_group is None:
            group_counter += 1
            matched_group = group_counter
            groups[matched_group] = (source, component)
        
        group_map[idx] = matched_group
    
    return group_map

def main():
    print("FGDEC: Loading production dataset...")
    # Load production dataset from Google Sheets
    sheet_url = "https://docs.google.com/spreadsheets/d/1Xw6WB_T3zUlLSry-AvLUBr-v9o-r5T6P/export?format=xlsx"
    response = requests.get(sheet_url)
    df = pd.read_excel(BytesIO(response.content), sheet_name=0)
    
    # Initialize error columns
    error_columns = [
        'ERROR: Multiple Descriptions',
        'ERROR: Same Description',
        'ERROR: Multiple URLs',
        'ERROR: Same Source Pair'
    ]
    
    for col in error_columns:
        df[col] = ""
    
    print("FGDEC: Creating unified component view...")
    # Create unified component view (enabling + dependent)
    enabling_df = df[['Enabling Source', 'Enabling Component', 
                      'Enabling Component Description', 'Enabling Component URL']].copy()
    enabling_df.columns = ['Source', 'Component', 'Description', 'URL']
    enabling_df['role'] = 'enabling'
    
    dependent_df = df[['Dependent Source', 'Dependent Component', 
                       'Dependent Component Description', 'Dependent Component URL']].copy()
    dependent_df.columns = ['Source', 'Component', 'Description', 'URL']
    dependent_df['role'] = 'dependent'
    
    components_df = pd.concat([enabling_df, dependent_df], ignore_index=True)
    
    print("FGDEC: Grouping similar components...")
    # Get similarity-matched component groups
    components_df['group_id'] = get_component_groups(components_df, 'Source', 'Component')
    
    # ERROR 1: Components with multiple non-null descriptions
    print("FGDEC: Checking for multiple descriptions...")
    for group_id, group_df in components_df.groupby('group_id'):
        if len(group_df) <= 1:
            continue
            
        # Get unique non-empty descriptions
        unique_descs = group_df['Description'].dropna().apply(normalize_text).unique()
        if len(unique_descs) > 1:
            # Flag original rows in main dataframe
            for _, row in group_df.iterrows():
                idx = row.name
                if idx < len(df):  # Enabling component
                    df.at[idx, 'ERROR: Multiple Descriptions'] = "ENABLING"
                else:  # Dependent component
                    orig_idx = idx - len(enabling_df)
                    if orig_idx < len(df):
                        df.at[orig_idx, 'ERROR: Multiple Descriptions'] = "DEPENDENT"
    
    # ERROR 2: Different components with identical descriptions
    print("FGDEC: Checking for same descriptions...")
    # Build description-component mapping
    desc_map = {}
    for idx, row in components_df.iterrows():
        desc = row['Description']
        if pd.isna(desc) or not str(desc).strip():
            continue
            
        normalized_desc = normalize_text(desc)
        if normalized_desc not in desc_map:
            desc_map[normalized_desc] = set()
        desc_map[normalized_desc].add(row['group_id'])
    
    # Find descriptions used by multiple component groups
    for desc, group_ids in desc_map.items():
        if len(group_ids) > 1:
            # Flag all components sharing this description
            comps = components_df[
                components_df['Description'].apply(normalize_text) == desc
            ]
            for _, row in comps.iterrows():
                idx = row.name
                if idx < len(df):  # Enabling component
                    df.at[idx, 'ERROR: Same Description'] = "ENABLING"
                else:  # Dependent component
                    orig_idx = idx - len(enabling_df)
                    if orig_idx < len(df):
                        df.at[orig_idx, 'ERROR: Same Description'] = "DEPENDENT"
    
    # ERROR 3: Identical components with multiple URLs
    print("FGDEC: Checking for multiple URLs...")
    for group_id, group_df in components_df.groupby('group_id'):
        if len(group_df) <= 1:
            continue
            
        # Get unique non-empty URLs
        unique_urls = group_df['URL'].dropna().apply(normalize_text).unique()
        if len(unique_urls) > 1:
            # Flag original rows in main dataframe
            for _, row in group_df.iterrows():
                idx = row.name
                if idx < len(df):  # Enabling component
                    df.at[idx, 'ERROR: Multiple URLs'] = "ENABLING"
                else:  # Dependent component
                    orig_idx = idx - len(enabling_df)
                    if orig_idx < len(df):
                        df.at[orig_idx, 'ERROR: Multiple URLs'] = "DEPENDENT"
    
    # ERROR 4: Enabling-dependent pairs from same source
    print("FGDEC: Checking for same source pairs...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Checking source pairs"):
        if pd.isna(row['Enabling Source']) or pd.isna(row['Dependent Source']):
            continue
            
        norm_source1 = normalize_text(row['Enabling Source'])
        norm_source2 = normalize_text(row['Dependent Source'])
        
        if similarity_ratio(norm_source1, norm_source2) > 95:
            df.at[idx, 'ERROR: Same Source Pair'] = "YES"
    
    # Save results with error flags
    print("FGDEC: Saving results...")
    with pd.ExcelWriter('error_flagged_dataset.xlsx') as writer:
        df.to_excel(writer, sheet_name='Flagged Dataset', index=False)
        
        # Create error reports
        error_reports = {
            "Multiple Descriptions": df[df['ERROR: Multiple Descriptions'] != ""],
            "Same Description": df[df['ERROR: Same Description'] != ""],
            "Multiple URLs": df[df['ERROR: Multiple URLs'] != ""],
            "Same Source Pairs": df[df['ERROR: Same Source Pair'] != ""]
        }
        
        for sheet_name, error_df in error_reports.items():
            error_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print("FGDEC: Process completed successfully! Output saved to error_flagged_dataset.xlsx")

if __name__ == "__main__":
    main()
