"""
First Cousin Analysis Script for IVN Dataset

This script analyzes component alignments to identify "first cousin" relationships -
pairs of components that aren't directly aligned but share several common alignment targets.
"""

import pandas as pd
import networkx as nx

def find_first_cousins(excel_file, min_common_targets=3):
    """
    Find first cousin relationships in IVN dataset
    
    Args:
        excel_file (str): Path to Excel file with Alignments and Components sheets
        min_common_targets (int): Minimum number of common targets to consider
    
    Returns:
        DataFrame: Results of first cousin analysis
    """
    
    # Step 1: Load data from Excel file
    print("Loading data from Excel file...")
    
    # Load the specific sheets from the Excel file
    alignments_df = pd.read_excel(excel_file, sheet_name='Alignments')
    components_df = pd.read_excel(excel_file, sheet_name='Components')
    
    # Create a mapping from component_id to component_name for easy lookup
    component_name_map = dict(zip(components_df['component_id'], components_df['component_name']))
    
    # Display column names to verify correct loading
    print(f"Columns in Alignments sheet: {list(alignments_df.columns)}")
    print(f"Columns in Components sheet: {list(components_df.columns)}")
    
    # Step 2: Create a directed graph to represent component alignments
    print("Creating alignment graph...")
    G = nx.DiGraph()
    
    # Add edges to the graph using the correct column names from your Excel file
    for _, row in alignments_df.iterrows():
        G.add_edge(row['enabling_component_id'], row['dependent_component_id'])
    
    # Step 3: Create a mapping of each component to its alignment targets
    print("Mapping components to their alignment targets...")
    targets_map = {}
    for component in G.nodes():
        targets_map[component] = set(G.successors(component))
    
    # Step 4: Identify candidate pairs with no direct alignment but common targets
    print("Finding candidate pairs with common alignment targets...")
    candidate_pairs = []
    common_targets_dict = {}
    
    # Get list of all components
    components = list(G.nodes())
    
    # Compare all pairs of components
    for i, comp1 in enumerate(components):
        for j, comp2 in enumerate(components[i+1:], i+1):
            # Skip if direct alignment exists in either direction
            if G.has_edge(comp1, comp2) or G.has_edge(comp2, comp1):
                continue
                
            # Find common targets (components aligned to both comp1 and comp2)
            common_targets = targets_map[comp1] & targets_map[comp2]
            
            # Check if meets the minimum common targets threshold
            if len(common_targets) >= min_common_targets:
                candidate_pairs.append((comp1, comp2))
                common_targets_dict[(comp1, comp2)] = common_targets
    
    # Step 5: Analyze each candidate pair in detail
    print("Analyzing candidate pairs...")
    results = []
    for comp1, comp2 in candidate_pairs:
        # Identify targets exclusive to each component
        exclusive_to_comp1 = targets_map[comp1] - targets_map[comp2]
        exclusive_to_comp2 = targets_map[comp2] - targets_map[comp1]
        
        # Count common targets
        common_targets_count = len(common_targets_dict[(comp1, comp2)])
        
        # Get component names for readability
        comp1_name = component_name_map.get(comp1, "Name not found")
        comp2_name = component_name_map.get(comp2, "Name not found")
        
        # Compile results for this pair with detailed column definitions:
        # Component_A: First component ID in the first cousin pair
        # Component_A_Name: Human-readable name of first component
        # Component_B: Second component ID in the first cousin pair
        # Component_B_Name: Human-readable name of second component
        # Common_Targets_Count: Number of components that both A and B align to
        # Common_Targets: Set of components that both A and B align to
        # Exclusive_to_A_Count: Number of components aligned to A but not to B
        # Exclusive_to_A: Set of components aligned to A but not to B
        # Exclusive_to_B_Count: Number of components aligned to B but not to A
        # Exclusive_to_B: Set of components aligned to B but not to A
        results.append({
            'Component_A': comp1,
            'Component_A_Name': comp1_name,
            'Component_B': comp2,
            'Component_B_Name': comp2_name,
            'Common_Targets_Count': common_targets_count,
            'Common_Targets': common_targets_dict[(comp1, comp2)],
            'Exclusive_to_A_Count': len(exclusive_to_comp1),
            'Exclusive_to_A': exclusive_to_comp1,
            'Exclusive_to_B_Count': len(exclusive_to_comp2),
            'Exclusive_to_B': exclusive_to_comp2
        })
    
    return pd.DataFrame(results)

# Main execution
if __name__ == "__main__":
    # Configuration parameters
    excel_file = 'ivntest.xlsx'  # Path to the Excel file
    min_common_targets = 3       # Minimum number of common targets to consider
    
    print("Starting first cousin analysis...")
    print(f"Using minimum common targets threshold: {min_common_targets}")
    
    # Execute the analysis
    results_df = find_first_cousins(excel_file, min_common_targets)
    
    # Save results to CSV file
    print("Saving results to CSV file...")
    results_df.to_csv('first_cousins_analysis.csv', index=False)
    
    # Print summary of findings
    print("\nAnalysis Complete!")
    print(f"Found {len(results_df)} first cousin pairs with {min_common_targets}+ common targets")
    
    if len(results_df) > 0:
        print("\nTop pairs by number of common targets:")
        top_pairs = results_df.nlargest(5, 'Common_Targets_Count')
        for _, row in top_pairs.iterrows():
            print(f"  {row['Component_A_Name']} & {row['Component_B_Name']}: {row['Common_Targets_Count']} common targets")
        
        # Show detailed information for the top pair
        print("\nDetailed information for top pair:")
        top_pair = top_pairs.iloc[0]
        print(f"Components: {top_pair['Component_A_Name']} and {top_pair['Component_B_Name']}")
        print(f"Component IDs: {top_pair['Component_A']} and {top_pair['Component_B']}")
        print(f"Common targets: {top_pair['Common_Targets']}")
        print(f"Exclusive to {top_pair['Component_A_Name']}: {top_pair['Exclusive_to_A']}")
        print(f"Exclusive to {top_pair['Component_B_Name']}: {top_pair['Exclusive_to_B']}")
    else:
        print("No first cousin relationships found with the current threshold.")
    
    print("\nDetailed results saved to 'first_cousins_analysis.csv'")
    
    # Print column definitions for reference
    print("\nColumn Definitions for Output CSV:")
    print("Component_A: First component ID in the first cousin pair")
    print("Component_A_Name: Human-readable name of first component")
    print("Component_B: Second component ID in the first cousin pair")
    print("Component_B_Name: Human-readable name of second component")
    print("Common_Targets_Count: Number of components that both A and B align to")
    print("Common_Targets: Set of components that both A and B align to")
    print("Exclusive_to_A_Count: Number of components aligned to A but not to B")
    print("Exclusive_to_A: Set of components aligned to A but not to B")
    print("Exclusive_to_B_Count: Number of components aligned to B but not to A")
    print("Exclusive_to_B: Set of components aligned to B but not to A")