# cable_detector.py
import cv2
import numpy as np

# Cable detection variables
in_counter = 0
out_counter = 0
stable_status = "No cable"

def detect_cable(frame):
    global in_counter, out_counter, stable_status

    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    largest_area = 0
    best_box = None
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if cw > ch*2 and area > 2000:
            if area > largest_area:
                largest_area = area
                best_box = (x, y, cw, ch)

    cable_detected = False
    cable_center_y = 0
    if best_box is not None:
        x, y, cw, ch = best_box
        cable_center_y = y + ch // 2
        cable_detected = True
        cv2.rectangle(frame, (x,y), (x+cw, y+ch), (255,0,0), 2)

    # Validation lines
    line1_y = h // 3
    line2_y = 2 * h // 3

    if cable_detected:
        if line1_y < cable_center_y < line2_y:
            in_counter += 1
            out_counter = 0
        else:
            out_counter += 1
            in_counter = 0

        if in_counter > 10:
            stable_status = "Cable IN"
        elif out_counter > 10:
            stable_status = "Cable OUT"

        cv2.circle(frame, (w//2, cable_center_y), 6, (0,255,255), -1)
    else:
        stable_status = "No cable"
        in_counter = 0
        out_counter = 0

    # Draw lines and status
    line_color = (0,255,0) if stable_status=="Cable IN" else (0,0,255)
    cv2.line(frame, (0,line1_y), (w,line1_y), line_color, 2)
    cv2.line(frame, (0,line2_y), (w,line2_y), line_color, 2)
    cv2.putText(frame, stable_status, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)

    return frame