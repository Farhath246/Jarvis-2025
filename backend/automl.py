"""
automl.py — Lightweight automated machine learning using scikit-learn.
Trains a single Decision Tree model for classification or regression.
"""

import os
import json
import sqlite3
import logging
from backend.config import DB_PATH, AUTOML_MODELS_DIR, AUTOML_ENABLED
from backend.data_pipeline import load_and_clean_data

logger = logging.getLogger(__name__)

# Try importing joblib, fallback to pickle
try:
    import joblib
    _serializer = joblib
except ImportError:
    import pickle
    _serializer = pickle

# Lazy import scikit-learn to avoid import overhead when not used
_sklearn_available = None

def _check_sklearn():
    global _sklearn_available
    if _sklearn_available is not None:
        return _sklearn_available
        
    try:
        import sklearn
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            r2_score, mean_squared_error, mean_absolute_error
        )
        _sklearn_available = True
    except ImportError:
        _sklearn_available = False
        
    return _sklearn_available


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_trained_models() -> list[dict]:
    """Return all registered models from database."""
    if not AUTOML_ENABLED:
        logger.info("AutoML is disabled on this device. Enable it in config.py")
        return []
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, task_type, target_col, metrics, model_path, created_at FROM trained_models ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        models = []
        for r in rows:
            m = dict(r)
            try:
                m["metrics"] = json.loads(m["metrics"])
            except Exception:
                m["metrics"] = {}
            models.append(m)
        return models
    except Exception as e:
        logger.error("Error listing trained models: %s", e)
        return []


def delete_model(model_name: str) -> bool:
    """Delete a model file and its DB record."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT model_path FROM trained_models WHERE name = ?", (model_name,))
        row = cursor.fetchone()
        
        if row:
            model_path = row["model_path"]
            if os.path.exists(model_path):
                try:
                    os.remove(model_path)
                except Exception as fe:
                    logger.warning("Could not delete model file: %s", fe)
            
            cursor.execute("DELETE FROM trained_models WHERE name = ?", (model_name,))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    except Exception as e:
        logger.error("Error deleting model %s: %s", model_name, e)
        return False


def train_and_save_model(filepath: str, model_name: str, target_col: str) -> dict:
    """
    Automated training pipeline:
    1. Load and clean dataset.
    2. Auto-detect task type (classification/regression).
    3. Label-encode categorical features and targets.
    4. Fit a single Decision Tree (Classifier/Regressor).
    5. Evaluate on 20% test split.
    6. Serialize model artifacts and metadata to disk.
    7. Register details in SQLite table.
    """
    if not AUTOML_ENABLED:
        return {"success": False, "error": "AutoML is disabled on this device. Enable it in config.py"}
        
    if not _check_sklearn():
        return {
            "success": False,
            "error": "scikit-learn is not installed. Please install it using: pip install scikit-learn"
        }
        
    try:
        # Import required sklearn APIs
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            r2_score, mean_squared_error, mean_absolute_error
        )
        
        # Load dataset
        data = load_and_clean_data(filepath)
        if not data:
            return {"success": False, "error": "Dataset is empty."}
            
        columns = list(data[0].keys())
        if target_col not in columns:
            return {"success": False, "error": f"Target column '{target_col}' not found in dataset."}
            
        # ── Step 1: Detect Task Type ──────────────────────────────────────
        target_vals = [row[target_col] for row in data]
        unique_targets = set(target_vals)
        
        # If strings or few unique numerical values, classification
        is_numeric = all(isinstance(v, (int, float)) for v in unique_targets)
        if not is_numeric or len(unique_targets) <= 10:
            task_type = "classification"
        else:
            task_type = "regression"
            
        # ── Step 2: Extract Features & Encode Categoricals ─────────────────
        feature_cols = [col for col in columns if col != target_col]
        # Ignore columns that contain only unique values per row (like names/IDs)
        valid_feature_cols = []
        for col in feature_cols:
            col_vals = set(row[col] for row in data)
            if len(col_vals) > 1 and len(col_vals) < len(data):
                valid_feature_cols.append(col)
                
        if not valid_feature_cols:
            return {"success": False, "error": "No valid feature columns found for training."}
            
        # Build categorical maps
        cat_mappings = {}
        for col in valid_feature_cols + [target_col]:
            col_vals = [row[col] for row in data]
            non_numeric = any(not isinstance(v, (int, float)) for v in col_vals)
            if non_numeric:
                unique_sorted = sorted(list(set(str(v) for v in col_vals)))
                cat_mappings[col] = {val: idx for idx, val in enumerate(unique_sorted)}
                
        # Transform data to numeric matrix X and vector y
        X = []
        y = []
        
        for row in data:
            # Feature row
            x_row = []
            for col in valid_feature_cols:
                val = row[col]
                if col in cat_mappings:
                    x_row.append(cat_mappings[col].get(str(val), 0))
                else:
                    x_row.append(val if val is not None else 0.0)
            X.append(x_row)
            
            # Target value
            t_val = row[target_col]
            if target_col in cat_mappings:
                y.append(cat_mappings[target_col].get(str(t_val), 0))
            else:
                y.append(t_val if t_val is not None else 0.0)
                
        # ── Step 3: Split Data ─────────────────────────────────────────────
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # ── Step 4: Train Simple Decision Tree Model ───────────────────────
        if task_type == "classification":
            # Lightweight Decision Tree
            model = DecisionTreeClassifier(max_depth=5, random_state=42)
            model.fit(X_train, y_train)
            
            # Evaluate
            preds = model.predict(X_test)
            acc = accuracy_score(y_test, preds)
            prec = precision_score(y_test, preds, average='weighted', zero_division=0)
            rec = recall_score(y_test, preds, average='weighted', zero_division=0)
            f1 = f1_score(y_test, preds, average='weighted', zero_division=0)
            
            metrics = {
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4)
            }
        else:
            model = DecisionTreeRegressor(max_depth=5, random_state=42)
            model.fit(X_train, y_train)
            
            # Evaluate
            preds = model.predict(X_test)
            r2 = r2_score(y_test, preds)
            mse = mean_squared_error(y_test, preds)
            mae = mean_absolute_error(y_test, preds)
            
            metrics = {
                "r2": round(r2, 4),
                "mse": round(mse, 4),
                "mae": round(mae, 4)
            }
            
        # ── Step 5: Serialize Model & Metadata ─────────────────────────────
        if not os.path.exists(AUTOML_MODELS_DIR):
            os.makedirs(AUTOML_MODELS_DIR)
            
        model_filename = f"{model_name}.pkl"
        model_filepath = os.path.join(AUTOML_MODELS_DIR, model_filename)
        
        model_data = {
            "model": model,
            "task_type": task_type,
            "target_col": target_col,
            "features": valid_feature_cols,
            "mappings": cat_mappings,
            "metrics": metrics
        }
        
        with open(model_filepath, 'wb') as f:
            _serializer.dump(model_data, f)
            
        # ── Step 6: Register in Database ──────────────────────────────────
        conn = _get_conn()
        cursor = conn.cursor()
        
        # Insert or update
        cursor.execute("SELECT id FROM trained_models WHERE name = ?", (model_name,))
        existing = cursor.fetchone()
        
        metrics_json = json.dumps(metrics)
        
        if existing:
            cursor.execute(
                "UPDATE trained_models SET task_type = ?, target_col = ?, metrics = ?, model_path = ? WHERE name = ?",
                (task_type, target_col, metrics_json, model_filepath, model_name)
            )
        else:
            cursor.execute(
                "INSERT INTO trained_models (name, task_type, target_col, metrics, model_path) VALUES (?, ?, ?, ?, ?)",
                (model_name, task_type, target_col, metrics_json, model_filepath)
            )
            
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "model_name": model_name,
            "task_type": task_type,
            "metrics": metrics,
            "features": valid_feature_cols
        }
        
    except Exception as e:
        logger.error("Model training failed: %s", e)
        return {"success": False, "error": str(e)}


def predict_with_model(model_name: str, features: dict) -> dict:
    """
    Load saved model metadata, process inputs, and predict.
    """
    if not AUTOML_ENABLED:
        return {"success": False, "error": "AutoML is disabled on this device. Enable it in config.py"}
        
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT model_path FROM trained_models WHERE name = ?", (model_name,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"success": False, "error": f"Model '{model_name}' is not registered."}
            
        model_path = row["model_path"]
        if not os.path.exists(model_path):
            return {"success": False, "error": f"Model file not found at {model_path}."}
            
        # Load model data
        with open(model_path, 'rb') as f:
            model_data = _serializer.load(f)
            
        model = model_data["model"]
        task_type = model_data["task_type"]
        expected_features = model_data["features"]
        mappings = model_data["mappings"]
        
        # Build numerical feature list in the exact trained order
        x_input = []
        for col in expected_features:
            val = features.get(col)
            
            # Categorical encoding
            if col in mappings:
                encoded_val = mappings[col].get(str(val), 0)
                x_input.append(encoded_val)
            else:
                try:
                    # Convert to float/int
                    x_input.append(float(val) if val is not None else 0.0)
                except (ValueError, TypeError):
                    x_input.append(0.0)
                    
        # Model prediction
        pred_val = model.predict([x_input])[0]
        
        # Convert classification prediction back to string label if map exists
        prediction = pred_val
        probability = None
        
        if task_type == "classification":
            target_col = model_data.get("target_col")
            if target_col and target_col in mappings:
                # Invert mapping
                inv_map = {idx: val for val, idx in mappings[target_col].items()}
                prediction = inv_map.get(int(pred_val), pred_val)
                
            # Try getting classification probability
            if hasattr(model, "predict_proba"):
                prob_vals = model.predict_proba([x_input])[0]
                probability = round(float(max(prob_vals)), 4)
                
        return {
            "success": True,
            "prediction": prediction,
            "probability": probability,
            "task_type": task_type
        }
        
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        return {"success": False, "error": str(e)}
