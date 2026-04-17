# interaction_setup.py

zoom = 1.0
pan_x, pan_y = 0, 0
drag_start = None

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