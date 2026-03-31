import os
from openpyxl.styles import (
    Font,
    Alignment
)
import pandas as pd
import json
from retrieve import (
    JSON_FOLDER,
    LIST_STR,
    EMPTY_FIELD
)

# Text that is added onto the end of the filename
FILENAME_END_TEXT = "_summary"

# Folder names for where exported data is stored
JSON_ANALYSIS_FOLDER = "analysis_json"
XSLX_ANALYSIS_FOLDER = "analysis_excel"

def summarize_mdr_incidents(data):
    """
        Takes in a JSON object in the format of the .json exports created in retrieve.py
        Returns a JSON object with a summary of the incidents
    """

    # Initialize the structure
    event_categories = ["malfunction", "injury", "death", "other"]
    summary = {
        "list of models": [],
        "earliest incident date": None,
        "latest incident date": None,
        "type of event": {cat: {"total": 0} for cat in event_categories},
        "Product problems": {},
        "Patient problems": {}
    }
    summary["type of event"]["total"] = {"total": 0}

    models_set = set()
    dates = []

    for entry in data:
        model = entry.get("Model Number")
        event_date = entry.get("Date of Event")
        event_type = entry.get("Type of Event", "").lower()
        prod_probs = entry.get("Product Problems", "").split(LIST_STR)
        pat_probs = entry.get("Patient Problems", "").split(LIST_STR)

        # Track models and dates
        if model:
            models_set.add(model)
        if event_date:
            dates.append(event_date)

        # 1. Process Type of Event
        if event_type in summary["type of event"]:
            # Increment model specific count
            summary["type of event"][event_type][model] = summary["type of event"][event_type].get(model, 0) + 1
            # Increment category total
            summary["type of event"][event_type]["total"] += 1
            # Increment grand total
            summary["type of event"]["total"]["total"] += 1
            summary["type of event"]["total"][model] = summary["type of event"]["total"].get(model, 0) + 1

        # 2. Process Product Problems & 3. Patient Problems
        for prob_type, prob_list in [("Product problems", prod_probs), ("Patient problems", pat_probs)]:
            for p in prob_list:
                p = p.strip()
                if not p: continue
                
                if p not in summary[prob_type]:
                    summary[prob_type][p] = {"total": 0}
                
                summary[prob_type][p][model] = summary[prob_type][p].get(model, 0) + 1
                summary[prob_type][p]["total"] += 1

        # Sort Product Problems and Patient Problems by the "Total" value inside each problem dict
        summary["Product problems"] = dict(
            sorted(summary["Product problems"].items(), key=lambda item: item[1]["total"], reverse=True)
        )

        summary["Patient problems"] = dict(
            sorted(summary["Patient problems"].items(), key=lambda item: item[1]["total"], reverse=True)
        )

    # Finalize Metadata
    summary["list of models"] = sorted(list(models_set))
    if dates:
        valid_dates = [d for d in dates if d and d != EMPTY_FIELD]
    summary["earliest incident date"] = min(valid_dates) if valid_dates else "18000101"
    summary["latest incident date"] = max(valid_dates) if valid_dates else "18000101"

    return summary

def create_table_df(summary_section, row_labels, prefix=""):
    """Helper to convert a summary sub-dictionary into a DataFrame."""
    data_dict = {}
    for label, counts in summary_section.items():
        column_name = f"{prefix}{label}"
        # Extract counts for each model and the total row
        data_dict[column_name] = [counts.get(row, 0) for row in row_labels]
    
    df = pd.DataFrame(data_dict, index=row_labels)
    df.index.name = "Model"
    return df.T

def write_summary_to_xlsx_file(summary, output_path):
    """Writes three separate tables into a single Excel file with multiple sheets."""
    row_labels = summary["list of models"] + ["total"]
    
    # Create the DataFrames
    df_events = create_table_df(summary["type of event"], row_labels)
    df_product = create_table_df(summary["Product problems"], row_labels)
    df_patient = create_table_df(summary["Patient problems"], row_labels)

    # Dictionary to map sheet names to their DataFrames
    sheets = {
        'Events': df_events,
        'Product Problems': df_product,
        'Patient Problems': df_patient
    }

    # Write to sheets and change column widths automatically to improve readability
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name)
                
                # Access the openpyxl worksheet object
                worksheet = writer.sheets[sheet_name]

                # Insert the title into the top left cell
                worksheet['A1'] = sheet_name
                worksheet['A1'].font = Font(bold=True)
                worksheet['A1'].alignment = Alignment(horizontal='center')
                
                # Iterate through all columns to find the max length
                for i, col in enumerate(df.columns, start=2): # start=2 because column A is the Index
                    # Calculate width of the header
                    column_len = len(str(col))
                    
                    # Check the width of the data in the rows
                    for val in df[col]:
                        column_len = max(column_len, len(str(val)))
                    
                    # Set the column width (adding a little extra padding)
                    header_cell_letter = worksheet.cell(row=1, column=i).column_letter
                    worksheet.column_dimensions[header_cell_letter].width = column_len + 3

                # Also adjust the Index column (Column A)
                index_col_letter = worksheet.cell(row=1, column=1).column_letter
                max_index_len = max([len(str(idx)) for idx in df.index] + [len(df.index.name or "")])
                worksheet.column_dimensions[index_col_letter].width = max_index_len + 3

    except PermissionError:
        print(f"\n[!] ERROR: Close '{os.path.basename(output_path)}' in Excel and try again.")

def write_summary_to_json_file(summary, output_path):
    """Writes the summary object to a formatted JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

def main():
    """Generates a summary file for each JSON file"""

    # Ensure the output directory exists
    if not os.path.exists(XSLX_ANALYSIS_FOLDER):
        os.makedirs(XSLX_ANALYSIS_FOLDER)

    if not os.path.exists(JSON_ANALYSIS_FOLDER):
        os.makedirs(JSON_ANALYSIS_FOLDER)

    # Check if the input directory exists
    if not os.path.exists(JSON_FOLDER):
        print(f"Error: The folder '{JSON_FOLDER}' does not exist.")
        return

    # Filter files in the directory for those ending in .json
    files = [f for f in os.listdir(JSON_FOLDER) if f.lower().endswith('.json')]

    if not files:
        print(f"No JSON files found in '{JSON_FOLDER}'")
        return

    print(f"Summarizing {len(files)} files...")

    for filename in files:
        input_path = os.path.join(JSON_FOLDER, filename)
        base_name = os.path.splitext(filename)[0]
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            summary_obj = summarize_mdr_incidents(raw_data)

            # Save as Text
            xlsx_path = os.path.join(XSLX_ANALYSIS_FOLDER, base_name + f"{FILENAME_END_TEXT}.xlsx")
            write_summary_to_xlsx_file(summary_obj, xlsx_path)

            # Save as JSON
            json_out_path = os.path.join(JSON_ANALYSIS_FOLDER, base_name + f"{FILENAME_END_TEXT}.json")
            write_summary_to_json_file(summary_obj, json_out_path)

            print(f"Processed: {filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("\nAll files summarized.")

if __name__ == "__main__":
    main()