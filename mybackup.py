import cv2
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import time
import numpy as np

cap = cv2.VideoCapture(0)

zoom = 1.0
pan_x = 0
pan_y = 0
drag_start = None

# ---- stability variables ----
in_counter = 0
out_counter = 0
stable_status = "No cable"

# ---- camera reference system ----
reference_image = None
reference_des = None
reference_kp = None
orb = cv2.ORB_create(1500)

camera_status = "No reference loaded"

# ---- frame storage ----
current_frame = None

# ---- score validation ----
score_timer = None
match_score = 0

# ---------------- Mouse Controls ----------------
def mouse_down(event):
    global drag_start
    drag_start = (event.x, event.y)

def mouse_move(event):
    global pan_x, pan_y, drag_start, zoom
    if drag_start is not None and zoom > 1:
        dx = event.x - drag_start[0]
        dy = event.y - drag_start[1]
        pan_x -= int(dx / zoom)
        pan_y -= int(dy / zoom)
        drag_start = (event.x, event.y)

def mouse_up(event):
    global drag_start
    drag_start = None

def mouse_scroll(event):
    global zoom, pan_x, pan_y
    old_zoom = zoom
    if event.delta > 0:
        zoom *= 1.1
    else:
        zoom /= 1.1
    zoom = max(1, min(zoom, 10))
    factor = zoom / old_zoom
    pan_x = int(pan_x * factor)
    pan_y = int(pan_y * factor)

# ---------------- Save Reference ----------------
def take_reference():
    global current_frame
    if current_frame is None:
        return
    file_path = filedialog.asksaveasfilename(
        title="Save Reference Image",
        defaultextension=".jpg",
        filetypes=[("JPEG Image", "*.jpg"), ("PNG Image", "*.png")]
    )
    if file_path:
        cv2.imwrite(file_path, current_frame)

# ---------------- Load Reference ----------------
def load_reference():
    global reference_image, reference_des, reference_kp
    file_path = filedialog.askopenfilename(
        title="Select Reference Image",
        filetypes=[("Image Files", "*.jpg *.png *.jpeg")]
    )
    if file_path:
        reference_image = cv2.imread(file_path)
        gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
        reference_kp, reference_des = orb.detectAndCompute(gray, None)
        print(f"Reference loaded: {file_path}")

# ---------------- Gauge Indicator ----------------
def draw_indicator(frame, score):
    h, w = frame.shape[:2]
    center_x = w // 2
    center_y = h - 30
    radius = 60
    # Red zone (0 - 300)
    cv2.ellipse(frame,(center_x,center_y),(radius,radius),0,180,230,(0,0,255),-1)
    # Yellow zone (300 - 600)
    cv2.ellipse(frame,(center_x,center_y),(radius,radius),0,230,270,(0,255,255),-1)
    # Green zone (600+)
    cv2.ellipse(frame,(center_x,center_y),(radius,radius),0,270,360,(0,255,0),-1)
    score = max(0, min(score, 1000))
    angle = 180 + (score / 1000) * 180
    x = int(center_x + radius * np.cos(np.radians(angle)))
    y = int(center_y + radius * np.sin(np.radians(angle)))
    cv2.line(frame,(center_x,center_y),(x,y),(255,255,255),3)
    cv2.circle(frame,(center_x,center_y),4,(255,255,255),-1)

# ---------------- Frame Processing ----------------
def update_frame():
    global zoom, pan_x, pan_y
    global in_counter, out_counter, stable_status
    global current_frame
    global camera_status
    global score_timer
    global match_score

    ret, frame = cap.read()
    if ret:
        current_frame = frame.copy()
        h, w = frame.shape[:2]

        # -------- Zoom & Pan --------
        max_pan_x = int((w * (zoom - 1)) / (2 * zoom))
        max_pan_y = int((h * (zoom - 1)) / (2 * zoom))
        pan_x_clamped = max(-max_pan_x, min(max_pan_x, pan_x))
        pan_y_clamped = max(-max_pan_y, min(max_pan_y, pan_y))
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        center_x = w // 2 + pan_x_clamped
        center_y = h // 2 + pan_y_clamped
        x1 = max(center_x - new_w // 2, 0)
        y1 = max(center_y - new_h // 2, 0)
        x2 = min(center_x + new_w // 2, w)
        y2 = min(center_y + new_h // 2, h)
        frame = frame[y1:y2, x1:x2]
        frame = cv2.resize(frame, (w, h))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # -------- Reference Comparison --------
        if reference_des is not None:
            kp_frame, des_frame = orb.detectAndCompute(gray, None)
            if des_frame is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(reference_des, des_frame)
                good_matches = [m for m in matches if m.distance < 50]
                match_score = len(good_matches)

                # ---- Camera distance check using reference image ----
                if len(good_matches) > 10:
                    ref_pts = np.array([reference_kp[m.queryIdx].pt for m in good_matches])
                    frame_pts = np.array([kp_frame[m.trainIdx].pt for m in good_matches])
                    ref_center = np.mean(ref_pts, axis=0)
                    frame_center = np.mean(frame_pts, axis=0)
                    ref_dist = np.linalg.norm(ref_pts - ref_center, axis=1).mean()
                    frame_dist = np.linalg.norm(frame_pts - frame_center, axis=1).mean()
                    avg_scale = frame_dist / ref_dist

                    if avg_scale < 0.95:
                        camera_status = "Camera too far"
                    elif avg_scale > 1.05:
                        camera_status = "Camera too close"
                    else:
                        camera_status = "Camera at ideal distance"

                cv2.putText(frame, f"Score: {match_score}", (10, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)

        # -------- Cable Detection --------
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 0
        best_box = None
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = cw * ch
            if cw > ch * 2 and area > 2000:
                if area > largest_area:
                    largest_area = area
                    best_box = (x, y, cw, ch)
        cable_detected = False
        cable_center_y = 0
        if best_box is not None:
            x, y, cw, ch = best_box
            cable_center_y = y + ch // 2
            cable_detected = True
            cv2.rectangle(frame, (x, y), (x + cw, y + ch), (255, 0, 0), 2)

        # -------- Validation Lines --------
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
            cv2.circle(frame, (w // 2, cable_center_y), 6, (0, 255, 255), -1)
        else:
            stable_status = "No cable"
            in_counter = 0
            out_counter = 0

        # -------- Draw Status --------
        line_color = (0, 255, 0) if stable_status == "Cable IN" else (0, 0, 255)
        cv2.putText(frame, stable_status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)
        cv2.line(frame, (0, line1_y), (w, line1_y), line_color, 2)
        cv2.line(frame, (0, line2_y), (w, line2_y), line_color, 2)

        # -------- Camera Status --------
        cv2.putText(frame, camera_status, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)

        # -------- Indicator --------
        draw_indicator(frame, match_score)

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        label.imgtk = imgtk
        label.configure(image=imgtk)

    label.after(10, update_frame)

# ---------------- GUI ----------------
root = tk.Tk()
root.title("Cable Camera Controller")
root.geometry("900x700")
root.configure(bg="#2b2b2b")

label = tk.Label(root,bg="black")
label.pack(pady=10)

btn1 = tk.Button(root, text="Take Reference Screenshot",
                 command=take_reference,
                 bg="#4CAF50", fg="white",
                 font=("Arial",11,"bold"),
                 padx=10,pady=5)
btn1.pack(pady=4)

btn2 = tk.Button(root, text="Load Reference Image",
                 command=load_reference,
                 bg="#2196F3", fg="white",
                 font=("Arial",11,"bold"),
                 padx=10,pady=5)
btn2.pack(pady=4)

# Mouse controls
label.bind("<Button-1>", mouse_down)
label.bind("<B1-Motion>", mouse_move)
label.bind("<ButtonRelease-1>", mouse_up)
label.bind("<MouseWheel>", mouse_scroll)

update_frame()
root.mainloop()
cap.release()