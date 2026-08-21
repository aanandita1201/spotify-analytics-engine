import json
from pathlib import Path


RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def load_streaming_history():
    records = []

    for file_path in RAW_DATA_DIR.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            records.extend(data)

    return records