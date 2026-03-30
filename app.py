import streamlit as st
import os
import json
import io
import pandas as pd
from dotenv import load_dotenv

# Importing functions AND folder constants from retrieve
from retrieve import (
    fetch_maude_events,
    process_event_data,
    run_deduplication,
    merge_duplicate_groups,
    export_to_json,
    JSON_FOLDER
)

load_dotenv()

# --- Utility: Ensure Folders Exist ---
os.makedirs(JSON_FOLDER, exist_ok=True)

# --- Helper Functions ---
def get_json_files():
    if not os.path.exists(JSON_FOLDER):
        return []
    return sorted([f for f in os.listdir(JSON_FOLDER) if f.endswith(".json")])

def stream_json_objects(path):
    decoder = json.JSONDecoder()
    with open(path, "r", encoding="utf-8") as f:
        buffer = ""
        for chunk in iter(lambda: f.read(8192), ""):
            buffer += chunk
            while buffer:
                buffer = buffer.lstrip()
                try:
                    obj, idx = decoder.raw_decode(buffer)
                    yield obj
                    buffer = buffer[idx:]
                except json.JSONDecodeError:
                    break

def convert_to_csv_bytes_stream(filename):
    path = os.path.join(JSON_FOLDER, filename)
    output = io.StringIO()

    first = True
    for obj in stream_json_objects(path):
        df = pd.DataFrame([obj])
        df.to_csv(output, index=False, header=first)
        first = False

    return output.getvalue().encode("utf-8")

def convert_to_excel_bytes_stream(filename):
    path = os.path.join(JSON_FOLDER, filename)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        row = 0
        header_written = False

        for obj in stream_json_objects(path):
            df = pd.DataFrame([obj])
            df.to_excel(
                writer,
                index=False,
                startrow=row,
                header=not header_written
            )
            header_written = True
            row += len(df)

    return output.getvalue()

def stream_json_download(path):
    with open(path, "rb") as f:
        return f.read()

def stream_csv_download(filename):
    return convert_to_csv_bytes_stream(filename)

def stream_excel_download(filename):
    return convert_to_excel_bytes_stream(filename)

# --- UI Configuration ---
st.set_page_config(page_title="MAUDE Data Manager", page_icon="🏥", layout="wide")

def main():
    st.title("🏥 MAUDE Data Manager")

    # --- Sidebar: API Configuration ---
    with st.sidebar:
        st.header("Settings")
        api_key = os.getenv("FDA_API_KEY")
        if not api_key:
            api_key = st.text_input("Enter FDA API Key", type="password")
        else:
            st.success("API Key active.")

    # --- Section 1: Data Retrieval ---
    st.header("1. Fetch & Archive Data")
    
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            cat_input = st.text_input("Model Number(s)", placeholder="e.g., HAR1136")
        with col_b:
            year_input = st.text_input("Year Filter", placeholder="e.g., 2024")

        st.subheader("Processing Options")
        c1, c2 = st.columns(2)
        do_dedupe = c1.checkbox("Deduplicate results", value=True)
        do_merge = c2.checkbox("Merge duplicate groups", value=True, disabled=not do_dedupe)

        # Default value is empty string
        filename = st.text_input(
            "Save as (Filename)",
            value="",
            key="filename_input",
            placeholder="Enter a filename to enable export"
        )
        
        full_filename = f"{filename}.json" if filename.strip() else ""
        file_exists = os.path.exists(os.path.join(JSON_FOLDER, full_filename)) if full_filename else False

        # Overwrite Confirmation Logic
        confirm_overwrite = False
        if file_exists:
            st.warning(f"⚠️ A file named '{full_filename}' already exists.")
            confirm_overwrite = st.checkbox("Confirm Overwrite")

        # Added check for 'filename' to the button condition
        if st.button("🚀 Run & Save to JSON", type="primary"):
            if not cat_input:
                st.error("Model Number is required.")
            elif not filename.strip():
                st.error("Please provide a filename before exporting.")
            elif file_exists and not confirm_overwrite:
                st.error("Please confirm overwrite to proceed.")
            else:
                run_search_logic(cat_input, year_input, do_dedupe, do_merge, filename.strip(), api_key)
                st.rerun()

    st.divider()

    # --- Section 2: JSON File Management ---
    st.header("2. Manage Records")
    
    json_files = get_json_files()
    
    if not json_files:
        st.info("No saved records found.")
    else:
        h_col1, h_col2, h_col3 = st.columns([2, 3, 1])
        h_col1.write("**Stored Record (JSON)**")
        h_col2.write("**Convert & Download**")
        h_col3.write("**Delete**")

        for f in json_files:
            col1, col2, col3 = st.columns([2, 3, 1])
            
            file_path = os.path.join(JSON_FOLDER, f)
            size_kb = os.path.getsize(file_path) / 1024
            col1.markdown(f"**{f}** \n`{size_kb:.1f} KB`")

            try:
                btn_json, btn_csv, btn_xlsx = col2.columns(3)

                # JSON (true streaming, no memory load)
                btn_json.download_button(
                    "JSON",
                    data=open(file_path, "rb"),
                    file_name=f,
                    mime="application/json"
                )

                # CSV (lazy conversion)
                btn_csv.download_button(
                    "CSV",
                    data=lambda f=f: convert_to_csv_bytes_stream(f),
                    file_name=f.replace(".json", ".csv"),
                    mime="text/csv"
                )

                # Excel (lazy conversion)
                btn_xlsx.download_button(
                    "Excel",
                    data=lambda f=f: convert_to_excel_bytes_stream(f),
                    file_name=f.replace(".json", ".xlsx"),
                    mime="application/vnd.ms-excel"
                )
            
            except Exception:
                col2.error("Error loading file")

            # Delete triggers st.rerun(), which closes the popover by refreshing the view
            with col3.popover("🗑️"):
                st.write(f"Delete '{f}'?")
                if st.button("Confirm Delete", key=f"del_{f}", type="primary"):
                    os.remove(file_path)
                    st.rerun()

def run_search_logic(cat_list_str, year_input, do_dedupe, do_merge, filename, api_key):
    cat_list = [c.strip() for c in cat_list_str.split(",") if c.strip()]
    year_filter = [y.strip() for y in year_input.split(",") if y.strip()] if year_input else None
    
    all_processed_results = []
    status_text = st.empty()
    
    progress_bar = st.progress(0)
    progress_bar_progress = 0
    progress_bar_length = len(cat_list)
    if do_dedupe: progress_bar_length += 1 
    if do_merge: progress_bar_length += 1

    for idx, cat in enumerate(cat_list):
        status_text.text(f"Fetching: {cat}...")
        raw_events = fetch_maude_events(cat, year_filter=year_filter, api_key=api_key)
        for event in raw_events:
            all_processed_results.append(process_event_data(event, cat))
        progress_bar_progress += 1
        progress_bar.progress(progress_bar_progress / progress_bar_length)

    if all_processed_results:
        if do_dedupe:
            status_text.text("Cleaning duplicates...")
            all_processed_results = run_deduplication(all_processed_results)
            progress_bar_progress += 1
            progress_bar.progress(progress_bar_progress / progress_bar_length)
            if do_merge:
                all_processed_results = merge_duplicate_groups(all_processed_results)
                progress_bar_progress += 1
                progress_bar.progress(progress_bar_progress / progress_bar_length)

        export_to_json(all_processed_results, f"{filename}.json")
        status_text.empty()
        st.success(f"Archived {len(all_processed_results)} events to {filename}.json")
    else:
        status_text.empty()
        st.warning("No results found.")

if __name__ == "__main__":
    main()