import sys
import os
import time
import cv2
import math
import numpy as np

# --- PATHS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
# ----------------

from app.tools.ha_core import control_light, control_vacuum

def run_vision_loop():
    print("--- DAA VISION CORE (OPENCV/MATH MODE) STARTING ---")
    
    # Find camera
    cap = None
    for idx in [0, 1, -1, 2]:
        temp = cv2.VideoCapture(idx)
        if temp.isOpened():
            cap = temp
            print(f"Camera found at index {idx}")
            break
            
    if not cap:
        print("CRITICAL ERROR: No camera found. Is the USB camera connected?")
        return

    last_action_time = 0
    cooldown = 4.0 

    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue

            # 1. Fokusera på en ruta i mitten (ROI)
            # Detta minskar felkällor från bakgrunden
            h, w, _ = frame.shape
            roi_size = 300 # Size of the square
            x_start = int(w/2 - roi_size/2)
            y_start = int(h/2 - roi_size/2)
            
            roi = frame[y_start:y_start+roi_size, x_start:x_start+roi_size]
            
            # 2. Find skin color (HSV)
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Adjust these values if your hand is not detected!
            # This is standard for "normal" skin color in room lighting
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            
            # Clean up noise (small dots)
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=4)
            mask = cv2.GaussianBlur(mask, (5,5), 100)
            
            # 3. Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 0:
                # Assume the largest object in the box is the hand
                contour = max(contours, key=lambda x: cv2.contourArea(x))
                
                if cv2.contourArea(contour) > 10000: # Must be large enough
                    
                    # 4. Math: Count fingers via "Convexity Defects"
                    hull = cv2.convexHull(contour)
                    hull_indices = cv2.convexHull(contour, returnPoints=False)
                    defects = cv2.convexityDefects(contour, hull_indices)
                    
                    finger_count = 0
                    
                    if defects is not None:
                        for i in range(defects.shape[0]):
                            s, e, f, d = defects[i,0]
                            start = tuple(contour[s][0])
                            end = tuple(contour[e][0])
                            far = tuple(contour[f][0])
                            
                            # Triangle math to find the angle between fingers
                            a = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
                            b = math.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
                            c = math.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)
                            angle = math.acos((b**2 + c**2 - a**2) / (2*b*c)) * 57
                            
                            # If the angle is sharp (< 90 degrees) it's a gap
                            if angle <= 90:
                                finger_count += 1
                                
                        total_fingers = finger_count + 1
                        
                        # LOGIK
                        current_time = time.time()
                        if current_time - last_action_time > cooldown:
                            
                            # > 4 fingers = Open hand
                            if total_fingers >= 4:
                                print(f"[OPENCV] 🖐️ Open hand ({total_fingers}) -> Home")
                                control_vacuum("vacuum.roborock_s5_f528_robot_cleaner", "dock")
                                last_action_time = current_time
                                
                            # 1-2 fingers = Point / V-sign
                            elif total_fingers == 1 or total_fingers == 2:
                                print(f"[OPENCV] ☝️ Point ({total_fingers}) -> Light on")
                                control_light("light.kontor_2", "on")
                                last_action_time = current_time
                                
                            # 0 fingers (Fist) is difficult with this method,
                            # so we only use Point and Open hand for now.

            time.sleep(0.1)
            
        except Exception as e:
            print(f"Vision Error: {e}")
            time.sleep(1)

    cap.release()

if __name__ == "__main__":
    try:
        run_vision_loop()
    except KeyboardInterrupt:
        pass