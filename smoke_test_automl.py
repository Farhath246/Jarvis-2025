"""
smoke_test_automl.py — Automated verification script for Jarvis Phase 4 Data Pipeline & AutoML.
Generates mock cricket data, cleans/analyzes it, trains/evaluates Decision Tree models, and runs predictions.
"""

import sys
sys.path.insert(0, ".")

import os
import csv
import random
import sqlite3
import shutil
from backend.config import DB_PATH, AUTOML_MODELS_DIR
from backend.data_pipeline import load_and_clean_data, get_summary_statistics, detect_schema
from backend.automl import train_and_save_model, predict_with_model, list_trained_models, delete_model

MOCK_CSV = "mock_cricket_bowling.csv"

def generate_mock_dataset():
    """Generate a mock cricket bowling dataset with numeric and categorical attributes."""
    random.seed(42)
    variations = ["leg_spin", "googly", "flipper", "top_spin"]
    pitches = ["dry", "dusty", "wet"]
    outcomes = ["wicket", "dot", "run", "boundary"]
    
    headers = ["spin_rate", "speed", "accuracy", "turn_deg", "variation", "pitch_condition", "success_rate", "outcome"]
    
    with open(MOCK_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for _ in range(100):
            spin = random.randint(1200, 2200)
            speed = random.randint(65, 85)
            acc = random.randint(60, 95)
            turn = round(random.uniform(1.5, 6.0), 2)
            var = random.choice(variations)
            pitch = random.choice(pitches)
            
            # success rate depends slightly on inputs
            success = round(0.1 + (spin / 5000.0) + (acc / 200.0) - (speed / 300.0) + random.uniform(-0.1, 0.1), 3)
            success = max(0.01, min(0.99, success))
            
            # outcome depends on success rate
            if success > 0.7:
                out = "wicket"
            elif success > 0.4:
                out = "dot"
            elif success > 0.2:
                out = "run"
            else:
                out = "boundary"
                
            writer.writerow([spin, speed, acc, turn, var, pitch, success, out])


def cleanup_test_artifacts():
    """Remove generated test files, models, and DB records."""
    if os.path.exists(MOCK_CSV):
        os.remove(MOCK_CSV)
        
    # Delete test models from AutoML models dir
    for model_name in ["test_class_model", "test_reg_model"]:
        delete_model(model_name)
        pkl_path = os.path.join(AUTOML_MODELS_DIR, f"{model_name}.pkl")
        if os.path.exists(pkl_path):
            os.remove(pkl_path)


def main():
    print("=" * 60)
    print("JARVIS AUTOML & DATA PIPELINE — SMOKE TEST")
    print("=" * 60)
    
    # Clean up previous runs
    cleanup_test_artifacts()
    
    # Generate mock data
    generate_mock_dataset()
    print(f"Generated mock dataset: {MOCK_CSV}")
    
    try:
        # ── Test 1: Ingest and clean ──────────────────────────────────────
        print("\n[TEST 1] Testing Data Ingestion & Imputation...")
        data = load_and_clean_data(MOCK_CSV)
        print(f"  Successfully loaded {len(data)} rows.")
        assert len(data) == 100, f"FAILED: Expected 100 rows, got {len(data)}"
        
        # Test cleaning/type conversions
        first_row = data[0]
        assert isinstance(first_row["spin_rate"], int), "FAILED: spin_rate should be integer"
        assert isinstance(first_row["turn_deg"], float), "FAILED: turn_deg should be float"
        assert isinstance(first_row["variation"], str), "FAILED: variation should be string"
        print("  PASSED ✅")
        
        # ── Test 2: Calculate stats & schema ──────────────────────────────
        print("\n[TEST 2] Testing Summary Statistics...")
        stats = get_summary_statistics(data)
        schema = detect_schema(data)
        
        print(f"  Total columns detected: {len(stats)}")
        assert "speed" in stats, "FAILED: 'speed' column not in stats"
        assert stats["speed"]["type"] == "numeric", "FAILED: 'speed' should be numeric"
        assert stats["variation"]["type"] == "categorical", "FAILED: 'variation' should be categorical"
        
        print(f"  Detected schemas: {schema}")
        assert schema["speed"] == "numeric", "FAILED: schema speed should be numeric"
        assert schema["variation"] == "categorical", "FAILED: schema variation should be categorical"
        print("  PASSED ✅")
        
        # Check scikit-learn availability
        from backend.automl import _check_sklearn
        if not _check_sklearn():
            print("\n⚠️ scikit-learn is not installed in the current environment!")
            print("Skipping ML model training and prediction tests.")
            print("Please run: pip install scikit-learn joblib")
            return
            
        # ── Test 3: Train Classification Model ─────────────────────────────
        print("\n[TEST 3] Training Classification Model...")
        import backend.automl
        backend.automl.AUTOML_ENABLED = True
        res_class = train_and_save_model(MOCK_CSV, "test_class_model", "outcome")
        print(f"  Classification training result: {res_class}")
        assert res_class["success"], f"FAILED: Classification training failed: {res_class.get('error')}"
        assert res_class["task_type"] == "classification", "FAILED: Task type should be classification"
        assert "accuracy" in res_class["metrics"], "FAILED: Accuracy metric missing"
        print("  PASSED ✅")
        
        # ── Test 4: Train Regression Model ───────────────────────────────
        print("\n[TEST 4] Training Regression Model...")
        res_reg = train_and_save_model(MOCK_CSV, "test_reg_model", "success_rate")
        print(f"  Regression training result: {res_reg}")
        assert res_reg["success"], f"FAILED: Regression training failed: {res_reg.get('error')}"
        assert res_reg["task_type"] == "regression", "FAILED: Task type should be regression"
        assert "r2" in res_reg["metrics"], "FAILED: R2 metric missing"
        print("  PASSED ✅")
        
        # ── Test 5: Model Predictions ─────────────────────────────────────
        print("\n[TEST 5] Testing Predictions...")
        test_features = {
            "spin_rate": 1800,
            "speed": 74,
            "accuracy": 85,
            "turn_deg": 3.5,
            "variation": "leg_spin",
            "pitch_condition": "dry"
        }
        
        pred_class = predict_with_model("test_class_model", test_features)
        print(f"  Classification prediction: {pred_class}")
        assert pred_class["success"], f"FAILED: Class prediction failed: {pred_class.get('error')}"
        assert pred_class["prediction"] in ["wicket", "dot", "run", "boundary"], "FAILED: Invalid outcome class"
        
        pred_reg = predict_with_model("test_reg_model", test_features)
        print(f"  Regression prediction: {pred_reg}")
        assert pred_reg["success"], f"FAILED: Reg prediction failed: {pred_reg.get('error')}"
        assert isinstance(pred_reg["prediction"], float), "FAILED: Reg prediction should be float"
        print("  PASSED ✅")
        
        # ── Test 6: Listing Models ────────────────────────────────────────
        print("\n[TEST 6] Listing Trained Models...")
        models = list_trained_models()
        model_names = [m["name"] for m in models]
        print(f"  Registered models: {model_names}")
        assert "test_class_model" in model_names, "FAILED: test_class_model not registered"
        assert "test_reg_model" in model_names, "FAILED: test_reg_model not registered"
        print("  PASSED ✅")
        
    finally:
        # Clean up
        print("\nCleaning up test files and DB models...")
        cleanup_test_artifacts()
        print("Cleanup complete.")
        
    print("\n" + "=" * 60)
    print("ALL AUTOML & DATA PIPELINE TESTS PASSED! ✅ Module is fully verified.")
    print("=" * 60)

if __name__ == "__main__":
    main()
