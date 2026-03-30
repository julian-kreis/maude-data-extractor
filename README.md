# MAUDE Adverse Event Fetcher

This Python project fetches medical device adverse event reports from the FDA MAUDE database by device model, processes the data, and exports results to JSON, CSV, and Excel file types.

streamlit run app.py

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
If you have an FDA API key, create a `.env` file in the project root to increase the number of daily API calls you can make:

```
FDA_API_KEY=your_api_key_here
```


---

## Use

Run the retrieve script to fetch, process, and export MAUDE events:


```
python retrieve.py
```


You will be prompted to:

1. **Enter Model Number(s):**  
Example: `HAR1136, TB-0009OFX`

2. **Enter Years to Retrieve Reports From:**  
Example: `2024, 2025`  
Leave blank to retrieve all available years

3. **Deduplication Options**  
You can choose if you want to label possible duplicate groups   
Then you can choose if you want to merge duplicate groups into one entry

4. **Export Options:**  
You can choose to export results to JSON, CSV and/or Excel.
You can choose the filename of your exports

---

## Duplicate Training

The script uses the `dedupe` library to identify possible duplicate reports (reports that all reference the same event).

Note that these are simply informed guesses based on training data, and results should be double checked.

Events identified as likely duplicates will share a `Possible Duplicate Group` number with each other.
 
- Training results are saved to:

  - `maude_dedupe_settings` → Stores the trained dedupe model  
  - `maude_dedupe_training.json` → Stores labeled training examples  

**Notes:**

- `SHORT_DESCRIPTION_LENGTH` controls how many characters of the event description are used for duplicate detection. Higher values increase accuracy but may slow processing.
- `TRAINING_SAMPLE_SIZE` controls the number of records used for training.
- **To retrain the dedupe model**, delete both `maude_dedupe_settings` and `maude_dedupe_training.json` before rerunning the script. When training the dedupe model, it is recomended to use as broad of a dataset as possible.  

---

## Configurable Constants

| Constant | Description | Default |
|----------|------------|---------|
| `BATCH_SIZE` | Number of entries to retrieve per API call (max 1000) | 999 |
| `SHORT_DESCRIPTION_LENGTH` | Max characters of description to use for duplicate detection | 1000 |
| `TRAINING_SAMPLE_SIZE` | Number of entries used to train the dedupe model | 1000 |

---

### Example Workflow

1. Activate the environment:  

```
venv\Scripts\activate
```


2. Run the script:  

```
python retrieve.py
```


3. Enter the model numbers and years.

4. Choose whether or not to label possible events, and whether or not to merge them

5. Export results to JSON/CSV/Excel.
