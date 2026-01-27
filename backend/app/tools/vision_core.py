import sys
import os
import time
import cv2
import math
import numpy as np

# --- SÖKVÄGAR ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
# ----------------

from app.tools.ha_core import control_light, control_vacuum

def run_vision_loop():
    print("--- DAA VISION CORE (OPENCV/MATH MODE) STARTAR ---")
    
    # Hitta kameran
    cap = None
    for idx in [0, 1, -1, 2]:
        temp = cv2.VideoCapture(idx)
        if temp.isOpened():
            cap = temp
            print(f"Kamera hittad på index {idx}")
            break
            
    if not cap:
        print("KRITISKT FEL: Ingen kamera hittad. Är USB-kameran i?")
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
            roi_size = 300 # Storleken på rutan
            x_start = int(w/2 - roi_size/2)
            y_start = int(h/2 - roi_size/2)
            
            roi = frame[y_start:y_start+roi_size, x_start:x_start+roi_size]
            
            # 2. Hitta hudfärg (HSV)
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Justera dessa värden om din hand inte syns!
            # Detta är standard för "vanlig" hudfärg i rumsbelysning
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            
            mask = cv2.inRange(hsv, lower_skin, upper_skin)
            
            # Städa bort brus (små prickar)
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=4)
            mask = cv2.GaussianBlur(mask, (5,5), 100)
            
            # 3. Hitta konturer
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 0:
                # Anta att den största saken i rutan är handen
                contour = max(contours, key=lambda x: cv2.contourArea(x))
                
                if cv2.contourArea(contour) > 10000: # Måste vara tillräckligt stor
                    
                    # 4. Matematik: Räkna fingrar via "Convexity Defects"
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
                            
                            # Triangel-matematik för att hitta vinkeln mellan fingrar
                            a = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
                            b = math.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
                            c = math.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)
                            angle = math.acos((b**2 + c**2 - a**2) / (2*b*c)) * 57
                            
                            # Om vinkeln är skarp (< 90 grader) är det ett mellanrum
                            if angle <= 90:
                                finger_count += 1
                                
                        total_fingers = finger_count + 1
                        
                        # LOGIK
                        current_time = time.time()
                        if current_time - last_action_time > cooldown:
                            
                            # > 4 fingrar = Öppen hand
                            if total_fingers >= 4:
                                print(f"[OPENCV] 🖐️ Öppen hand ({total_fingers}) -> Hem")
                                control_vacuum("vacuum.roborock_s5_f528_robot_cleaner", "dock")
                                last_action_time = current_time
                                
                            # 1-2 fingrar = Peka / V-tecken
                            elif total_fingers == 1 or total_fingers == 2:
                                print(f"[OPENCV] ☝️ Peka ({total_fingers}) -> Tänd")
                                control_light("light.kontor_2", "on")
                                last_action_time = current_time
                                
                            # 0 fingrar (Knytnäve) är svårt med denna metod, 
                            # så vi använder bara Peka och Öppen hand just nu.

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