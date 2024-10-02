import cv2
import numpy as np
import customtkinter as ctk
from PIL import Image, ImageTk
import threading
import time

WIDTH, HEIGHT = 640, 480
FPS = 30

def get_frame(cap, width=WIDTH, height=HEIGHT):
    ret, frame = cap.read()
    if not ret:
        return None
    resized_frame = cv2.resize(frame, (width, height))
    return resized_frame

class WebcamApp:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.tracker = cv2.TrackerCSRT_create()
        self.BB = None
        self.pid = [0.4, 0.4, 0]
        self.pError = 0
        self.running = True
        self.tracking = False

        # CustomTkinter setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Webcam Control Panel")

        self.video_label = ctk.CTkLabel(self.root)
        self.video_label.pack()

        self.controls_frame = ctk.CTkFrame(self.root)
        self.controls_frame.pack()

        self.start_tracking_button = ctk.CTkButton(self.controls_frame, text="Start Tracking", command=self.start_tracking)
        self.start_tracking_button.grid(row=0, column=0)

        self.stop_tracking_button = ctk.CTkButton(self.controls_frame, text="Stop Tracking", command=self.stop_tracking)
        self.stop_tracking_button.grid(row=0, column=1)

        self.text_area = ctk.CTkTextbox(self.root, width=500, height=100)
        self.text_area.pack()

        self.video_thread = threading.Thread(target=self.update_video_feed)
        self.video_thread.daemon = True
        self.video_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def log_message(self, message):
        self.text_area.insert(ctk.END, message + '\n')
        self.text_area.see(ctk.END)

    def draw_crosshair(self, frame):
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        size = 10

        cv2.line(frame, (center_x - size, center_y), (center_x + size, center_y), (255, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - size), (center_x, center_y + size), (255, 255, 255), 2)

    def run(self):
        self.root.mainloop()

    def update_video_feed(self):
        while self.running:
            frame = get_frame(self.cap, WIDTH, HEIGHT)
            if frame is None:
                continue

            if self.tracking and self.BB is not None:
                success, frame, box = self.track(frame)
                if success:
                    self.track_target(box, WIDTH, HEIGHT)

            self.draw_crosshair(frame)

            # Convert the frame to a format suitable for Tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

            time.sleep(1 / FPS)  # Control frame rate

    def start_tracking(self):
        # Create a separate thread to select the ROI
        roi_thread = threading.Thread(target=self.select_roi)
        roi_thread.start()

    def select_roi(self):
        # Pause the video update while selecting ROI
        self.running = False
        frame = get_frame(self.cap, WIDTH, HEIGHT)
        if frame is not None:
            self.BB = cv2.selectROI("Select ROI", frame, fromCenter=False, showCrosshair=True)
            cv2.destroyWindow("Select ROI")
            if self.BB and self.BB != (0, 0, 0, 0):
                self.tracker = cv2.TrackerCSRT_create()
                self.tracker.init(frame, self.BB)
                self.tracking = True
                self.log_message("Tracking started")
        self.running = True

    def stop_tracking(self):
        self.tracking = False
        self.BB = None
        self.log_message("Tracking stopped")

    def track(self, frame):
        success, box = self.tracker.update(frame)
        if success:
            x, y, w, h = [int(v) for v in box]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        return success, frame, box

    def track_target(self, box, frame_w, frame_h):
        x, y, w, h = box
        cx = x + w // 2
        cy = y + h // 2
        error = cx - frame_w // 2
        self.pError = error
        area = w * h

        if area > 40000:  # Якщо об'єкт дуже близько
            pass  # Дії якщо об'єкт дуже близько
        elif area < 10000:  # Якщо об'єкт далеко
            pass  # Дії якщо об'єкт далеко

    def on_closing(self):
        self.running = False
        self.video_thread.join()
        self.cap.release()
        self.root.destroy()

if __name__ == '__main__':
    app = WebcamApp()
    app.run()
