import os
import cv2
import numpy as np
import argparse
import tkinter as tk
from PIL import Image, ImageTk
from djitellopy import Tello
from pynput import keyboard

WIDTH, HEIGHT = 640, 480
FPS = 30

class RyzeTelloApp:
    def __init__(self, window, window_title, save_path):
        self.window = window
        self.window.title(window_title)

        # Спробуємо підключитися до дрона
        self.tello = Tello()
        self.use_drone = False
        
        try:
            self.tello.connect()
            self.tello.streamon()
            self.use_drone = True
            print("Підключено до дрона")
        except Exception as e:
            print(f"Не вдалося підключитися до дрона: {e}")
            self.use_drone = False

        # Якщо не підключено до дрона, використовуємо веб-камеру
        if not self.use_drone:
            self.vid = cv2.VideoCapture(0)  # Камера ноутбука
            self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

        # Параметри для запису відео
        self.is_recording = False
        self.out = None
        self.save_path = save_path

        # Canvas для відео
        self.canvas = tk.Canvas(window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()

        # Кнопка для запису/зупинки відео
        self.btn_video = tk.Button(window, text="Почати запис", width=50, command=self.toggle_recording)
        self.btn_video.pack(anchor=tk.CENTER, expand=True)

        # Затримка оновлення відео
        self.delay = 10

        # Змінні для керування дроном
        self.for_back_velocity = 0
        self.left_right_velocity = 0
        self.up_down_velocity = 0
        self.yaw_velocity = 0
        self.speed = 60
        self.send_rc_control = False

        # Ініціалізація трекінгу
        self.tracker = cv2.TrackerKCF_create()  # Використовуємо TrackerKCF як альтернативу
        self.BB = None
        self.tracking = False

        # Налаштування обробки натискань клавіш
        self.listener = keyboard.Listener(on_press=self.handle_keys)
        self.listener.start()

        # Оновлення відеопотоку
        self.update()

        # Запуск головного вікна
        self.window.mainloop()

    def get_frame(self):
        if self.use_drone:
            frame = self.tello.get_frame_read().frame
            resized_frame = cv2.resize(frame, (WIDTH, HEIGHT))
        else:
            ret, frame = self.vid.read()
            if ret:
                resized_frame = cv2.resize(frame, (WIDTH, HEIGHT))
            else:
                resized_frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        return resized_frame

    def toggle_recording(self):
        # Якщо вже записуємо відео - зупиняємо запис
        if self.is_recording:
            self.is_recording = False
            self.btn_video.config(text="Почати запис")
            self.out.release()
            print(f"Відео збережено у: {self.save_path}")
        else:
            # Починаємо новий запис відео
            self.is_recording = True
            self.btn_video.config(text="Зупинити запис")
            self.out = cv2.VideoWriter(self.save_path, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (WIDTH, HEIGHT))
            print("Почався запис відео")

    def update(self):
        frame = self.get_frame()

        if self.tracking and self.BB is not None:
            success, box = self.tracker.update(frame)
            if success:
                x, y, w, h = [int(v) for v in box]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                self.track_target(box, WIDTH, HEIGHT)
            else:
                print("Трекер втратив об'єкт")

        # Малюємо crosshair
        self.draw_crosshair(frame)

        if self.use_drone:
            # Відображаємо батарею, якщо підключено до дрона
            cv2.putText(frame, f'Battery: {self.tello.get_battery()}%', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Конвертація для відображення у Tkinter
        self.photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        # Записуємо кадр у файл, якщо запис триває
        if self.is_recording:
            self.out.write(frame)

        # Оновлення через затримку
        self.window.after(self.delay, self.update)

    def draw_crosshair(self, frame):
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        size = 10
        cv2.line(frame, (center_x - size, center_y), (center_x + size, center_y), (255, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - size), (center_x, center_y + size), (255, 255, 255), 2)

    def handle_keys(self, key):
        try:
            if key == keyboard.Key.esc:
                self.window.quit()
            elif key.char == 'q':
                # Вихід з програми при натисканні Q
                self.window.quit()
                return False  # Зупиняє слухач клавіатури
            elif key.char == 'c':
                # Активуємо режим трекінгу при натисканні C
                frame = self.get_frame()
                if frame is not None:
                    self.BB = cv2.selectROI("Select Object", frame, fromCenter=False, showCrosshair=True)
                    if self.BB[2] > 0 and self.BB[3] > 0:  # Переконаємося, що ROI має ненульову ширину та висоту
                        self.tracker.init(frame, self.BB)
                        self.tracking = True
                        cv2.destroyWindow("Select Object")
                    else:
                        print("ROI не вибрано")

            # Управління рухом з клавішами
            if key.char == 'w':
                self.for_back_velocity = self.speed
            elif key.char == 's':
                self.for_back_velocity = -self.speed
            else:
                self.for_back_velocity = 0

            if key.char == 'a':
                self.left_right_velocity = -self.speed
            elif key.char == 'd':
                self.left_right_velocity = self.speed
            else:
                self.left_right_velocity = 0

            if key.char == 'up':
                self.up_down_velocity = self.speed
            elif key.char == 'down':
                self.up_down_velocity = -self.speed
            else:
                self.up_down_velocity = 0

            if key.char == 'right':
                self.yaw_velocity = self.speed
            elif key.char == 'left':
                self.yaw_velocity = -self.speed
            else:
                self.yaw_velocity = 0

            if key.char == '+':
                self.speed = min(self.speed + 5, 100)
            elif key.char == '-':
                self.speed = max(self.speed - 5, 5)

            if self.use_drone:
                self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)
        except AttributeError:
            # Виключаємо клавіші, які не мають символів (наприклад, клавіші зі стрілками)
            pass

    def track_target(self, box, frame_w, frame_h):
        x, y, w, h = box
        cx = x + w // 2
        cy = y + h // 2
        error = cx - frame_w // 2
        self.yaw_velocity = int(np.clip(0.4 * error + 0.4 * (error - 0), -100, 100))

        area = w * h
        if area > 40000:  # Якщо об'єкт дуже близько
            self.for_back_velocity = -40  # Повільний рух назад
        elif area < 10000:  # Якщо об'єкт далеко
            self.for_back_velocity = 40  # Повільний рух вперед
        else:
            self.for_back_velocity = 0  # Залишатися на місці

        if self.use_drone:
            self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-sp', '--save_path', type=str, default="video.mp4", help="Path where video will be saved")
    args = parser.parse_args()

    root = tk.Tk()
    app = RyzeTelloApp(root, "Ryze Tello App", args.save_path)
