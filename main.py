import requests
import csv
import os
import re
import dedupe
import pandas as pd
from dotenv import load_dotenv

BATCH_SIZE = 999 # max number of entries that can be recieved from OpenFDA API with a single call is 1000

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
    """Extracts specific fields from the raw API response."""
    device_info = event.get("device", [{}])[0]
    
    # Get all narrative on the description of the event
    mdr_text_list = event.get("mdr_text", [])
    description = " ".join([t.get("text", "") for t in mdr_text_list if t.get("text")])

    # Get all product problems
    product_problems = event.get("product_problems", [])
    product_problems_str = "; ".join([p for p in product_problems if p is not None]) if product_problems else "N/A"

    # Get all patient problems
    patients = event.get("patient", [])
    patient_problems = []
    for p in patients:
        problems = p.get("patient_problems", [])
        patient_problems.extend(problems)
    patient_problems_str = "; ".join(filter(None, patient_problems))

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
        "Description": description
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
        return cleaned

    data_d = {
        str(i): normalize_record(record)
        for i, record in enumerate(data_list)
    }

    # 2. Define the fields dedupe will pay attention to 
    fields = [
        dedupe.variables.Exact('Model Number'),
        dedupe.variables.Exact('Date of Event'),
        dedupe.variables.String('Lot Number', has_missing=True),
        dedupe.variables.String('Type of Event', has_missing=True),
        dedupe.variables.String('Patient Problems', has_missing=True),
        dedupe.variables.String('Product Problems', has_missing=True),
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
        print('Starting active labeling...')
        deduper.prepare_training(data_d)
        dedupe.console_label(deduper)
        deduper.train()

        with open(settings_file, 'wb') as f:
            deduper.write_settings(f)
        with open(training_file, 'w') as f:
            deduper.write_training(f)

    # 5. Clustering
    # This identifies groups and assigns a confidence score
    print('Identifying possible duplicates...')
    clustered_dupes = deduper.partition(data_d, threshold=0.5)

    # 6. Map results back to the original list
    # Initialize all with 0 (meaning no duplicate found)
    for record in data_list:
        record["Possible Duplicate Group"] = 0
        # record["Confidence Score"] = 0

    for cluster_id, (records, scores) in enumerate(clustered_dupes):
        for record_id, score in zip(records, scores):
            idx = int(record_id)
            data_list[idx]["Possible Duplicate Group"] = cluster_id + 1
            # data_list[idx]["Confidence Score"] = round(score, 4)

    return data_list

def export_to_csv(data, filename="maude_export.csv"):
    """Writes the processed data list to a CSV file."""
    if not data:
        print("No data to export.")
        return

    keys = data[0].keys()
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
        print(f"Successfully exported to {filename}")
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

    try:
        # Convert list of dicts to a DataFrame
        df = pd.DataFrame(data)
        # Ensure the text can be written into Excel
        df = df.apply(lambda col: col.map(clean_excel_text))
        # Export to Excel
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"Successfully exported to {filename}")
    except Exception as e:
        print(f"Error writing Excel: {e}")

if __name__ == "__main__":
    cat_input = input("Enter Model Number(s) separated by commas (e.g., HAR1136, HAR1100): ")
    cat_list = [c.strip() for c in cat_input.split(",") if c.strip()]

    year_input = input(
    "What years would you like to retrieve reports from? "
    "Enter in a comma-separated list (eg. 2024, 2025) or leave blank to retrieve reports from all years: "
    ).strip()
    year_filter = [y.strip() for y in year_input.split(",") if y.strip()] if year_input else None
    
    all_processed_results = []
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
        all_processed_results = run_deduplication(all_processed_results)
        print("Possible duplicate events labeled")

        # --- EXPORT SECTION ---
        csv_choice = input("\nWould you like to export these results to CSV? (y/n): ").lower().strip()
        if csv_choice == 'y':
            export_to_csv(all_processed_results)

        excel_choice = input("Would you like to export these results to Excel? (y/n): ").lower().strip()
        if excel_choice == 'y':
            export_to_excel(all_processed_results)
            
    else:
        print("No results found for the provided Model Number(s).")