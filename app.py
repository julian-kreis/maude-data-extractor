import streamlit as st
import streamlit.components.v1 as components
import os
import sys
from dotenv import load_dotenv
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
from analyze import (
    summarize_mdr_incidents,
    write_summary_to_xlsx_file,
    write_summary_to_json_file,
    FILENAME_END_TEXT,
    JSON_ANALYSIS_FOLDER,
    XSLX_ANALYSIS_FOLDER
)

load_dotenv()

# --- Utility: Ensure Folders Exist ---
for folder in [JSON_FOLDER, CSV_FOLDER, EXCEL_FOLDER, JSON_ANALYSIS_FOLDER, XSLX_ANALYSIS_FOLDER]:
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
    
def create_dl_button(column, label, path, mime, base_key, help_text=""):
    """
    Handles both string paths and Path objects. 
    Busts Streamlit cache using file modification time.
    """
    # Convert pathlib objects to strings for os.path functions
    path_str = str(path)
    
    if os.path.exists(path_str):
        # Get modified time to force a fresh key/cache bust
        mtime = os.path.getmtime(path_str)
        size = get_file_size_info(path) # Your existing size function
        
        with open(path_str, "rb") as f:
            column.download_button(
                label=f"{label} ({size})",
                data=f.read(),
                file_name=os.path.basename(path_str),
                mime=mime,
                key=f"{base_key}_{mtime}", # Unique ID based on time
                help=help_text
            )
    else:
        column.button(f"{label} N/A", disabled=True, key=f"{base_key}_na")

# --- Popup Dialogs ---
@st.dialog("Rename Record")
def rename_file_dialog(old_name, paths):
    st.write(f"Enter a new name for **{old_name}**:")
    new_name = st.text_input("New Name", value=old_name).strip()
    
    st.info("This will rename all associated files (JSON, CSV, Excel, and Analysis Summaries).")

    col1, col2 = st.columns(2)
    if col1.button("Save Changes", type="primary", use_container_width=True):
        if not new_name:
            st.error("Name cannot be empty.")
        elif new_name == old_name:
            st.rerun()
        else:
            try:
                for old_path in paths:
                    if os.path.exists(old_path):
                        # Split path to keep directory and extension, but change filename
                        directory = os.path.dirname(old_path)
                        extension = os.path.splitext(old_path)[1]
                        
                        # Preserve the suffix for analysis files
                        if FILENAME_END_TEXT in os.path.basename(old_path):
                            new_path = os.path.join(directory, f"{new_name}{FILENAME_END_TEXT}{extension}")
                        else:
                            new_path = os.path.join(directory, f"{new_name}{extension}")
                        
                        os.rename(old_path, new_path)
                st.rerun()
            except Exception as e:
                st.error(f"Error renaming files: {e}")
        
    if col2.button("Cancel", use_container_width=True):
        st.rerun()

@st.dialog("Confirm Deletion")
def confirm_delete_dialog(filename, paths):
    st.write(f"Are you sure you want to delete **{filename}**?")
    st.write("This will remove the JSON, CSV, Excel, and Analysis summary versions permanently.")
    
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
            api_key = st.text_input("Enter FDA API Key (optional)", type="password")
        else:
            st.success("API Key active.")

    # --- Section Data Retrieval ---
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

        if st.button("Run", type="primary"):
            if not cat_input:
                st.error("Model Number is required.")
            elif not filename.strip():
                st.error("Please provide a filename.")
            elif file_exists and not confirm_overwrite:
                st.error("Please confirm overwrite.")
            else:
                run_search_logic(cat_input, year_input, do_dedupe, do_merge, filename.strip(), api_key)

    st.divider()

    # --- Section Manage Records ---
    st.header("Manage Records")
    json_files = get_json_files()
    
    if not json_files:
        st.info("No saved records found.")
    else:
        # Column headers
        h_col1, h_col2, h_col3, h_col4 = st.columns([2, 3, 2, 1])
        h_col1.write("**Stored Record Name**")
        h_col2.write("**Data Downloads**")
        h_col3.write("**Summary Downloads**")
        h_col4.write("**Actions**")

        for f in json_files:
            col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
            clean_name = f.replace(".json", "")
            
            # Paths
            paths = {
                "json": os.path.join(JSON_FOLDER, f),
                "csv": os.path.join(CSV_FOLDER, f.replace(".json", ".csv")),
                "xlsx": os.path.join(EXCEL_FOLDER, f.replace(".json", ".xlsx")),
                "sum_json": os.path.join(JSON_ANALYSIS_FOLDER, f"{clean_name}{FILENAME_END_TEXT}.json"),
                "sum_xlsx": os.path.join(XSLX_ANALYSIS_FOLDER, f"{clean_name}{FILENAME_END_TEXT}.xlsx")
            }

            col1.markdown(f"**{clean_name}**")

            try:
                btn_json, btn_csv, btn_xlsx = col2.columns(3)
                btn_sum_json, btn_sum_xlsx = col3.columns(2)

                # JSON Download
                create_dl_button(btn_json, "JSON", paths["json"], "application/json", "dl_json", "Raw JSON")
                
                # CSV Download
                create_dl_button(btn_csv, "CSV", paths["csv"], "text/csv", "dl_csv", "Raw CSV")

                # Excel Download
                create_dl_button(btn_xlsx, "Excel", paths["xlsx"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "dl_xlsx", "Raw Excel")

                # Analysis Downloads
                create_dl_button(btn_sum_json, "JSON", paths["sum_json"], "application/json", "dl_sum_json", "Analysis Summary JSON")
                create_dl_button(btn_sum_xlsx, "Excel", paths["sum_xlsx"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "dl_sum_xlsx", "Analysis Summary Excel")

            except Exception as e:
                col2.error(f"Error accessing files: {e}")

            # --- Action Buttons ---
            act_col1, act_col2 = col4.columns(2)
            
            if act_col1.button("✏️", key=f"btn_edit_{f}", help="Rename this record"):
                rename_file_dialog(clean_name, file_paths)

            if act_col2.button("🗑️", key=f"btn_del_{f}", help="Delete this record"):
                confirm_delete_dialog(clean_name, file_paths)

def run_search_logic(cat_list_str, year_input, do_dedupe, do_merge, filename, api_key):
    cat_list = [c.strip() for c in cat_list_str.split(",") if c.strip()]
    year_filter = [y.strip() for y in year_input.split(",") if y.strip()] if year_input else None
    
    all_processed_results = []
    status_text = st.empty()
    
    # Progress bars and logic
    progress_bar = st.progress(0)
    steps = len(cat_list) + (1 if do_dedupe else 0) + (1 if do_dedupe and do_merge else 0) + 5 # +5 for data files and analysis files
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

        # SAVE RAW FORMATS
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

        # GENERATE AND SAVE ANALYSIS SUMMARIES
        status_text.text("Generating Analysis Summaries...")
        summary_obj = summarize_mdr_incidents(all_processed_results)
        
        status_text.text("Saving Analysis JSON...")
        write_summary_to_json_file(summary_obj, os.path.join(JSON_ANALYSIS_FOLDER, f"{filename}{FILENAME_END_TEXT}.json"))
        current_step += 1
        progress_bar.progress(current_step / steps)

        status_text.text("Saving Analysis Excel...")
        write_summary_to_xlsx_file(summary_obj, os.path.join(XSLX_ANALYSIS_FOLDER, f"{filename}{FILENAME_END_TEXT}.xlsx"))
        current_step += 1
        progress_bar.progress(current_step / steps)

        status_text.empty()
        st.success(f"Successfully saved '{filename}' raw files and analysis summaries.")
    else:
        status_text.empty()
        st.warning("No results found.")

if __name__ == "__main__":
    # This will "ping" our server to indicate that the page is active.
    # Once the page is closed or inactive, the pings will stop.
    if getattr(sys, 'frozen', False):
        components.html("""
            <script>
                function ping() {
                    var img = new Image();
                    img.src = "http://127.0.0.1:8502/ping?t=" + new Date().getTime();
                }
                setInterval(ping, 5000); // ping every 5 seconds
            </script>
        """, height=0)

    # Create pages
    home_page = st.Page(main, title="Home", icon="🏠")
    analysis_page = st.Page("pages/analysis.py", title="Data Analysis", icon="📈")
    comparison_page = st.Page("pages/comparison.py", title="Data Comparison", icon="📊")

    pg = st.navigation([home_page, analysis_page, comparison_page])
    pg.run()