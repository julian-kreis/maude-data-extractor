import streamlit as st
import os
from dotenv import load_dotenv

# Importing functions AND folder constants from retrieve
from retrieve import (
    fetch_maude_events,
    process_event_data,
    run_deduplication,
    merge_duplicate_groups,
    export_to_json,
    export_to_csv,
    export_to_excel,
    JSON_FOLDER,
    CSV_FOLDER,
    EXCEL_FOLDER
)

load_dotenv()

# --- Utility: Ensure Folders Exist ---
for folder in [JSON_FOLDER, CSV_FOLDER, EXCEL_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# --- Helper Functions ---
def get_json_files():
    if not os.path.exists(JSON_FOLDER):
        return []
    return sorted([f for f in os.listdir(JSON_FOLDER) if f.endswith(".json")])

def get_file_size_info(filepath):
    """Returns a formatted string of the file size."""
    if not os.path.exists(filepath):
        return "N/A"
    size_bytes = os.path.getsize(filepath)
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

# Popup Deletion Confirmation Dialog ---
@st.dialog("Confirm Deletion")
def confirm_delete_dialog(filename, paths):
    st.write(f"Are you sure you want to delete **{filename}**?")
    st.write("This will remove the JSON, CSV, and Excel versions permanently.")
    
    col1, col2 = st.columns(2)
    if col1.button("Yes, Delete", type="primary", use_container_width=True):
        for path in paths:
            if os.path.exists(path):
                os.remove(path)
        st.rerun() # This closes the dialog and refreshes the file list
        
    if col2.button("Cancel", use_container_width=True):
        st.rerun() # This simply closes the dialog

# --- UI Configuration ---
st.set_page_config(page_title="MAUDE Data Extractor", page_icon="🏥", layout="wide")

def main():
    st.title("🏥 MAUDE Data Extractor")

    # --- Sidebar: API Configuration ---
    with st.sidebar:
        st.header("Settings")
        api_key = os.getenv("FDA_API_KEY")
        if not api_key:
            api_key = st.text_input("Enter FDA API Key", type="password")
        else:
            st.success("API Key active.")

    # --- Section 1: Data Retrieval ---
    st.header("Fetch & Save Data")
    
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            cat_input = st.text_input("Model Number(s)", placeholder="e.g. HAR1136, TB-0009OFX")
        with col_b:
            year_input = st.text_input("Year(s) (Optional)", placeholder="e.g. 2024, 2025")

        st.subheader("Processing Options")
        c1, c2 = st.columns(2)
        do_dedupe = c1.checkbox("Mark possible duplicate groups", value=True)
        do_merge = c2.checkbox("Merge duplicate groups", value=True, disabled=not do_dedupe)

        filename = st.text_input(
            "Save as (Filename)",
            value="",
            key="filename_input",
            placeholder="e.g. MyReport"
        )
        
        full_filename = f"{filename}.json" if filename.strip() else ""
        file_exists = os.path.exists(os.path.join(JSON_FOLDER, full_filename)) if full_filename else False

        confirm_overwrite = False
        if file_exists:
            st.warning(f"⚠️ A record named '{filename}' already exists.")
            confirm_overwrite = st.checkbox("Confirm Overwrite")

        if st.button("🚀 Run & Save Records", type="primary"):
            if not cat_input:
                st.error("Model Number is required.")
            elif not filename.strip():
                st.error("Please provide a filename.")
            elif file_exists and not confirm_overwrite:
                st.error("Please confirm overwrite.")
            else:
                run_search_logic(cat_input, year_input, do_dedupe, do_merge, filename.strip(), api_key)

    st.divider()

    # --- Section 2: Manage Records ---
    st.header("Manage Records")
    json_files = get_json_files()
    
    if not json_files:
        st.info("No saved records found.")
    else:
        h_col1, h_col2, h_col3 = st.columns([2, 4, 1])
        h_col1.write("**Stored Record Name**")
        h_col2.write("**Downloads**")
        h_col3.write("**Action**")

        for f in json_files:
            col1, col2, col3 = st.columns([2, 4, 1])
            clean_name = f.replace(".json", "")
            
            json_path = os.path.join(JSON_FOLDER, f)
            csv_path = os.path.join(CSV_FOLDER, f.replace(".json", ".csv"))
            xlsx_path = os.path.join(EXCEL_FOLDER, f.replace(".json", ".xlsx"))

            col1.markdown(f"**{clean_name}**")

            # Download Buttons
            try:
                btn_json, btn_csv, btn_xlsx = col2.columns(3)

                # JSON Download
                json_size = get_file_size_info(json_path)
                btn_json.download_button(
                    f"JSON ({json_size})",
                    data=open(json_path, "rb"),
                    file_name=f,
                    mime="application/json",
                    key=f"dl_json_{f}"
                )

                # CSV Download
                csv_size = get_file_size_info(csv_path)
                if os.path.exists(csv_path):
                    btn_csv.download_button(
                        f"CSV ({csv_size})",
                        data=open(csv_path, "rb"),
                        file_name=f.replace(".json", ".csv"),
                        mime="text/csv",
                        key=f"dl_csv_{f}"
                    )
                else:
                    btn_csv.button("CSV N/A", disabled=True, key=f"dl_csv_na_{f}")

                # Excel Download
                xlsx_size = get_file_size_info(xlsx_path)
                if os.path.exists(xlsx_path):
                    btn_xlsx.download_button(
                        f"Excel ({xlsx_size})",
                        data=open(xlsx_path, "rb"),
                        file_name=f.replace(".json", ".xlsx"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_xlsx_{f}"
                    )
                else:
                    btn_xlsx.button("Excel N/A", disabled=True, key=f"dl_xlsx_na_{f}")
            
            except Exception as e:
                col2.error("Error accessing files")

            # --- POPUP TRIGGER ---
            if col3.button("🗑️", key=f"btn_pop_{f}", help="Delete this record"):
                confirm_delete_dialog(clean_name, [json_path, csv_path, xlsx_path])

def run_search_logic(cat_list_str, year_input, do_dedupe, do_merge, filename, api_key):
    cat_list = [c.strip() for c in cat_list_str.split(",") if c.strip()]
    year_filter = [y.strip() for y in year_input.split(",") if y.strip()] if year_input else None
    
    all_processed_results = []
    status_text = st.empty()
    
    # Progress bars and logic
    progress_bar = st.progress(0)
    steps = len(cat_list) + (1 if do_dedupe else 0) + (1 if do_dedupe and do_merge else 0) + 3 # +3 for the 3 exports
    current_step = 0

    for cat in cat_list:
        status_text.text(f"Fetching: {cat}...")
        raw_events = fetch_maude_events(cat, year_filter=year_filter, api_key=api_key)
        for event in raw_events:
            all_processed_results.append(process_event_data(event, cat))
        current_step += 1
        progress_bar.progress(current_step / steps)

    if all_processed_results:
        if do_dedupe:
            status_text.text("Marking likely duplicate groups...")
            all_processed_results = run_deduplication(all_processed_results)
            current_step += 1
            progress_bar.progress(current_step / steps)
            if do_merge:
                status_text.text("Merging duplicate groups...")
                all_processed_results = merge_duplicate_groups(all_processed_results)
                current_step += 1
                progress_bar.progress(current_step / steps)

        # SAVE ALL THREE FORMATS
        status_text.text("Saving JSON...")
        export_to_json(all_processed_results, f"{filename}.json")
        current_step += 1
        progress_bar.progress(current_step / steps)

        status_text.text("Saving CSV...")
        export_to_csv(all_processed_results, f"{filename}.csv")
        current_step += 1
        progress_bar.progress(current_step / steps)

        status_text.text("Saving Excel...")
        export_to_excel(all_processed_results, f"{filename}.xlsx")
        current_step += 1
        progress_bar.progress(current_step / steps)

        status_text.empty()
        st.success(f"Successfully saved '{filename}' in JSON, CSV, and Excel formats.")
    else:
        status_text.empty()
        st.warning("No results found.")

if __name__ == "__main__":
    main()