import os
import csv

def summarize_csv_exports():
    """Prints event totals for each CSV file in csv_exports folder."""
    export_dir = "csv_exports"

    if not os.path.exists(export_dir):
        print("csv_exports folder not found.")
        return

    csv_files = [f for f in os.listdir(export_dir) if f.lower().endswith(".csv")]

    if not csv_files:
        print("No CSV files found.")
        return

    for file in sorted(csv_files):
        filepath = os.path.join(export_dir, file)

        total_incidents = 0
        total_malfunction = 0
        total_injury = 0
        total_death = 0
        total_other = 0

        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                total_incidents += 1
                event = (row.get("Type of Event") or "").strip().lower()

                if event == "malfunction":
                    total_malfunction += 1
                elif event == "injury":
                    total_injury += 1
                elif event == "death":
                    total_death += 1
                else:
                    total_other += 1

        print(f"\n{file}")
        print(f"  total_incidents : {total_incidents}")
        print(f"  total_malfunction: {total_malfunction}")
        print(f"  total_injury    : {total_injury}")
        print(f"  total_death     : {total_death}")
        print(f"  total_other     : {total_other}")

if __name__ == "__main__":
    summarize_csv_exports()