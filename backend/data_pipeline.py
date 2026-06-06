"""
data_pipeline.py — Ingestion, cleaning, and summary statistics.
Uses pure Python standard library to ensure zero system overhead.
"""

import csv
import json
import os
import math
import logging

logger = logging.getLogger(__name__)


def load_and_clean_data(filepath: str) -> list[dict]:
    """
    Ingest a CSV or JSON file, clean string fields, convert numeric values,
    and impute missing values using pure Python standard library.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    _, ext = os.path.splitext(filepath.lower())
    raw_rows = []
    
    if ext == '.csv':
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                # Normalize column names: strip spaces
                reader.fieldnames = [name.strip() for name in (reader.fieldnames or [])]
                for row in reader:
                    cleaned_row = {k.strip(): (v.strip() if v is not None else "") for k, v in row.items() if k is not None}
                    raw_rows.append(cleaned_row)
        except Exception as e:
            logger.error("Error reading CSV file %s: %s", filepath, e)
            raise ValueError(f"Failed to parse CSV file: {e}")
            
    elif ext == '.json':
        try:
            with open(filepath, mode='r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    raw_rows = data
                elif isinstance(data, dict):
                    # If columnar JSON (dict of lists)
                    keys = list(data.keys())
                    if keys and isinstance(data[keys[0]], list):
                        length = len(data[keys[0]])
                        for i in range(length):
                            row = {k: data[k][i] for k in keys}
                            raw_rows.append(row)
                    else:
                        raw_rows = [data]
                else:
                    raise ValueError("Unsupported JSON layout.")
        except Exception as e:
            logger.error("Error reading JSON file %s: %s", filepath, e)
            raise ValueError(f"Failed to parse JSON file: {e}")
    else:
        raise ValueError(f"Unsupported format: {ext}. Only CSV and JSON are supported.")
        
    if not raw_rows:
        return []
        
    # Convert string numbers to float/int where applicable
    converted_rows = []
    for row in raw_rows:
        conv_row = {}
        for k, v in row.items():
            if v == "" or v is None:
                conv_row[k] = None
            else:
                try:
                    if '.' in str(v):
                        conv_row[k] = float(v)
                    else:
                        conv_row[k] = int(v)
                except ValueError:
                    conv_row[k] = str(v).strip()
        converted_rows.append(conv_row)
        
    # Missing value imputation
    columns = list(converted_rows[0].keys())
    imputation_values = {}
    
    for col in columns:
        vals = [row[col] for row in converted_rows if row[col] is not None]
        if not vals:
            imputation_values[col] = ""
            continue
            
        numeric_vals = [v for v in vals if isinstance(v, (int, float))]
        if len(numeric_vals) > 0:
            # Impute with median
            sorted_vals = sorted(numeric_vals)
            n = len(sorted_vals)
            if n % 2 == 1:
                median = sorted_vals[n // 2]
            else:
                median = (sorted_vals[(n // 2) - 1] + sorted_vals[n // 2]) / 2.0
            imputation_values[col] = median
        else:
            # Impute with mode
            freqs = {}
            for v in vals:
                freqs[v] = freqs.get(v, 0) + 1
            mode = max(freqs, key=freqs.get)
            imputation_values[col] = mode
            
    # Impute missing cells
    cleaned_rows = []
    for row in converted_rows:
        new_row = {}
        for col in columns:
            if row[col] is None:
                new_row[col] = imputation_values[col]
            else:
                new_row[col] = row[col]
        cleaned_rows.append(new_row)
        
    return cleaned_rows


def get_summary_statistics(data: list[dict]) -> dict:
    """
    Calculate summary statistics for numeric and categorical columns.
    """
    if not data:
        return {}
        
    columns = list(data[0].keys())
    stats = {}
    
    for col in columns:
        vals = [row[col] for row in data]
        numeric_vals = [v for v in vals if isinstance(v, (int, float))]
        
        if len(numeric_vals) == len(vals) and len(vals) > 0:
            count = len(numeric_vals)
            mean = sum(numeric_vals) / count
            sorted_vals = sorted(numeric_vals)
            
            if count % 2 == 1:
                median = sorted_vals[count // 2]
            else:
                median = (sorted_vals[(count // 2) - 1] + sorted_vals[count // 2]) / 2.0
                
            minimum = sorted_vals[0]
            maximum = sorted_vals[-1]
            
            variance = sum((x - mean) ** 2 for x in numeric_vals) / max(1, count - 1)
            std_dev = math.sqrt(variance)
            
            stats[col] = {
                "type": "numeric",
                "count": count,
                "mean": round(mean, 3),
                "median": round(median, 3),
                "min": round(minimum, 3),
                "max": round(maximum, 3),
                "std": round(std_dev, 3)
            }
        else:
            count = len(vals)
            freqs = {}
            for v in vals:
                k = str(v)
                freqs[k] = freqs.get(k, 0) + 1
                
            unique_count = len(freqs)
            top_val = max(freqs, key=freqs.get)
            top_freq = freqs[top_val]
            
            stats[col] = {
                "type": "categorical",
                "count": count,
                "unique": unique_count,
                "top": top_val,
                "freq": top_freq,
                "frequencies": freqs
            }
            
    return stats


def detect_schema(data: list[dict]) -> dict:
    """
    Detect column schemas (numeric vs categorical).
    """
    stats = get_summary_statistics(data)
    schema = {}
    
    for col, info in stats.items():
        col_type = info["type"]
        if col_type == "numeric":
            # Treat numeric columns with <= 10 unique values as classification
            unique_vals = set(row[col] for row in data)
            if len(unique_vals) <= 10:
                schema[col] = "categorical"
            else:
                schema[col] = "numeric"
        else:
            schema[col] = "categorical"
            
    return schema
