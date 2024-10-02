import os
import cv2
import numpy as np
import argparse
import keyboard
from djitellopy import Tello

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

    def draw_crosshair(self, frame):
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        size = 10

        cv2.line(frame, (center_x - size, center_y), (center_x + size, center_y), (255, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - size), (center_x, center_y + size), (255, 255, 255), 2)

    def run(self):
        self.tello.connect()
        self.tello.streamon()

        while True:
            frame = get_frame(self.tello, WIDTH, HEIGHT)

            # if self.handle_keys(frame):
            #     break
            #
            # if self.BB is not None:
            #     success, frame, box = self.track(frame)
            #     if success:
            #         self.track_target(box, WIDTH, HEIGHT)
            #
            # self.draw_crosshair(frame)
            #
            # cv2.putText(frame, f'Battery: {self.tello.get_battery()}%', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.imshow('Tello Drone', frame)

            # Write the frame to the video file
            self.out.write(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()
        self.tello.end()
        self.out.release()

    def handle_keys(self, frame):
        if keyboard.is_pressed('esc'):
            return True
        elif keyboard.is_pressed('t'):
            self.tello.takeoff()
            self.send_rc_control = True
        elif keyboard.is_pressed('l'):
            self.tello.land()
            self.send_rc_control = False
        elif keyboard.is_pressed('c'):
            self.BB = cv2.selectROI("Tello Drone", frame, fromCenter=False, showCrosshair=True)
            self.tracker.init(frame, self.BB)

        if self.send_rc_control:
            # fly forward and back
            if keyboard.is_pressed('w'):
                self.for_back_velocity = self.speed
            elif keyboard.is_pressed('s'):
                self.for_back_velocity = -self.speed
            else:
                self.for_back_velocity = 0

            # fly left & right
            if keyboard.is_pressed('d'):
                self.left_right_velocity = self.speed
            elif keyboard.is_pressed('a'):
                self.left_right_velocity = -self.speed
            else:
                self.left_right_velocity = 0

            # fly up & down
            if keyboard.is_pressed('up'):
                self.up_down_velocity = self.speed
            elif keyboard.is_pressed('down'):
                self.up_down_velocity = -self.speed
            else:
                self.up_down_velocity = 0

            # turn right or left
            if keyboard.is_pressed('right'):
                self.yaw_velocity = self.speed
            elif keyboard.is_pressed('left'):
                self.yaw_velocity = -self.speed
            else:
                self.yaw_velocity = 0

            if keyboard.is_pressed('+'):
                self.speed = min(self.speed + 5, 100)
            if keyboard.is_pressed('-'):
                self.speed = max(self.speed - 5, 5)

            self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)

        return False

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
