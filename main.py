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
import pyautogui
import threading
import numpy as np
from predict import Network
import shutil
import random
import tkinter as tk
from tkinter import filedialog
from mousepath import wind_mouse

x_size = win32api.GetSystemMetrics(0)
y_size = win32api.GetSystemMetrics(1)

# Constants

DEBUG = False
NETWORK_INPUT = (400,300)
RIGHT_CLICK = 0
LEFT_CLICK = 1
SAVE_DIR = 'scripts\\'
EXTRA_SLEEP = 2

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
        self.screen_size = (x_size, y_size)
        self.left_corner = self.config['left_corner']
        self.move(*self.left_corner)
        self.right_corner = (self.left_corner[0] + self.current_size[0], self.left_corner[1] + self.current_size[1])
        self.setMinimumSize(QtCore.QSize(*self.current_size))
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

    def clear_last_capture(self):
        print('Clearing previous capture')
        if self.last_click_time == None:
            if len(self.click_time_buffer) > 0:
                self.click_buffer.pop()
                self.screen_cap_buffer.pop()
                self.click_time_buffer.pop()
        self.last_click_time = None
        self.last_click_location = None
        self.last_screen_capture = None

    def new_recording(self):
        self.click_buffer = []
        self.screen_cap_buffer = []
        self.click_time_buffer = []
        self.clear_last_capture()

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
            if self.mode == 'record':
                if pressed and (button == mouse.Button.left or button == mouse.Button.right):
                    click = self.full_to_window((x, y))#, RIGHT_CLICK if button == mouse.Button.right else LEFT_CLICK
                    cap = pyautogui.screenshot(region=(*self.left_corner, *self.current_size))
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
            self.mode = 'idle'
        elif key == self.config['train']:
            print('Starting training')
            self.mode = 'training'
            self.mouse_predictor.train(self.screen_cap_buffer, self.click_buffer, self.click_time_buffer)
        elif key == self.config['save_network']:
            if self.mode != 'idle':
                print('You must be in idle mode to save a network, press', self.config['idle'], 'then try again')
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
        elif key == self.config['load_network']:
            if self.mode != 'idle':
                print('You must be in idle mode to load a network, press', self.config['idle'], 'then try again')
            else:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askdirectory(initialdir=SAVE_DIR, title='Select network folder')
                self.mouse_predictor.load(file_path)
        elif key == self.config['new_network']:
            if self.mode != 'idle':
                print('You must be in idle mode to create a new network, press', self.config['idle'], 'then try again')
            else:
                print('Creating new network, wiping loaded weights')
                self.current_save_path = 'none'
                self.new_recording()
                self.mouse_predictor.new_network()
        elif key == self.config['clear_recording']:
            if self.mode != 'idle':
                print('You must be in idle mode to clear training data, press', self.config['idle'], 'then try again')
            else:
                print('Clearing data')
                self.new_recording()
        elif key == self.config['help']:
            self.print_help()
        elif key == self.config['modify_learning_rate']:
            print('Enter a new learning rate')
            stdinput = input('>')
            try:
                new_learning_rate = float(stdinput)
                self.mouse_predictor.update_learning_rate(new_learning_rate)
            except:
                print('Invalid learning rate, not a float')
        elif key == self.config['modify_epochs']:
            print('Enter a new # of epochs')
            stdinput = input('>')
            try:
                new_epochs = int(stdinput)
                self.mouse_predictor.update_epochs(new_epochs)
            except:
                print('Invalid epochs, not an int')

    def background_thread(self):
        while self.capture_on:
            if self.mode == 'control':
                cap = pyautogui.screenshot(region=(*self.left_corner, *self.current_size))
                processed_capture = cap.resize(NETWORK_INPUT)
                location, sleep_time = self.mouse_predictor.predict(processed_capture)
                print('Predicted location:', location)
                print('Predicted sleep time:', sleep_time)
                location_scaled = location[0] + self.left_corner[0], location[1] + self.left_corner[1]
                wind_mouse(*pyautogui.position(), *location_scaled, move_mouse=self.move_mouse)
                pyautogui.click()
                time.sleep(max(sleep_time + EXTRA_SLEEP + random.random(), 1))
            else:
                time.sleep(0.1)
    
    def move_mouse(self, x, y):
        x_dest, y_dest = self.box_movement(x, y)
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
        if self.mode == 'record':
            painter.setPen(QtCore.Qt.green)
        elif self.mode == 'control':
            painter.setPen(QtCore.Qt.yellow)
        else:
            painter.setPen(QtCore.Qt.red)
        painter.drawLine(0,0,0,self.current_size[1]-1)
        painter.drawLine(0,0,self.current_size[0]-1,0)
        painter.drawLine(self.current_size[0],0,self.current_size[0]-1,self.current_size[1]-1)
        painter.drawLine(0,self.current_size[1]-1,self.current_size[0]-1,self.current_size[1]-1)

    def print_help(self):
        print('Keybinds can be set in config.txt')
        print(self.config['close'], '- close program')
        print(self.config['idle'], '- idle mode (does nothing)')
        print(self.config['record'], '- record mode (also deletes last recorded click)')
        print(self.config['control'], '- control mode')
        print(self.config['record-control'], '- controls but also records clicks for training')
        print(self.config['train'], '- trains network on recorded data')
        print(self.config['save_network'], '- save current network')
        print(self.config['load_network'], '- load a saved network')
        print(self.config['new_network'], '- create new network')
        print(self.config['clear_recording'], '- deletes all training data')
        print(self.config['modify_learning_rate'], '- updates learning rate of network (default 0.0001)')
        print(self.config['modify_epochs'], '- updates the number of epochs during learning (default 1000)')
        print(self.config['help'], '- prints this message')

if __name__ == "__main__":
    conf_file = open('config.txt','r')
    config = json.loads(conf_file.read())
    app = QApplication([config])
    mainWin = ScreenOverlay(config)
    mainWin.show()
    mainWin.print_help()
    app.exec_()
    print('done')

