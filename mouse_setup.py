
import cv2


pan_x, pan_y = 0, 0
drag_start = None
dragging = False

def mouse_pan(event, x, y, flags, param):
  
    global pan_x, pan_y, drag_start, dragging

    if event == cv2.EVENT_LBUTTONDOWN:
        drag_start = (x, y)
        dragging = True

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
        drag_start = None

    elif event == cv2.EVENT_MOUSEMOVE and dragging:
        dx = x - drag_start[0]
        dy = y - drag_start[1]
        pan_x += dx
        pan_y += dy
        drag_start = (x, y)