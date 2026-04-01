import streamlit as st
import pandas as pd
import plotly.express as px
from pages.analysis import (
    JSON_DIR,
    FILENAME_END_TEXT,
    load_json_data,
    plot_pie_charts_for_models,
    format_date
)

def main():
    st.sidebar.title("Comparison Selection")
    
    if not JSON_DIR.exists():
        st.error(f"Directory {JSON_DIR} not found.")
        return

    # Show user clean file list names visually
    suffix = f"{FILENAME_END_TEXT}.json"
    files = list(JSON_DIR.glob("*.json"))

    # Use multiselect to allow adding/removing multiple records
    selected_files = st.sidebar.multiselect(
        "Choose Records to Compare",
        options=files,
        format_func=lambda x: x.name.removesuffix(suffix)
    )

    if not selected_files:
        st.info("Please select at least one record from the sidebar to begin comparison.")
        return

    # --- Load Data ---
    records_data = {}
    record_names = []
    
    for f in selected_files:
        clean_name = f.name.removesuffix(suffix)
        records_data[clean_name] = load_json_data(f)
        record_names.append(clean_name)

    st.title("Device Incident Comparison Dashboard")
    
    # --- Top Section: List of Records ---
    st.subheader("Selected Records Overview")
    
    # Create columns dynamically based on how many records are selected for a clean top view
    overview_cols = st.columns(len(record_names))
    
    for i, name in enumerate(record_names):
        with overview_cols[i]:
            data = records_data[name]
            models = data.get("list of models", [])
            start_date = format_date(data.get("earliest incident date", "N/A"))
            end_date = format_date(data.get("latest incident date", "N/A"))
            
            st.markdown(f"#### {name}")
            st.markdown(f"**Models:** {', '.join(models) if models else 'None'}")
            st.markdown(f"**Date Range:** {start_date} to {end_date}")

    st.divider()

    # --- Data Restructuring ---
    # We rebuild the dictionaries so that the inner keys are 'record names' instead of 'model names'.
    # This allows us to perfectly reuse `plot_pie_charts_for_models` from analysis.py.
    
    combined_events = {}
    combined_prod = {}
    combined_pat = {}
    record_totals = {}

    for name in record_names:
        data = records_data[name]
        
        # 1. Total Incidents
        events_data = data.get("type of event", {})
        # Sum up all totals for event categories to get the grand total for the record
        total_incidents = sum([events_data[k].get("total", 0) for k in events_data.keys() if k != "total"])
        record_totals[name] = total_incidents
        
        # 2. Event Types
        for cat, counts in events_data.items():
            if cat == "total": continue
            if cat not in combined_events: combined_events[cat] = {}
            combined_events[cat][name] = counts.get("total", 0)
            
        # 3. Product Problems
        prod_probs = data.get("Product problems", {})
        for cat, counts in prod_probs.items():
            if cat == "total": continue
            if cat not in combined_prod: combined_prod[cat] = {}
            combined_prod[cat][name] = counts.get("total", 0)
            
        # 4. Patient Problems
        pat_probs = data.get("Patient problems", {})
        for cat, counts in pat_probs.items():
            if cat == "total": continue
            if cat not in combined_pat: combined_pat[cat] = {}
            combined_pat[cat][name] = counts.get("total", 0)

    # --- Bar Chart: Total Incidents by Record ---
    st.subheader("Total Incidents per Record")
    df_totals = pd.DataFrame(list(record_totals.items()), columns=["Record", "Total Incidents"])
    fig_totals = px.bar(
        df_totals, 
        x="Record", 
        y="Total Incidents", 
        color="Record", 
        text_auto=True
    )
    st.plotly_chart(fig_totals, width='stretch')
    
    st.divider()

    # --- Pie Charts: Incident Types by Record ---
    st.subheader("Incident Types by Record")
    plot_pie_charts_for_models(combined_events, record_names, "Event Types")
    
    st.divider()
    
    # --- Pie Charts: Product Problems by Record ---
    st.subheader("Product Problems by Record")
    st.text("Note that some incident reports may list multiple product problems, which are all counted here")
    plot_pie_charts_for_models(combined_prod, record_names, "Product Problems")
    
    st.divider()
    
    # --- Pie Charts: Patient Problems by Record ---
    st.subheader("Patient Problems by Record")
    st.text("Note that some incident reports may list multiple patient problems, which are all counted here")
    plot_pie_charts_for_models(combined_pat, record_names, "Patient Problems")

if __name__ == "__main__":
    main()