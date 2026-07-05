#!/usr/bin/env python3
"""
Standalone Model Training and Testing Script
Trains the cable measurement model and tests it
No GUI required - just run and wait!
"""

import sys
import json
import numpy as np
from pathlib import Path
from PIL import Image
import tensorflow as tf
from sklearn.model_selection import train_test_split

# Paths
DATASET_DIR = Path("C:/BellmouthProject/dataset")
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MODEL_DIR = Path("C:/BellmouthProject/app/models/mesure")
MODEL_FILE = MODEL_DIR / "CNN_BELMOUNTH_MODEL_V1.h5"

print("=" * 80)
print("CABLE MEASUREMENT MODEL - TRAINING & TESTING")
print("=" * 80)

# Step 1: Load annotations
print("\n[1/4] Loading dataset...")
try:
    with open(ANNOTATIONS_FILE, 'r') as f:
        annotations = json.load(f)
    print(f"[OK] Loaded {len(annotations)} annotations")
except Exception as e:
    print(f"[ERROR] Error loading annotations: {e}")
    sys.exit(1)

# Step 2: Prepare dataset
print("\n[2/4] Preparing training data...")
X = []
y = []

for i, ann in enumerate(annotations):
    if i % 100 == 0:
        print(f"  Processing... {i}/{len(annotations)}")

    # Load thresholded image
    img_path = Path(ann.get("thresholded_path", ""))
    if not img_path.exists():
        img_path = THRESH_DIR / ann["filename"]

    try:
        if img_path.exists():
            img = Image.open(str(img_path)).convert('L')
            img = img.resize((640, 480))
            img_array = np.array(img, dtype=np.float32) / 255.0

            # Get keypoints (normalized)
            points = ann.get("points", [])
            if len(points) >= 2:
                p1 = points[0]
                p2 = points[1]
                width = ann.get("width", 640)
                height = ann.get("height", 480)

                kps = np.array([
                    p1.get("x", 0) / width,
                    p1.get("y", 0) / height,
                    p2.get("x", 0) / width,
                    p2.get("y", 0) / height
                ], dtype=np.float32)

                X.append(img_array)
                y.append(kps)
    except Exception as e:
        pass

X = np.array(X)[..., np.newaxis]  # Add channel dimension
y = np.array(y, dtype=np.float32)

print(f"[OK] Prepared {len(X)} samples")
if len(X) < 10:
    print(f"[ERROR] Not enough samples ({len(X)} < 10)")
    sys.exit(1)

# Step 3: Build and train model
print("\n[3/4] Training model...")
print(f"  Train/test split: 80/20")
print(f"  Input shape: (640, 480, 1)")
print(f"  Output: 4 keypoints (x1, y1, x2, y2)")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Build model
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(480, 640, 1)),
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(512, activation='relu'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.Dropout(0.4),
    tf.keras.layers.Dense(256, activation='relu'),
    tf.keras.layers.Dropout(0.3),
    tf.keras.layers.Dense(4, activation='sigmoid')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss='mse',
    metrics=['mae']
)

# Train
print("\n  Training for 30 epochs...")
history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=8,
    validation_data=(X_test, y_test),
    verbose=1
)

# Step 4: Evaluate and save
print("\n[4/4] Evaluating and saving model...")
test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)
print(f"[OK] Test Loss: {test_loss:.4f}")
print(f"[OK] Test MAE: {test_mae:.4f}")

# Save model
MODEL_DIR.mkdir(parents=True, exist_ok=True)
model.save(str(MODEL_FILE))
print(f"[OK] Model saved to: {MODEL_FILE}")

# Test on a sample
print("\n" + "=" * 80)
print("TESTING MODEL")
print("=" * 80)

sample_idx = np.random.randint(0, len(X_test))
sample_img = X_test[sample_idx:sample_idx+1]
sample_true = y_test[sample_idx]

prediction = model.predict(sample_img, verbose=0)[0]

print(f"\nSample {sample_idx}:")
print(f"  True keypoints:   {sample_true}")
print(f"  Predicted:        {prediction}")
print(f"  Difference:       {np.abs(sample_true - prediction)}")

print("\n" + "=" * 80)
print("[OK] TRAINING COMPLETE!")
print("=" * 80)
print(f"\nModel is ready at: {MODEL_FILE}")
print("You can now use it in the admin panel for inference!")
