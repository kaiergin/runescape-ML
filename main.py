import sys
import json
import time
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5 import QtCore, QtGui
from pynput import mouse
from pynput import keyboard
import win32api
import win32con
import win32gui
import win32com.client
import pyautogui
import threading
import numpy as np
from predict import Network
import random
import tkinter as tk
from tkinter import filedialog
from PIL import ImageTk
import pickle
from mousepath import wind_mouse

x_size = win32api.GetSystemMetrics(0)
y_size = win32api.GetSystemMetrics(1)
shell = win32com.client.Dispatch("WScript.Shell")

# Constants

DEBUG = False
NETWORK_INPUT = (400,300)
RIGHT_CLICK = 0
LEFT_CLICK = 1
SAVE_DIR = 'scripts\\'
PICKLE_SAVE = 'training.data'
EXTRA_SLEEP = 0.5

# For window and main loop

class ScreenOverlay(QMainWindow):
    def __init__(self, config):
        super().__init__()

        # Config
        self.config = config
        self.mode = 'idle'
        self.current_save_path = 'none'

        # Capturing setup
        self.last_click_time = None
        self.new_recording()

        # Screen setup
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.X11BypassWindowManagerHint
        )
        self.current_size = self.config['window_size']
        self.left_corner = self.config['left_corner']
        self.move(*self.left_corner)
        self.right_corner = (self.left_corner[0] + self.current_size[0], self.left_corner[1] + self.current_size[1])
        self.setMinimumSize(QtCore.QSize(self.current_size[0] + 1, self.current_size[1] + 1))
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        # Network setup and thread init
        self.mouse_predictor = Network(self.current_size, NETWORK_INPUT)
        self.capture_on = True

        keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        keyboard_listener.start()
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        threading.Thread(target=self.background_thread, daemon=True).start()

        find_window_then_resize_and_move(self.config['window_name'], self.left_corner, self.current_size)

    def clear_last_capture(self):
        self.last_click_time = None
        self.last_click_location = None
        self.last_screen_capture = None

    def new_recording(self):
        self.click_buffer = []
        self.screen_cap_buffer = []
        self.click_time_buffer = []
        self.clear_last_capture()

    def save_data(self):
        with open(PICKLE_SAVE, 'wb') as savefile:
            print('Saving data to', PICKLE_SAVE)
            pickle.dump((self.click_buffer, self.screen_cap_buffer, self.click_time_buffer), savefile)

    def load_data(self):
        with open(PICKLE_SAVE, 'rb') as savefile:
            print('Loading data from', PICKLE_SAVE)
            clicks, screen_caps, click_times = pickle.load(savefile)
            self.click_buffer += clicks
            self.screen_cap_buffer += screen_caps
            self.click_time_buffer += click_times
            if DEBUG:
                print(self.click_buffer)
                print(self.click_time_buffer)

    def record_moment(self, click, screen_cap):
        start_time = time.time()
        if self.last_click_time != None:
            self.click_buffer.append(self.last_click_location)
            self.screen_cap_buffer.append(self.last_screen_capture)
            self.click_time_buffer.append(start_time - self.last_click_time)
        self.last_click_time = start_time
        self.last_click_location = click
        self.last_screen_capture = screen_cap
    
    def on_click(self, x, y, button, pressed):
        if DEBUG:
            print('{0} at {1}'.format('Pressed' if pressed else 'Released', (x, y)))
        if self.in_capture_window(x, y):
            if self.mode == 'record' or self.mode == 'record-control':
                if pressed and (button == mouse.Button.left):# or button == mouse.Button.right):
                    click = self.full_to_window((x, y))#, RIGHT_CLICK if button == mouse.Button.right else LEFT_CLICK
                    cap = pyautogui.screenshot(region=(*self.left_corner, self.current_size[0], self.current_size[1]))
                    processed_capture = cap.resize(NETWORK_INPUT)
                    self.record_moment(click, processed_capture)
        if not self.capture_on:
            # Stop listener
            return False

    def on_press(self, key):
        if DEBUG:
            try:
                print('alphanumeric key {0} pressed'.format(key.char))
            except AttributeError:
                print('special key {0} pressed'.format(key))
        
    def on_release(self, key):
        try:
            key = '{0}'.format(key.char)
        except AttributeError:
            key = '{0}'.format(key)
            key = key.split('.')[1]

        if DEBUG:
            print(key, 'released')

        if key == self.config['close']: 
            print('Closing application')
            self.capture_on = False
            QApplication.quit()
            return False
        elif key == self.config['record']:
            print('Record mode: ON')
            self.mode = 'record'
            self.clear_last_capture()
        elif key == self.config['control']:
            print('Control mode: ON')
            self.mode = 'control'
        elif key == self.config['idle']:
            print('Recording/Controlling: OFF')
            print('Idle: ON')
            self.mode = 'idle'
        elif key == self.config['record-control']:
            print('Recording AND Controlling: ON')
            self.mode = 'record-control'
            self.clear_last_capture()
        elif key == self.config['train']:
            print('Starting training')
            self.mode = 'training'
            if len(self.screen_cap_buffer) == 0:
                print('No data to train on')
            else:
                self.mouse_predictor.train(self.screen_cap_buffer, self.click_buffer, self.click_time_buffer)
        elif key == self.config['load/save_network']:
            if self.mode != 'idle':
                print('You must be in idle mode to load or save a network, press', self.config['idle'], 'then try again')
            else:
                print('Would you like to load or save a network? (l or s)')
                load_or_save = input('>')
                while load_or_save != 'l' and load_or_save != 's':
                    print('Not l or s')
                    load_or_save = input('>')
                if load_or_save == 'l':
                    root = tk.Tk()
                    root.withdraw()
                    file_path = filedialog.askdirectory(initialdir=SAVE_DIR, title='Select network folder')
                    self.mouse_predictor.load(file_path)
                else:
                    if self.current_save_path == 'none':
                        print('Saving network - please input network name')
                        network_name = input('>')
                        while network_name == '':
                            network_name = input('>')
                        self.current_save_path = SAVE_DIR + network_name
                    else:
                        print('Saving network - file already exist at ' + self.current_save_path + ', would you like to overwrite it? (y,n)')
                        stdinput = input('>')
                        while stdinput != 'y' and stdinput != 'n':
                            print('Unknown response, type y or n')
                            stdinput = input('>')
                        if stdinput == 'y':
                            pass
                        else:
                            print('Please input new network name')
                            network_name = input('>')
                            while network_name == '':
                                network_name = input('>')
                            self.current_save_path = SAVE_DIR + network_name
                    print('Saving to', self.current_save_path)
                    self.mouse_predictor.save(self.current_save_path)
        elif key == self.config['load/save_data']:
            if self.mode != 'idle':
                print('You must be in idle mode to load or save training data, press', self.config['idle'], 'then try again')
            else:
                print('Would you like to load or save training data? (l or s)')
                load_or_save = input('>')
                while load_or_save != 'l' and load_or_save != 's':
                    print('Not l or s')
                    load_or_save = input('>')
                if load_or_save == 'l':
                    self.load_data()
                else:
                    self.save_data()
        elif key == self.config['new_network']:
            if self.mode != 'idle':
                print('You must be in idle mode to create a new network, press', self.config['idle'], 'then try again')
            else:
                print('Creating new network, wiping loaded weights')
                self.current_save_path = 'none'
                self.mouse_predictor.new_network()
        elif key == self.config['clear_recording']:
            if self.mode != 'idle':
                print('You must be in idle mode to clear training data, press', self.config['idle'], 'then try again')
            else:
                print('Clearing data')
                self.new_recording()
        elif key == self.config['data_edit']:
            print('Starting data edit mode')
            print('Click in location to reset prediction for training')
            print('Exit window or hit S to move to next record')
            print('Hit D to delete record')
            print('Hit SPACE to exit data edit mode')
            print('Hit [ to decrease time until next click')
            print('Hit ] to increase time until next click')
            self.mode = 'data_edit'
            self.update()
            self.exit_edit_mode = False
            self.index = 0
            while self.index < len(self.screen_cap_buffer):
                image = self.screen_cap_buffer[self.index]
                root = tk.Tk()
                root.geometry('%dx%d+%d+%d' % (NETWORK_INPUT[0] + 1, NETWORK_INPUT[1] + 1, self.left_corner[0], self.left_corner[1]))
                canvas = tk.Canvas(root, width = NETWORK_INPUT[0], height = NETWORK_INPUT[1])
                canvas.pack()
                img = ImageTk.PhotoImage(image)
                canvas.create_image((NETWORK_INPUT[0] // 2), (NETWORK_INPUT[1] // 2), image=img)
                canvas.create_oval((self.click_buffer[self.index][0] / self.current_size[0]) * NETWORK_INPUT[0] - 3, (self.click_buffer[self.index][1] / self.current_size[1]) * NETWORK_INPUT[1] - 3, \
                        (self.click_buffer[self.index][0] / self.current_size[0]) * NETWORK_INPUT[0] + 3, (self.click_buffer[self.index][1] / self.current_size[1]) * NETWORK_INPUT[1] + 3)
                def key_press(e):
                    if e.char == 's':
                        print('Moving to next record')
                        root.destroy()
                    if e.char == ' ':
                        print('Exiting data edit mode')
                        self.exit_edit_mode = True
                        root.destroy()
                    if e.char == 'd':
                        print('Deleting record')
                        del self.screen_cap_buffer[self.index]
                        del self.click_buffer[self.index]
                        del self.click_time_buffer[self.index]
                        self.index -= 1
                        root.destroy()
                    if e.char == '[':
                        self.click_time_buffer[self.index] -= 1
                        print('New time until next click', self.click_time_buffer[self.index])
                    if e.char == ']':
                        self.click_time_buffer[self.index] += 1
                        print('New time until next click', self.click_time_buffer[self.index])
                def new_coords(e):
                    scaled_x = (e.x / NETWORK_INPUT[0]) * self.current_size[0]
                    scaled_y = (e.y / NETWORK_INPUT[1]) * self.current_size[1]
                    print('Click assigned to', (scaled_x, scaled_y))
                    self.click_buffer[self.index] = (scaled_x, scaled_y)
                    self.index -= 1
                    root.destroy()
                root.bind('<Key>', key_press)
                root.bind('<Button 1>', new_coords)
                shell.SendKeys('%')
                win32gui.SetForegroundWindow(root.winfo_id())
                print('Time until next click:', self.click_time_buffer[self.index])
                root.mainloop()
                if self.exit_edit_mode:
                    break
                self.index += 1
            print('Idle mode: ON')
            self.mode = 'idle'
        elif key == self.config['help']:
            self.print_help()
        self.update()

    def background_thread(self):
        while self.capture_on:
            if self.mode == 'control' or self.mode == 'record-control':
                cap = pyautogui.screenshot(region=(*self.left_corner, *self.current_size))
                processed_capture = cap.resize(NETWORK_INPUT)
                location, sleep_time = self.mouse_predictor.predict(processed_capture)
                print('Predicted location:', location)
                print('Predicted sleep time:', sleep_time)
                location_scaled = location[0] + self.left_corner[0], location[1] + self.left_corner[1]
                # If windmouse is off, auto move mouse to predicted location then back to original location
                if self.config['windmouse']:
                    wind_mouse(*pyautogui.position(), *location_scaled, move_mouse=self.move_mouse)
                    time.sleep((random.random() / 10) + 0.1)
                    pyautogui.click()
                else:
                    current_pos = pyautogui.position()
                    self.move_mouse(*location_scaled)
                    time.sleep((random.random() / 10) + 0.02)
                    pyautogui.click(*location_scaled)
                    self.move_mouse(*current_pos, False)
                time.sleep(sleep_time + EXTRA_SLEEP + random.random())
            else:
                time.sleep(0.1)
    
    def move_mouse(self, x, y, box_movement = True):
        if box_movement:
            x_dest, y_dest = self.box_movement(x, y)
        else:
            x_dest, y_dest = x, y
        x_conv = int(65535 * x_dest / x_size)
        y_conv = int(65535 * y_dest / y_size)
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE | win32con.MOUSEEVENTF_ABSOLUTE, x_conv, y_conv)

    # Prevents predicted mouse movements from going outside the application area
    def box_movement(self, x, y):
        new_x = min(max(self.left_corner[0], x), self.right_corner[0])
        new_y = min(max(self.left_corner[1], y), self.right_corner[1])
        return (new_x, new_y)

    # Returns true if inside capture window
    def in_capture_window(self, x, y):
        if x < self.left_corner[0] or x > self.right_corner[0]:
            return False
        if y < self.left_corner[1] or y > self.right_corner[1]:
            return False
        return True

    # Converts from full screen position to window relative position
    def full_to_window(self, position):
        p0 = min(max(position[0] - self.left_corner[0], 0), self.current_size[0] - 1)
        p1 = min(max(position[1] - self.left_corner[1], 0), self.current_size[1] - 1)
        return (p0, p1)

    # Paints application boarders
    def paintEvent(self, e):
        painter = QtGui.QPainter(self)
        if self.mode == 'data_edit':
            return
        elif self.mode == 'record':
            painter.setPen(QtCore.Qt.green)
        elif self.mode == 'control' or self.mode == 'record-control':
            painter.setPen(QtCore.Qt.yellow)
        else:
            painter.setPen(QtCore.Qt.red)
        painter.drawLine(0,0,0,self.current_size[1])
        painter.drawLine(0,0,self.current_size[0],0)
        painter.drawLine(self.current_size[0],0,self.current_size[0],self.current_size[1])
        painter.drawLine(0,self.current_size[1],self.current_size[0],self.current_size[1])

    def print_help(self):
        print('Keybinds can be set in config.txt')
        print(self.config['close'], '- close program')
        print(self.config['idle'], '- idle mode (does nothing)')
        print(self.config['record'], '- record mode')
        print(self.config['control'], '- control mode')
        print(self.config['record-control'], '- controls but also records clicks for training')
        print(self.config['train'], '- trains network on recorded data')
        print(self.config['load/save_network'], '- load or save current network')
        print(self.config['load/save_data'], '- load or save training data')
        print(self.config['new_network'], '- create new network with random weights')
        print(self.config['clear_recording'], '- deletes all training data')
        print(self.config['data_edit'], '- opens an interface to edit recorded data')
        print(self.config['help'], '- prints this message')

def find_window_then_resize_and_move(window_name, position, size):
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd == 0:
        print('Window with name', window_name, 'not found for auto moving/resizing')
        print('Window name can be set in config.txt')
        return None
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, *position, *size, win32con.SWP_SHOWWINDOW)
    print('Window with name', window_name, 'moved and resized successfully')

if __name__ == "__main__":
    conf_file = open('config.txt','r')
    config = json.loads(conf_file.read())
    app = QApplication([config])
    mainWin = ScreenOverlay(config)
    mainWin.show()
    mainWin.print_help()
    app.exec_()
    print('done')

