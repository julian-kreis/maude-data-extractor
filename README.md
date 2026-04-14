# MAUDE Data Extractor

This Python project fetches medical device adverse event reports from the FDA MAUDE database by device model, processes the data, and exports the processed data to JSON, CSV, and Excel file types. Additionally, summaries of data are generated in JSON and Excel file types and can be viewed graphically through the UI.

---

# For Non-Developers

- Go to the latest release at https://github.com/julian-kreis/maude-data-extractor/releases and download the zip file corresponding to your OS

- Unzip the folder 

- Double click the application file in the folder to run the program

---

# For Developers

## Setup

**Requirements:**

- Python 3.11 or newer

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

You can run the program via the Streamlit Web Interface (recommended) or the Command Line Script.

**Streamlit Web Interface (recomended)**  
Run the following command to launch the browser-based UI:

```
streamlit run app.py
```

If you get missing module errors, you may run this instead:

```
python -m streamlit run app.py
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
Whether using the UI or the script to retrieve data, you will have the following options:

**Enter Model Number(s):**

- Uses a comma-seprated list (e.g. `HAR1136, TB-0009OFX`)

**Enter Year(s) to Retrieve Reports From:**

- Uses a comma-seperated list (e.g. `2024, 2025`)

- Leave blank to retrieve all available years.

**Deduplication Options:**

- Label possible duplicate groups - Identifies reports likely referencing the same event.

- Merge duplicate groups - Combines identified duplicates into a single comprehensive entry.

**Save Data as Files:**

- Raw data files stored as .json, .csv, .xlsx

---

Whether using the UI or script to produce data summaries, you will get the following information:

- Number of events by event type and device model

- Number of different product problems by device model

- Number of different patient problems by device model

- Most common words and phrases in event descriptions

If a shorter phrase appears in a longer phrase in most occurences (threshold can be set as a Constant), it is removed from the list

- Data summary files stored as .json, .xlsx

Using the UI gives you access to additional data visualizations and comparisons of summary data

---

## Creating a New Executable File

If you are looking for an executable file to run the program, check the releases tab for the project in GitHub.  

If you are looking to create a new executable file:  

**Windows**  

Run `build.bat`

**macOS / Linux**

Run `build.sh`

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

These values are defined in `retrieve.py` and can be adjusted to change the behavior of the program:

| Constant | Description | Default |
|----------|------------|---------|
| `BATCH_SIZE` | Number of entries to retrieve per API call (max 1000) | 999 |
| `SHORT_DESCRIPTION_LENGTH` | Max characters of description to use for duplicate detection | 1000 |
| `TRAINING_SAMPLE_SIZE` | Number of entries used to train the dedupe model | 1000 |
| `EVENT_SEVERITY` |	Priority mapping used when merging duplicates (keeps the most severe type) | Death > Injury > Malfunction > Other
| `EMPTY_FIELD` |	The placeholder string used for missing data in reports |	"N/A"
| `LIST_STR` | String to put between values in lists | "; "
| `JSON_FOLDER` |	Directory where JSON exports are saved (must be changed manually in .gitignore and build_exe files) | "data_json"
| `CSV_FOLDER` |	Directory where CSV exports are saved (must be changed manually in .gitignore and build_exe files) | "data_csv"
| `EXCEL_FOLDER` |	Directory where Excel exports are saved (must be changed manually in .gitignore and build_exe files) | "data_excel"

These values are defined in `analyze.py` and can be adjusted to change the behavior of the program:

| Constant | Description | Default |
|----------|------------|---------|
| `FILENAME_END_TEXT` | Added to the filename of all files generated with with analyze.py | "_summary" |
| `MIN_PHRASE_WORDCOUNT` | Min wordcount of commom phrases to look for | 1 |
| `MAX_PHRASE_WORDCOUNT` | Max wordcount of common phrases to look for | 12 |
| `IGNORED_WORDS` | Medical report boilerplate words to remove when looking for common phrases | "reported","event","procedure","provided","use","duplicate","report","medical","customer","received","associated","consequence","consequences","resulted","information","using","during","surgery","unknown","patient","complete","completed","observed","additional","another","adverse" |
| `JSON_ANALYSIS_FOLDER` | Directory where JSON summaries are saved (must be changed manually in .gitignore and build_exe files) | "analysis_json" |
| `XLSX_ANALYSIS_FOLDER` | Directory where Excel summaries are saved (must be changed manually in .gitignore and build_exe files) | "analysis_excel" |

These values are defined in `analysis.py` and can be adjusted to change the behavior of the program:

| Constant | Description | Default |
|----------|------------|---------|
| `OTHER_LABEL_MAX_CHARS` | In charts, the "Other" label gets truncated to this length | 50 |

These values are defined in `comparison.py` and can be adjusted to change the behavior of the program:

| Constant | Description | Default |
|----------|------------|---------|
| `MAX_COLS` | Maximum number of records shown per row at the top of the comparison page | 4 |