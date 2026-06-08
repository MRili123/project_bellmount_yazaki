import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model_bellmounth_mesure"))

try:
    import cv2
    import numpy as np
    from PIL import Image
    from utils import apply_threshold
    
    print("✓ All imports successful")
    
    # Test with a simple image
    test_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
    print(f"✓ Created test image: {test_img.shape}")
    
    # Apply threshold
    result = apply_threshold(test_img)
    print(f"✓ Applied threshold: {result.shape}, dtype={result.dtype}")
    
    # Convert to PIL
    pil_img = Image.fromarray(result)
    print(f"✓ Converted to PIL: {pil_img.mode}, {pil_img.size}")
    
    # Convert to RGB
    rgb_img = pil_img.convert('RGB')
    print(f"✓ Converted to RGB: {rgb_img.mode}, {rgb_img.size}")
    
    print("\n✅ Thresholding pipeline works correctly!")
    
except Exception as e:
    print(f"✗ Error: {str(e)}")
    import traceback
    traceback.print_exc()
