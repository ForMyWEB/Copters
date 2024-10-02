import os
import cv2
import numpy as np
import argparse
from djitellopy import Tello
import tkinter as tk
from tkinter import scrolledtext
from PIL import Image, ImageTk

WIDTH, HEIGHT = 640, 480
FPS = 30

def get_frame(tello, width=WIDTH, height=HEIGHT):
    frame = tello.get_frame_read().frame
    resized_frame = cv2.resize(frame, (width, height))
    return resized_frame

class RyzeTello:
    def __init__(self, save_path):
        self.tello = Tello()
        self.for_back_velocity = 0
        self.left_right_velocity = 0
        self.up_down_velocity = 0
        self.yaw_velocity = 0
        self.speed = 60
        self.send_rc_control = False
        self.save_path = save_path

        # Video writer
        self.out = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (WIDTH, HEIGHT))

        self.tracker = cv2.TrackerCSRT_create()
        self.BB = None
        self.pid = [0.4, 0.4, 0]
        self.pError = 0

        # Tkinter setup
        self.root = tk.Tk()
        self.root.title("Tello Drone Control Panel")

        self.video_label = tk.Label(self.root)
        self.video_label.pack()

        self.controls_frame = tk.Frame(self.root)
        self.controls_frame.pack()

        self.takeoff_button = tk.Button(self.controls_frame, text="Takeoff", command=self.takeoff)
        self.takeoff_button.grid(row=0, column=0)

        self.land_button = tk.Button(self.controls_frame, text="Land", command=self.land)
        self.land_button.grid(row=0, column=1)

        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=50, height=10)
        self.text_area.pack()

        self.update_video_feed()

        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)

    def log_message(self, message):
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.see(tk.END)

    def takeoff(self):
        self.tello.takeoff()
        self.send_rc_control = True
        self.log_message("Takeoff initiated")

    def land(self):
        self.tello.land()
        self.send_rc_control = False
        self.log_message("Landing initiated")

    def draw_crosshair(self, frame):
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        size = 10

        cv2.line(frame, (center_x - size, center_y), (center_x + size, center_y), (255, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - size), (center_x, center_y + size), (255, 255, 255), 2)

    def run(self):
        self.tello.connect()
        self.tello.streamon()
        self.root.mainloop()

    def update_video_feed(self):
        frame = get_frame(self.tello, WIDTH, HEIGHT)

        if self.BB is not None:
            success, frame, box = self.track(frame)
            if success:
                self.track_target(box, WIDTH, HEIGHT)

        self.draw_crosshair(frame)

        cv2.putText(frame, f'Battery: {self.tello.get_battery()}%', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Convert the frame to a format suitable for Tkinter
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        # Write the frame to the video file
        self.out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

        self.video_label.after(10, self.update_video_feed)

    def on_key_press(self, event):
        if event.keysym == 'Escape':
            self.root.destroy()
        elif event.keysym == 'w':
            self.for_back_velocity = self.speed
        elif event.keysym == 's':
            self.for_back_velocity = -self.speed
        elif event.keysym == 'a':
            self.left_right_velocity = -self.speed
        elif event.keysym == 'd':
            self.left_right_velocity = self.speed
        elif event.keysym == 'Up':
            self.up_down_velocity = self.speed
        elif event.keysym == 'Down':
            self.up_down_velocity = -self.speed
        elif event.keysym == 'Left':
            self.yaw_velocity = -self.speed
        elif event.keysym == 'Right':
            self.yaw_velocity = self.speed

        self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)

    def on_key_release(self, event):
        if event.keysym in ['w', 's']:
            self.for_back_velocity = 0
        elif event.keysym in ['a', 'd']:
            self.left_right_velocity = 0
        elif event.keysym in ['Up', 'Down']:
            self.up_down_velocity = 0
        elif event.keysym in ['Left', 'Right']:
            self.yaw_velocity = 0

        self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)

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
        self.yaw_velocity = int(np.clip(self.pid[0] * error + self.pid[1] * (error - self.pError), -100, 100))
        self.pError = error
        area = w * h

        if area > 40000:  # Якщо об'єкт дуже близько
            self.for_back_velocity = -40  # Повільний рух назад
        elif area < 10000:  # Якщо об'єкт далеко
            self.for_back_velocity = 40  # Повільний рух вперед
        else:
            self.for_back_velocity = 0  # Залишатися на місці

        self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-sp', '--save_path', type=str, default="drone_video.mp4", help="Path where video will be saved")
    args = parser.parse_args()

    drone = RyzeTello(args.save_path)
    drone.run()
