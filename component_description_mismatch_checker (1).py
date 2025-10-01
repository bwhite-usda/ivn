# component_description_mismatch_checker.py checks for mismatches between component IDs/names and their descriptions in several sheets of the ivntest.xlsx Excel file. It helps ensure that each component has a consistent description across the dataset.
# Last updated: 2025-07-07

import pandas as pd

sheet_names = [
    "Internal-Dataset",      # Old way
    "Internal-Components",   # New way
    "Internal-Alignments",
    "Internal-Sources"
]

with pd.ExcelWriter("component_description_mismatches.xlsx", engine="openpyxl") as writer:
    for sheet in sheet_names:
        df = pd.read_excel("ivntest.xlsx", sheet_name=sheet)
        print(f"Columns in '{sheet}': {list(df.columns)}")

        # Clean string columns
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].map(lambda x: x.strip() if isinstance(x, str) else x)
        df[str_cols] = df[str_cols].map(lambda x: x.lower().strip() if isinstance(x, str) else x)

        if sheet == "Internal-Dataset":
            # Old way: Check for mismatches in Enabling/Dependent Component Descriptions
            if (
                "Enabling Component" in df.columns and
                "Enabling Component Description" in df.columns
            ):
                ec_grouped = df.groupby("Enabling Component")["Enabling Component Description"].nunique()
                ec_mismatched_keys = ec_grouped[ec_grouped > 1].index
                ec_mismatches = df[df["Enabling Component"].isin(ec_mismatched_keys)]
                ec_mismatches.to_excel(writer, sheet_name="Internal-Dataset - Enabling Mismatches", index=False)
                print("Internal-Dataset: Enabling Component mismatches:")
                print(ec_grouped)
            else:
                print("Internal-Dataset: Enabling Component columns not found.")

            if (
                "Dependent Component" in df.columns and
                "Dependent Component Description" in df.columns
            ):
                dc_grouped = df.groupby("Dependent Component")["Dependent Component Description"].nunique()
                dc_mismatched_keys = dc_grouped[dc_grouped > 1].index
                dc_mismatches = df[df["Dependent Component"].isin(dc_mismatched_keys)]
                dc_mismatches.to_excel(writer, sheet_name="Internal-Dataset - Dependent Mismatches", index=False)
                print("Internal-Dataset: Dependent Component mismatches:")
                print(dc_grouped)
            else:
                print("Internal-Dataset: Dependent Component columns not found.")

        elif sheet == "Internal-Components":
            # New way: Check for mismatches in component_id to description
            if "component_id" in df.columns and "description" in df.columns:
                grouped = df.groupby("component_id")["description"].nunique()
                mismatched_keys = grouped[grouped > 1].index
                mismatches = df[df["component_id"].isin(mismatched_keys)]
                mismatches.to_excel(writer, sheet_name="Internal-Components - Description Mismatches", index=False)
                print("Internal-Components: Component ID to Description uniqueness:")
                print(grouped)
                if mismatches.empty:
                    print("No mismatches found! All component_ids have consistent descriptions.\n")
                else:
                    print("Mismatches found!\n")
            else:
                print("Internal-Components: component_id or description column not found.")

        else:
            # No description columns to check in these sheets
            print(f"No description consistency check for '{sheet}'.\n")

print("Mismatch export complete: component_description_mismatches.xlsx")
