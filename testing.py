import cv2 

camera_avalaible = False

zoom = 1.0 
zoom_step = 0.1

for i in [0,1,2,3] :
   
   cap = cv2.VideoCapture(i)

   if  cap.isOpened(): 
      print(f"camera detected in port {i}")
      camera_avalaible = True
      break 
   
if camera_avalaible == False : 
   print("theres no camera detected")
   exit()

def Zoom_controlle(event,x,y,flags,param): 
   global zoom 

   if event == cv2.EVENT_MOUSEWHEEL :
       if flags > 0: 
          zoom += zoom_step 
       else : 
          zoom -= zoom_step
       zoom = max(1.0, min(zoom, 5.0))

cv2.namedWindow("frame",cv2.WINDOW_NORMAL)
cv2.setMouseCallback("frame",Zoom_controlle)  

while True : 
     ret, frame = cap.read()
     if not ret : 
      print("something went wrong")  
      break 
     h,w = frame.shape[:2]

     new_h = int( h / zoom)
     new_w = int(w / zoom) 

     x1 = (w - new_w ) // 2 
     y1 = (h - new_h ) // 2 
     
     yh = y1 + new_h
     xw = x1 + new_w

     cropped  = frame[y1:yh ,x1:xw]

     frame_zoomed = cv2.resize(cropped, (w,h))    


     cv2.imshow("frame", frame_zoomed) 
     cv2.waitKey(1)
     if cv2.getWindowProperty("frame", cv2.WND_PROP_VISIBLE) < 1:
        break
     
  
cap.release()
cv2.destroyAllWindows()

         
  