import os
import re
from openpyxl.styles import (
    Font,
    Alignment
)
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
import pandas as pd
import collections
import json
from retrieve import (
    JSON_FOLDER,
    LIST_STR,
    EMPTY_FIELD
)

# Text that is added onto the end of the filename
FILENAME_END_TEXT = "_summary"

# Max number of most-used 1-3 word phrases to record
TOP_N = 100

# Subphrase duplicate threshold
# If a shorter phrase is contained in a longer phrase with at least this frequency,
# removes it from the list of common phrases
DUPLICATE_THRESHOLD = 0.9

# Length of phrases to look for
MIN_PHRASE_WORDCOUNT = 1
MAX_PHRASE_WORDCOUNT = 12

# Words to remove when looking for most the most common words/phrases due to
# being general boilerplate medical report text that would clog the results
# Note that basic English words are automatically added through ENGLISH_STOP_WORDS
IGNORED_WORDS = {
    "reported","event","procedure","provided", "use", "duplicate", "report",
    "medical","customer","received","associated","consequence", "consequences",
    "resulted","information","using","during", "surgery","unknown", "patient",
    "complete", "completed","observed","additional","another", "adverse"
}

# Folder names for where exported data is stored
JSON_ANALYSIS_FOLDER = "analysis_json"
XSLX_ANALYSIS_FOLDER = "analysis_excel"

def find_common_phrases(data, top_n=TOP_N):
    """
    Finds common phrases within sentence boundaries. 
    Removes sub-phrases if a longer parent phrase captures 
    at least 90% of its occurrences.
    """

    def remove_subphrases(candidate_results, max_len=MAX_PHRASE_WORDCOUNT, threshold=DUPLICATE_THRESHOLD):
        # DOES NOT MAINTAIN LIST ORDER

        # tokenize + sort longest first
        phrases = [
            (tuple(p.split()), c)
            for p, c in candidate_results
            if len(p.split()) <= max_len
        ]

        phrases.sort(key=lambda x: (-len(x[0]), -x[1]))

        # substring index built ONLY from kept longer phrases
        substring_index = collections.defaultdict(list)

        filtered = []

        for tokens, count in phrases:
            redundant = False

            # check if any longer kept phrase contains this
            for parent_tokens, parent_count in substring_index.get(tokens, []):
                if parent_count >= threshold * count:
                    redundant = True
                    break

            if not redundant:
                filtered.append((" ".join(tokens), count))

                # add this phrase to index so it can remove shorter ones
                length = len(tokens)
                for sub_len in range(1, length):
                    for i in range(length - sub_len + 1):
                        substring = tokens[i:i+sub_len]
                        substring_index[substring].append((tokens, count))

        return filtered

    stop_words = set(ENGLISH_STOP_WORDS).union(IGNORED_WORDS)

    # Pre-process into "Sentence-Blocked" strings
    # Join sentences with a special non-alphanumeric character 
    # and tell CountVectorizer to only look at words.
    processed_descriptions = []
    for entry in data:
        desc = entry.get("Description", "")
        # Split by sentence, clean, then join with a '.' to ensure n-grams don't bridge
        sentences = re.split(r'[.!?]+', desc.lower())
        # We join with a period because the default tokenizer in sklearn 
        # treats punctuation as a separator and won't form n-grams across it.
        processed_descriptions.append(". ".join(sentences))

    # Vectorize
    stop_words = list(set(ENGLISH_STOP_WORDS).union(IGNORED_WORDS))
    vectorizer = CountVectorizer(
        ngram_range=(MIN_PHRASE_WORDCOUNT, MAX_PHRASE_WORDCOUNT),
        stop_words=stop_words,
        binary=True, # Count only once per report
        min_df=2
    )
    
    X = vectorizer.fit_transform(processed_descriptions)
    
    # Aggregate Counts
    counts = X.sum(axis=0).A1.tolist()
    terms = vectorizer.get_feature_names_out()
    all_results = sorted(zip(terms, counts), key=lambda x: x[1], reverse=True)

    # Remove common subphrases as duplicates
    filtered_results = remove_subphrases(all_results[:top_n*5]) # no limit causes unneeded processing time, too small a limit can delete valid results

    # Return the top phrases in order
    filtered_results.sort(key=lambda x: x[1], reverse=True)
    return filtered_results[:top_n]

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
        "Patient problems": {},
        "Common phrases": {}
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

    # Add most-used phrases
    summary["Common phrases"] = find_common_phrases(data)

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
    df_phrases = pd.DataFrame(summary["Common phrases"], columns=["Phrase", "Event count"])

    # Dictionary to map sheet names to their DataFrames
    sheets = {
        'Events': df_events,
        'Product Problems': df_product,
        'Patient Problems': df_patient,
        'Common Description Phrases': df_phrases
    }

    # Write to sheets and change column widths automatically to improve readability
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for sheet_name, df in sheets.items():
                include_index = (sheet_name != 'Common Description Phrases')

                df.to_excel(writer, sheet_name=sheet_name, index=include_index)
                
                # Access the openpyxl worksheet object
                worksheet = writer.sheets[sheet_name]

                # Column Auto-Width Logic
                # Adjusting start point based on whether index is present
                start_col = 2 if include_index else 1
                
                for i, col in enumerate(df.columns, start=start_col):
                    column_len = max(len(str(col)), df[col].astype(str).map(len).max())
                    cell_letter = worksheet.cell(row=1, column=i).column_letter
                    worksheet.column_dimensions[cell_letter].width = column_len + 3

                if include_index:
                    # Insert the title into the top left cell
                    worksheet['A1'] = sheet_name
                    worksheet['A1'].font = Font(bold=True)
                    worksheet['A1'].alignment = Alignment(horizontal='center')
                
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