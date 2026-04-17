
import cv2

zoom = 1.0
zoom_step = 0.1
pan_x, pan_y = 0, 0  

def zoom_control(event, x, y, flags, param):

    global zoom
    if event == cv2.EVENT_MOUSEWHEEL:
        if flags > 0:
            zoom += zoom_step
        else:
            zoom -= zoom_step
        zoom = max(1.0, min(zoom, 5.0))

def apply_zoom(frame):

    global zoom, pan_x, pan_y
    h, w = frame.shape[:2]
    new_h = int(h / zoom)
    new_w = int(w / zoom)


    x1 = max(0, min((w - new_w) // 2 - pan_x, w - new_w))
    y1 = max(0, min((h - new_h) // 2 - pan_y, h - new_h))

    cropped = frame[y1:y1+new_h, x1:x1+new_w]
    return cv2.resize(cropped, (w, h))