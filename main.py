import requests
import csv
import os
import pandas as pd
from dotenv import load_dotenv

BATCH_SIZE = 999 # max number of entries that can be recieved from OpenFDA API with a single call is 1000

def fetch_maude_events(catalog_number, api_key=None, limit=BATCH_SIZE):
    """Fetches ALL MAUDE adverse event reports using pagination."""
    base_url = "https://api.fda.gov/device/event.json"
    query = f'device.catalog_number:"{catalog_number}"'
    
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
                print(f"Warning: Reached OpenFDA pagination limit for {catalog_number}.")
                break

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {catalog_number}: {e}")
            break
            
    return all_results

def process_event_data(event, cat_num):
    """Extracts specific fields from the raw API response."""
    device_info = event.get("device", [{}])[0]
    
    mdr_text_list = event.get("mdr_text", [])
    description = " ".join([t.get("text", "") for t in mdr_text_list if t.get("text")])

    return {
        "Searched CAT": cat_num,
        "MDR Report Key": event.get("mdr_report_key", ""),
        "Brand Name": device_info.get("brand_name", "N/A"),
        "Manufacturer": device_info.get("manufacturer_d_name", "N/A"),
        "Lot Number": device_info.get("lot_number", "N/A"),
        "Problem Codes": "; ".join(device_info.get("mdr_problem_code", [])),
        "Health Effect Codes": "; ".join(event.get("patient", [{}])[0].get("patient_sequence_number_outcome", [])),
        "Date of Event": event.get("date_of_event", "N/A"),
        "Type of Event": event.get("event_type", "N/A"),
        "Description": description
    }

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

def export_to_excel(data, filename="maude_export.xlsx"):
    """Writes the processed data list to an Excel file using pandas."""
    if not data:
        print("No data to export.")
        return

    try:
        # Convert list of dicts to a DataFrame
        df = pd.DataFrame(data)
        # Export to Excel
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"Successfully exported to {filename}")
    except Exception as e:
        print(f"Error writing Excel: {e}")

if __name__ == "__main__":
    cat_input = input("Enter Catalog Number(s) separated by commas (e.g., HAR1136, HAR1100): ")
    cat_list = [c.strip() for c in cat_input.split(",") if c.strip()]
    
    all_processed_results = []
    MY_API_KEY = os.getenv("FDA_API_KEY")

    print("\n--- Fetching Data ---")
    for cat in cat_list:
        print(f"Searching for: {cat}...")
        raw_events = fetch_maude_events(cat, api_key=MY_API_KEY)
        
        for event in raw_events:
            processed = process_event_data(event, cat)
            all_processed_results.append(processed)
        
        print(f" Found {len(raw_events)} events.")

    if all_processed_results:
        # --- EXPORT SECTION ---
        csv_choice = input("\nWould you like to export these results to CSV? (y/n): ").lower().strip()
        if csv_choice == 'y':
            export_to_csv(all_processed_results)

        excel_choice = input("Would you like to export these results to Excel? (y/n): ").lower().strip()
        if excel_choice == 'y':
            export_to_excel(all_processed_results)
            
    else:
        print("No results found for the provided Catalog Number(s).")