# MAUDE Data Extractor

This Python project fetches medical device adverse event reports from the FDA MAUDE database by device model, processes the data, and exports results to JSON, CSV, and Excel file types.  

---

## Setup

1. **Create a virtual environment**  

```
python -m venv venv
```


2. **Activate the virtual environment**  

- **Windows:**  

```
venv\Scripts\activate
```

- **macOS / Linux:**  

```
source venv/bin/activate
```


3. **Install dependencies**  

```
pip install -r requirements.txt
```


4. **Environment variables (optional)**  
If you have an FDA API key, you can create a `.env` file in the project root to increase the number of daily API calls you can make:  

```
FDA_API_KEY=your_api_key_here
```


---

## Use

You can run the fetcher via the Streamlit Web Interface (recommended) or the Command Line Script.

**Streamlit Web Interface (recomended)**  
Run the following command to launch the browser-based UI:

```
streamlit run app.py
```

**Command Line**  
Run the retrieve script directly to fetch, process, and export MAUDE events via terminal prompts:

```
python retrieve.py
```

Run the analyze script directly to create summary files for all data json files:

```
python analyze.py
```

---

## Features & Options
Whether using the UI or the script, you will have the following options:

**Enter Model Number(s):** e.g. `HAR1136, TB-0009OFX`

**Enter Year(s) to Retrieve Reports From:** e.g. `2024, 2025`

Leave blank to retrieve all available years.

**Deduplication Options:**

Label possible duplicate groups - Identifies reports likely referencing the same event.

Merge duplicate groups - Combines identified duplicates into a single comprehensive entry.

**Export Data as Files:** Results are automatically organized into specific folders:

data_json/

data_csv/

data_excel/

---

## Duplicate Training

The script uses the `dedupe` library to identify possible duplicate reports (reports that all reference the same event).

Note that these are simply informed guesses based on training data, and results should be double checked.

Events identified as likely duplicates will share a `Possible Duplicate Group` number with each other.
 
- Training results are saved to:

  - `maude_dedupe_settings` → Stores the trained dedupe model  
  - `maude_dedupe_training.json` → Stores labeled training examples  

**To retrain the dedupe model**

- Delete both `maude_dedupe_settings` and `maude_dedupe_training.json` before rerunning the script  
- Run the program like usual, make sure to choose to `mark duplicate groups`  
- The dataset used for training will use the records you pulled in this run. When training the dedupe model, it is recomended to use as broad of a dataset as possible  
- In the command line, the program will take some time to prepare the data and then will prompt you with two records from the data at a time, asking if they are duplicate records of the same event  
- You may continue marking records until you believe you have created sufficient training data  
- Once you mark the training as finished, new `maude_dedupe_settings` and `maude_dedupe_training.json` files will be created  
Note: You may modify the `SHORT_DESCRIPTION_LENGTH` and `TRAINING_SAMPLE_SIZE` constants to change the max amount of sample data used when training  

---

## Configurable Constants

These values are defined in `retrieve.py` and can be adjusted to change the behavior of the data processing and storage:

| Constant | Description | Default |
|----------|------------|---------|
| `BATCH_SIZE` | Number of entries to retrieve per API call (max 1000) | 999 |
| `SHORT_DESCRIPTION_LENGTH` | Max characters of description to use for duplicate detection | 1000 |
| `TRAINING_SAMPLE_SIZE` | Number of entries used to train the dedupe model | 1000 |
| `EVENT_SEVERITY` |	Priority mapping used when merging duplicates (keeps the most severe type) | Death > Injury > Malfunction > Other
| `EMPTY_FIELD` |	The placeholder string used for missing data in reports |	"N/A"
| `LIST_STR` | String to put between values in lists | "; "
| `JSON_FOLDER` |	Directory where JSON exports are saved | "data_json"
| `CSV_FOLDER` |	Directory where CSV exports are saved | "data_csv"
| `EXCEL_FOLDER` |	Directory where Excel exports are saved | "data_excel"

These values are defined in `analyze.py` and can be adjusted to change the behavior of the data processing and storage:

| Constant | Description | Default |
|----------|------------|---------|
| `FILENAME_END_TEXT` | Added to the filename of all files generated with with analyze.py | "_summary" |
| `JSON_ANALYSIS_FOLDER` | Directory where JSON summaries are saved | "analysis_json" |
| `XLSX_ANALYSIS_FOLDER` | Directory where Excel summaries are saved | "analysis_txt" |