import requests
import csv
import os
import re
import dedupe
import pandas as pd
from dotenv import load_dotenv

# Number of entries to retrieve with each API call (this is NOT the limit on the total number of entries that can be retrieved by the script)
# The max number of entries that can be recieved from OpenFDA API with a single call is 1000
BATCH_SIZE = 999

# Max number of characters in the description to look at when identifying duplicate events
# Higher will be more accurate, but will take longer to run
SHORT_DESCRIPTION_LENGTH = 1000

# Max number of entries to use when training the algorithm to identify duplicate events
TRAINING_SAMPLE_SIZE = 1000

# Priority of event to keep when merging duplicate groups into one entry
EVENT_SEVERITY = {"Other": 0, "Malfunction": 1, "Injury": 2, "Death": 3}

def fetch_maude_events(model_number, year_filter=None, api_key=None, limit=BATCH_SIZE):
    """Fetches ALL MAUDE adverse event reports using pagination."""
    base_url = "https://api.fda.gov/device/event.json"
    query = f'(device.model_number:"{model_number}" OR device.catalog_number:"{model_number}")'

    # Add year filter to query if provided
    if year_filter:
        year_queries = [f"date_of_event:[{year}0101 TO {year}1231]" for year in year_filter]
        date_query = " OR ".join(year_queries)
        query += f" AND ({date_query})"
    
    all_results = []
    skip = 0
    
    while True:
        params = {"search": query, "limit": limit, "skip": skip}
        if api_key:
            params["api_key"] = api_key

        try:
            response = requests.get(base_url, params=params)
            
            if response.status_code == 404:
                break # No more results found
                
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            all_results.extend(results)
            
            # If we fetched fewer items than the limit, we've reached the end
            if len(results) < limit:
                break
                
            # Increment skip for the next page
            skip += limit
            
            # OpenFDA has a hard limit of 25,000 for skip + limit
            if skip + limit > 25000:
                print(f"Warning: Reached OpenFDA pagination limit for {model_number}.")
                break

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {model_number}: {e}")
            break
            
    return all_results

def process_event_data(event, mod_num):
    """Extracts specific fields from the raw API response with separate manufacturer narrative."""
    device_info = event.get("device", [{}])[0]
    
    # Get all MDR text entries
    mdr_text_list = event.get("mdr_text", [])

    # Separate Description vs Additional Manufacturer Narrative
    description_texts = [
        t.get("text", "")
        for t in mdr_text_list
        if t.get("text") and t.get("text_type_code") == "Description of Event or Problem"
    ]
    description = " ".join(description_texts)

    manufacturer_narrative_texts = [
        t.get("text", "")
        for t in mdr_text_list
        if t.get("text") and t.get("text_type_code") == "Additional Manufacturer Narrative"
    ]
    manufacturer_narrative = " ".join(manufacturer_narrative_texts) if manufacturer_narrative_texts else "N/A"

    # Get all product problems
    product_problems = event.get("product_problems", [])
    product_problems_str = "; ".join([p for p in product_problems if p is not None]) if product_problems else "N/A"

    # Get all patient problems
    patients = event.get("patient", [])
    patient_problems = []
    for p in patients:
        problems = p.get("patient_problems", [])
        patient_problems.extend(problems)
    patient_problems_str = "; ".join(filter(None, patient_problems)) if patient_problems else "N/A"

    return {
        "Model Number": mod_num,
        "MDR Report Key": event.get("mdr_report_key", ""),
        "Brand Name": device_info.get("brand_name", "N/A"),
        "Manufacturer": device_info.get("manufacturer_d_name", "N/A"),
        "Lot Number": device_info.get("lot_number", "N/A"),
        "Date of Event": event.get("date_of_event", "N/A"),
        "Type of Event": event.get("event_type", "N/A"),
        "Product Problems": product_problems_str,
        "Patient Problems": patient_problems_str,
        "Description": description,
        "Additional Manufacturer Narrative": manufacturer_narrative
    }

def run_deduplication(data_list):
    if len(data_list) < 2:
        return data_list

    # 1. Prepare data for dedupe
    def normalize_record(record):
        cleaned = {}
        for k, v in record.items():
            if v in ["", "N/A", "UNKNOWN", None]:
                cleaned[k] = None
            else:
                cleaned[k] = v
        
        # Truncate the description to n characters ---
        desc = record.get('Description', '')
        if desc:
            cleaned['Description_Short'] = str(desc)[:SHORT_DESCRIPTION_LENGTH]
        else:
            cleaned['Description_Short'] = None
            
        return cleaned

    data_d = {
        str(i): normalize_record(record)
        for i, record in enumerate(data_list)
    }

    # 2. Define the fields dedupe will pay attention to 
    fields = [
        dedupe.variables.Exact('Model Number'),
        dedupe.variables.String('Date of Event', has_missing=True),
        dedupe.variables.String('Lot Number', has_missing=True),
        dedupe.variables.String('Type of Event', has_missing=True),
        dedupe.variables.String('Patient Problems', has_missing=True),
        dedupe.variables.String('Product Problems', has_missing=True),
        dedupe.variables.Text('Description_Short', has_missing=True),
    ]

    # 3. Initialize Deduper
    deduper = dedupe.Dedupe(fields)
    settings_file = 'maude_dedupe_settings'
    training_file = 'maude_dedupe_training.json'

    if os.path.exists(settings_file):
        print('Reading settings from', settings_file)
        with open(settings_file, 'rb') as f:
            deduper = dedupe.StaticDedupe(f)
    else:
        # To train, dedupe needs examples. This will prompt you in the console
        print('No settings file found. Starting active labeling.\nOnce data is prepared, you will be prompted to help train the identification algorithm...')
        deduper.prepare_training(data_d, sample_size=TRAINING_SAMPLE_SIZE)
        dedupe.console_label(deduper)
        deduper.train()

        with open(settings_file, 'wb') as f:
            deduper.write_settings(f)
        with open(training_file, 'w') as f:
            deduper.write_training(f)

    # 4. Clustering
    # This identifies groups and assigns a confidence score
    print('Identifying possible duplicates...')
    clustered_dupes = deduper.partition(data_d, threshold=0.5)

    # 5. Map results back to the original list
    # Initialize all with 0 (meaning no duplicate found)
    for record in data_list:
        record["Possible Duplicate Group"] = 0
        # record["Confidence Score"] = 0

    for cluster_id, (records, scores) in enumerate(clustered_dupes):
        for record_id, score in zip(records, scores):
            idx = int(record_id)
            data_list[idx]["Possible Duplicate Group"] = cluster_id + 1
            # data_list[idx]["Confidence Score"] = round(score, 4)

    # Count of duplicate events (counts only the extra records beyond the first one in each group)
    duplicate_event_count = sum(len(records) - 1 for records, _ in clustered_dupes)
    print(f"{duplicate_event_count} likely duplicate events found")

    return data_list

def merge_duplicate_groups(data_list):
    grouped = {}
    singles = []

    # 1. Categorize records once
    for record in data_list:
        gid = record.get("Possible Duplicate Group", 0)
        if gid > 0:
            grouped.setdefault(gid, []).append(record)
        else:
            singles.append(record)

    merged_results = []
    
    # 2. Process groups
    for gid, records in grouped.items():
        # Use first record as base template
        base = records[0].copy()
        
        for other in records[1:]:
            # --- Fill Blanks & Combine Narratives ---
            for key in ["Description", "Additional Manufacturer Narrative"]:
                val = other.get(key, "").strip()
                if val and val not in base[key]:
                    base[key] += f" :ADDITIONAL INFO FROM DUPLICATE REPORT: {val}"

            # --- Fill other missing fields ---
            for k, v in other.items():
                if base.get(k) in ["", "N/A", None] and v not in ["", "N/A", None]:
                    base[k] = v

            # --- Union Problem Sets (Helper logic) ---
            for field in ["Product Problems", "Patient Problems"]:
                base_vals = set(str(base.get(field, "")).split("; "))
                other_vals = set(str(other.get(field, "")).split("; "))
                combined = sorted({p for p in base_vals | other_vals if p and p != "N/A"})
                base[field] = "; ".join(combined) if combined else "N/A"

            # --- Severity Check ---
            base_sev = EVENT_SEVERITY.get(base.get("Type of Event", "Other"), 0)
            other_sev = EVENT_SEVERITY.get(other.get("Type of Event", "Other"), 0)
            if other_sev > base_sev:
                base["Type of Event"] = other["Type of Event"]

        merged_results.append(base)

    # 3. Get final list of events and remove Possible Duplicate Group field
    final_list = merged_results + singles
    for record in final_list:
        record.pop("Possible Duplicate Group", None)

    return final_list

def export_to_csv(data, filename="maude_export.csv"):
    """Writes the processed data list to a CSV file."""
    if not data:
        print("No data to export.")
        return

    export_dir = "data_csv_exports"
    os.makedirs(export_dir, exist_ok=True)

    filepath = os.path.join(export_dir, filename)

    keys = data[0].keys()
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
        print(f"Successfully exported to {filepath}")
    except IOError as e:
        print(f"Error writing CSV: {e}")

def clean_excel_text(text):
    if not isinstance(text, str):
        return text
    
    # Remove illegal control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    
    # Truncate to Excel cell limit (32,767 chars)
    return text[:32767]

def export_to_excel(data, filename="maude_export.xlsx"):
    """Writes the processed data list to an Excel file using pandas."""
    if not data:
        print("No data to export.")
        return

    export_dir = "data_excel_exports"
    os.makedirs(export_dir, exist_ok=True)

    filepath = os.path.join(export_dir, filename)

    try:
        # Convert list of dicts to a DataFrame
        df = pd.DataFrame(data)
        # Ensure the text can be written into Excel
        df = df.apply(lambda col: col.map(clean_excel_text))
        # Export to Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        print(f"Successfully exported to {filepath}")
    except Exception as e:
        print(f"Error writing Excel: {e}")

if __name__ == "__main__":
    cat_input = input("Enter Model Number(s) separated by commas (e.g., HAR1136, TB-0009OFX): ")
    cat_list = [c.strip() for c in cat_input.split(",") if c.strip()]

    year_input = input(
    "What years would you like to retrieve reports from? "
    "Enter in a comma-separated list (eg. 2024, 2025) or leave blank to retrieve reports from all years: "
    ).strip()
    year_filter = [y.strip() for y in year_input.split(",") if y.strip()] if year_input else None
    
    all_processed_results = []

    load_dotenv()
    MY_API_KEY = os.getenv("FDA_API_KEY")

    print("\n--- Fetching Data ---")
    for cat in cat_list:
        print(f"Searching for: {cat}...")
        raw_events = fetch_maude_events(cat, year_filter=year_filter, api_key=MY_API_KEY)
        
        for event in raw_events:
            processed = process_event_data(event, cat)
            all_processed_results.append(processed)
        
        print(f" Found {len(raw_events)} events.")

    if all_processed_results:
        # Run Deduplication
        dedupe_choice = input("\nWould you like to label likely duplicate events? (y/n): ").lower().strip()
        if dedupe_choice == 'y':
            all_processed_results = run_deduplication(all_processed_results)

            # Check if any groups actually exist before asking
            has_groups = any(r.get("Possible Duplicate Group", 0) > 0 for r in all_processed_results)
            
            # Merge duplicate groups
            if has_groups and input("\nWould you like to merge likely duplicate event groups into one entry? (y/n): ").lower() == 'y':
                all_processed_results = merge_duplicate_groups(all_processed_results)

        # Run Exports
        csv_choice = input("\nWould you like to export these results to CSV? (y/n): ").lower().strip()

        excel_choice = input("\nWould you like to export these results to Excel? (y/n): ").lower().strip()

        if csv_choice == 'y' or excel_choice == 'y':
            filename = input("\nEnter your desired filename: ").strip() or "maude_export"

            if csv_choice == 'y':
                export_to_csv(all_processed_results, f"{filename}.csv")

            if excel_choice == 'y':
                export_to_excel(all_processed_results, f"{filename}.xlsx")
            
    else:
        print("No results found for the provided Model Number(s).")