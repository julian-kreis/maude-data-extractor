import streamlit as st
import pandas as pd
import plotly.express as px
import json
from datetime import datetime
from pathlib import Path
from analyze import (
    TOP_N,
    DUPLICATE_THRESHOLD,
    JSON_ANALYSIS_FOLDER,
    XSLX_ANALYSIS_FOLDER,
    FILENAME_END_TEXT
)
from app import get_file_size_info
from retrieve import EMPTY_FIELD

# Other label lists examples within this label, but gets truncated to this many characters
OTHER_LABEL_MAX_CHARS = 50

# Configure the page layout
st.set_page_config(page_title="Incident Analysis", layout="wide")

# Path resolution
ROOT_DIR = Path(__file__).parent.parent
JSON_DIR = ROOT_DIR / JSON_ANALYSIS_FOLDER
XLSX_DIR = ROOT_DIR / XSLX_ANALYSIS_FOLDER

@st.cache_data
def load_json_data(filepath):
    with open(filepath, "r") as f:
        return json.load(f)
    
def format_date(date_str):
    """Formats dates in form yyyymmdd to be human-readable"""
    if not date_str or date_str == EMPTY_FIELD:
        return EMPTY_FIELD
    try:
        return datetime.strptime(date_str, "%Y%m%d").strftime("%B %d, %Y")
    except ValueError:
        return date_str

def process_data_for_pie(data_dict, create_other_category=False):
    """
    Optionally groups categories < 1% into 'Other'.
    Returns a DataFrame ready for plotting.
    """
    if not data_dict:
        return pd.DataFrame()

    total_sum = sum(data_dict.values())
    if total_sum == 0:
        return pd.DataFrame()

    main_items = {}
    other_items = []
    other_sum = 0

    for label, value in data_dict.items():
        percentage = (value / total_sum)
        if create_other_category and percentage < 0.01:
            other_items.append(label)
            other_sum += value
        else:
            main_items[label] = value

    # Create the 'Other' label if there is an other catergory
    if other_items:
        other_label = f"Other ({', '.join(other_items)})"
        # prevents "Other" category name from being too long
        if len(other_label) > OTHER_LABEL_MAX_CHARS: other_label = f"{other_label[0:OTHER_LABEL_MAX_CHARS - 3]}..."
        main_items[other_label] = other_sum

    return pd.DataFrame(list(main_items.items()), columns=["Category", "Count"])

def plot_pie_charts_for_models(data_dict, models, title_suffix):
    """Plots pie charts side-by-side with 'Other' grouping for small slices."""
    cols = st.columns(2)
    
    for i, model in enumerate(models):
        # Extract specific model data
        raw_model_data = {
            category: data_dict[category].get(model, 0) 
            for category in data_dict.keys() 
            if category != "total" and data_dict[category].get(model, 0) > 0
        }
        
        df = process_data_for_pie(raw_model_data, create_other_category=True)
        col_idx = i % 2
        
        with cols[col_idx]:
            if not df.empty:
                fig = px.pie(
                    df, 
                    values="Count", 
                    names="Category", 
                    title=f"{model} - {title_suffix}",
                    hole=0.3
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                # Updated width parameter for 2026 standards
                st.plotly_chart(fig, width='stretch')
            else:
                st.info(f"No {title_suffix.lower()} recorded for {model}.")

def main():
    st.sidebar.title("Data Selection")
    
    if not JSON_DIR.exists():
        st.error(f"Directory {JSON_DIR} not found.")
        return

    # Show user clean file list names visually, while maintaining full file names in the backend
    suffix = f"{FILENAME_END_TEXT}.json"

    # Get the file list
    files = list(JSON_DIR.glob("*.json"))

    # Use format_func to strip the suffix visually
    selected_file = st.sidebar.selectbox(
        "Choose Record",
        options=files,
        format_func=lambda x: x.name.removesuffix(suffix)
    )

    if selected_file:
        with open(selected_file) as f:
            data = json.load(f)

        # --- SIDEBAR DOWNLOAD BUTTONS ---
        st.sidebar.divider()
        st.sidebar.subheader("Download Summary Data")

        json_size = get_file_size_info(selected_file)
        json_bytes = selected_file.read_bytes()
        st.sidebar.download_button(
            label=f"JSON ({json_size})",
            data=json_bytes,
            file_name=selected_file.name,
            mime="application/json",
            key=f"dl_json_{selected_file.stem}"
        )

        xlsx_filename = selected_file.stem + ".xlsx"
        xlsx_path = XLSX_DIR / xlsx_filename
        if xlsx_path.exists():
            xlsx_size = get_file_size_info(xlsx_path)
            xlsx_bytes = xlsx_path.read_bytes()
            st.sidebar.download_button(
                label=f"Excel ({xlsx_size})",
                data=xlsx_bytes,
                file_name=xlsx_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_xlsx_{selected_file.stem}"
            )

        models = data.get("list of models", [])
        start_date = format_date(data.get("earliest incident date"))
        end_date = format_date(data.get("latest incident date"))

        st.title("Device Incident Analysis Dashboard")
        st.subheader(f"Record: {selected_file.name.removesuffix(suffix)}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Models:** {', '.join(models)}")
        with c2:
            st.markdown(f"**Date Range:** {start_date} to {end_date}")
            
        st.divider()

        # --- Bar Chart: Total Incidents by Type ---
        st.subheader("Total Incidents by Event Type")
        events_data = data.get("type of event", {})
        event_types = [k for k in events_data.keys() if k != "total"]
        event_totals = [events_data[k].get("total", 0) for k in event_types]
        
        df_events = pd.DataFrame({"Event Type": event_types, "Total Incidents": event_totals})
        fig_events = px.bar(df_events, x="Event Type", y="Total Incidents", color="Event Type", text_auto=True)
        st.plotly_chart(fig_events, width='stretch')

        # --- Bar Chart: Total Incidents by Product Model ---
        st.subheader("Total Incidents by Product Model")
        model_totals_dict = events_data.get("total", {})
        model_totals = [model_totals_dict.get(m, 0) for m in models]
        
        df_models = pd.DataFrame({"Product Model": models, "Total Incidents": model_totals})
        fig_models = px.bar(df_models, x="Product Model", y="Total Incidents", color="Product Model", text_auto=True)
        st.plotly_chart(fig_models, width='stretch')

        st.divider()

        # --- Pie Charts: Event Types by Model ---
        st.subheader("Incident Types by Product Model")
        plot_pie_charts_for_models(events_data, models, "Event Types")

        st.divider()

        # --- Pie Charts: Product Problems ---
        st.subheader("Product Problems")
        st.text("Note that some incident reports may list multiple product problems, which are all counted here")
        prod_probs = data.get("Product problems", {})
        
        # Total Product Problems (Aggregated)
        total_pp_raw = {p: prod_probs[p].get("total", 0) for p in prod_probs.keys() if prod_probs[p].get("total", 0) > 0}
        df_pp_total = process_data_for_pie(total_pp_raw, create_other_category=True)
        
        if not df_pp_total.empty:
            fig_pp_tot = px.pie(df_pp_total, values="Count", names="Category", title="Total Product Problems (All Models)")
            fig_pp_tot.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
            st.plotly_chart(fig_pp_tot, width='stretch')
            
        st.markdown("##### Product Problems Breakdown by Model")
        plot_pie_charts_for_models(prod_probs, models, "Product Problems")

        st.divider()

        # --- Pie Charts: Patient Problems ---
        st.subheader("Patient Problems")
        st.text("Note that some incident reports may list multiple patient problems, which are all counted here")
        pat_probs = data.get("Patient problems", {})
        
        # Total Patient Problems (Aggregated)
        total_pat_raw = {p: pat_probs[p].get("total", 0) for p in pat_probs.keys() if pat_probs[p].get("total", 0) > 0}
        df_pat_total = process_data_for_pie(total_pat_raw, create_other_category=True)
        
        if not df_pat_total.empty:
            fig_pat_tot = px.pie(df_pat_total, values="Count", names="Category", title="Total Patient Problems (All Models)")
            fig_pat_tot.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
            st.plotly_chart(fig_pat_tot, width='stretch')
            
        st.markdown("##### Patient Problems Breakdown by Model")
        plot_pie_charts_for_models(pat_probs, models, "Patient Problems")

        st.divider()

        # --- Section: Common Phrases ---
        st.subheader("Common Words & Phrases in Report Descriptions")
        st.text(f"Looks for the top {TOP_N} most common words/phrases based on how many reports they appeared in. If a shorter phrase appeared in a longer phrase in >={DUPLICATE_THRESHOLD*100}% of occurences, the shorter phrase was removed from the list to reduce the number of duplicate entries. Some phrases are missing common, non-descriptive words (eg. \"the\", \"as\", \"that\") and boilerplate medical report words (eg. \"reported\", \"observed\", \"information\") as those were removed to improve analysis.")

        phrases_raw = data.get("Common phrases", [])
        # Get the total number of incidents to calculate the percentage
        total_incidents = data.get("type of event", {}).get("total", {}).get("total", 1)

        if phrases_raw:
            # Create the DataFrame
            df_phrases = pd.DataFrame(phrases_raw, columns=["Phrase", "Count"])
            
            # Calculate the % frequency
            df_phrases["Frequency %"] = (df_phrases["Count"] / total_incidents) * 100

            # Display as a scrolling list with a Progress Column
            st.dataframe(
                df_phrases.sort_values(by="Count", ascending=False),
                column_config={
                    "Phrase": st.column_config.TextColumn(
                        "Commonly used word or phrase",
                        width="large",
                    ),
                    "Count": st.column_config.NumberColumn(
                        "Occurrences",
                        help="Number of reports containing this phrase",
                        width="small",
                    ),
                    "Frequency %": st.column_config.ProgressColumn(
                        "Frequency",
                        help="Percentage of total reports this phrase appears in",
                        format="%d%%", # Displays as 0-100%
                        min_value=0,
                        max_value=100,
                        width="small",
                    ),
                },
                hide_index=True,
                width="stretch",
                height=600
            )
        else:
            st.warning("No common phrases were identified for this record.")

if __name__ == "__main__":
    main()