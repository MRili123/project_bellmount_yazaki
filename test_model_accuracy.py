#!/usr/bin/env python3
"""
Test the CNN model accuracy on the dataset
"""

import json
import numpy as np
from pathlib import Path
from PIL import Image
import os
import sys

# Add model module to path
sys.path.insert(0, str(Path(__file__).parent / "model_bellmounth_mesure"))
from utils import apply_threshold

# TensorFlow
try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model
except ImportError:
    print("❌ TensorFlow not installed. Installing...")
    os.system("pip install -q tensorflow")
    import tensorflow as tf
    from tensorflow.keras.models import load_model

MODELS_ROOT = Path(__file__).parent / "models"
MODELS_MESURE_DIR = MODELS_ROOT / "mesure"
MODEL_PATH = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MODEL_V1.h5"
DATASET_DIR = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"

def load_annotations():
    """Load annotations from JSON"""
    if not ANNOTATIONS_FILE.exists():
        print(f"❌ Annotations file not found: {ANNOTATIONS_FILE}")
        return []
    return json.loads(ANNOTATIONS_FILE.read_text())

def preprocess_image(image_path):
    """Load and preprocess image like during training"""
    try:
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32) / 255.0

        # Apply threshold as in training
        thresh = apply_threshold(img_array)

        # Normalize to 0-1
        thresh = thresh.astype(np.float32) / 255.0

        return np.expand_dims(thresh, axis=-1)
    except Exception as e:
        print(f"Error loading {image_path}: {e}")
        return None

def normalize_points(points, width, height):
    """Normalize points to 0-1 range"""
    return np.array([
        points[0][0] / width,
        points[0][1] / height,
        points[1][0] / width,
        points[1][1] / height
    ], dtype=np.float32)

def denormalize_points(pred_norm, width, height):
    """Convert normalized predictions back to pixel coordinates"""
    return np.array([
        pred_norm[0] * width,
        pred_norm[1] * height,
        pred_norm[2] * width,
        pred_norm[3] * height
    ])

def pixel_distance(p1, p2):
    """Calculate Euclidean distance between two points"""
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def test_model():
    """Test model on entire dataset"""
    print("\n" + "="*60)
    print("🧪 MODEL ACCURACY TEST")
    print("="*60)

    # Load model
    if not MODEL_PATH.exists():
        print(f"❌ Model not found: {MODEL_PATH}")
        return None

    print(f"\n📥 Loading model from: {MODEL_PATH}")
    model = load_model(str(MODEL_PATH))

    # Load annotations
    annotations = load_annotations()
    if not annotations:
        print("❌ No annotations found")
        return None

    print(f"📊 Total annotations: {len(annotations)}")

    # Prepare data
    X = []
    y = []
    valid_indices = []

    print("\n⏳ Preprocessing images...")
    for idx, ann in enumerate(annotations):
        if idx % 50 == 0:
            print(f"  {idx}/{len(annotations)}", end='\r')

        orig_path = Path(ann.get('original_path', ''))
        if not orig_path.exists():
            # Try alternative path
            orig_path = DATASET_DIR / "original" / ann.get('filename', '')

        if not orig_path.exists():
            continue

        img = preprocess_image(orig_path)
        if img is None:
            continue

        points = ann.get('points', [])
        if len(points) < 2:
            continue

        width = ann.get('width', 640)
        height = ann.get('height', 480)

        # Get points in order
        p1 = [points[0].get('x', 0), points[0].get('y', 0)]
        p2 = [points[1].get('x', 0), points[1].get('y', 0)]

        y_norm = normalize_points([p1, p2], width, height)

        X.append(img)
        y.append(y_norm)
        valid_indices.append(idx)

    print(f"\n✓ Loaded {len(X)} valid training samples")

    X = np.array(X)
    y = np.array(y)

    # Split into train/test
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"  Train samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")

    # Evaluate
    print("\n⏳ Evaluating model...")
    test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)

    # Get predictions for accuracy calculation
    print("⏳ Making predictions...")
    predictions = model.predict(X_test, verbose=0)

    # Calculate accuracies
    widths = [640] * len(X_test)
    heights = [480] * len(X_test)

    acc_10px = 0
    acc_20px = 0
    pixel_errors = []

    for i in range(len(X_test)):
        pred_denorm = denormalize_points(predictions[i], widths[i], heights[i])
        true_denorm = denormalize_points(y_test[i], widths[i], heights[i])

        # Calculate distance error for each point
        p1_error = pixel_distance(pred_denorm[:2], true_denorm[:2])
        p2_error = pixel_distance(pred_denorm[2:], true_denorm[2:])
        mean_error = (p1_error + p2_error) / 2

        pixel_errors.append(mean_error)

        if mean_error <= 10:
            acc_10px += 1
        if mean_error <= 20:
            acc_20px += 1

    acc_10px = (acc_10px / len(X_test)) * 100
    acc_20px = (acc_20px / len(X_test)) * 100
    mean_pixel_error = np.mean(pixel_errors)

    # Display results
    print("\n" + "="*60)
    print("📊 TEST RESULTS")
    print("="*60)
    print(f"\n✓ Accuracy (within ±10px): {acc_10px:.2f}%")
    print(f"✓ Accuracy (within ±20px): {acc_20px:.2f}%")
    print(f"\n• Test Loss (MSE): {test_loss:.6f}")
    print(f"• Test MAE: {test_mae:.6f} px")
    print(f"• Mean Pixel Error: {mean_pixel_error:.4f} px")
    print(f"• Min Error: {np.min(pixel_errors):.4f} px")
    print(f"• Max Error: {np.max(pixel_errors):.4f} px")

    print("\n" + "="*60)

    results = {
        "acc_10px": acc_10px / 100.0,  # Convert to decimal
        "acc_20px": acc_20px / 100.0,
        "test_loss": float(test_loss),
        "test_mae": float(test_mae),
        "mean_pixel_error": float(mean_pixel_error),
        "test_count": len(X_test),
        "train_count": len(X_train)
    }

    return results

if __name__ == "__main__":
    results = test_model()

    if results:
        print("\n✅ Testing completed successfully!")

        # Save results to JSON for reference
        results_file = Path(__file__).parent / "model_test_results.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(f"Results saved to: {results_file}")
