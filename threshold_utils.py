"""Image thresholding used for cable detection preprocessing.

Local copy of apply_threshold (previously imported from the separate
model_bellmounth_mesure project on the Desktop) so the app is self-contained
and can be packaged as a standalone executable.
"""

import cv2
import numpy as np


def apply_threshold(bgr):
    """Apply threshold to convert image to binary - optimized.
    Kernel=21, C=5 for cable detection preprocessing.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 21, 5)
    k = np.ones((2, 2), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
    return cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)
