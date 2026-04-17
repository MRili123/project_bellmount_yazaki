# camera_setup.py
import cv2

def get_camera(index=0):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print("No camera detected")
        return None
    print(f"Camera detected at port {index}")
    return cap