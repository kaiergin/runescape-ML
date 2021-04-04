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
import os
import shutil
import random
import tkinter as tk
from tkinter import filedialog

x_size = win32api.GetSystemMetrics(0)
y_size = win32api.GetSystemMetrics(1)

# Constants (temporary)

DEBUG = False
BUFFER_SIZE = 2
NETWORK_INPUT = (200,150)
# Filler mouse movements for each movement vector
MOUSE_FILL = 6
USE_PREDICTED_CLICK = True
IMAGE_DIR = 'captures\\'
SAVE_DIR = 'saves\\'

# For window and main loop

class ScreenOverlay(QMainWindow):
    def __init__(self, config):
        super().__init__()

        self.config = config
        self.mode = 'idle'
        self.idle_on = True # to be used for discard_last_10_seconds without having to be in idle mode
        self.draw_predictions = False

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
        
        self.next_move_available = False
        self.position = (0,0)
        self.movement = (0,0)
        self.predicted_movement = (0,0)
        self.choice = 0
        self.predicted_click = (0,0)
        self.position_buffer = []
        self.movement_buffer = []
        self.click_buffer = []
        self.click_control_buffer = []
        self.average_time = 0
        self.cur_index = 0
        self.cur_session = -1
        self.max_time_last_click = 0
        self.creating_new_session = False
        try:
            os.mkdir(os.path.join(IMAGE_DIR))
        except OSError:
            shutil.rmtree(os.path.join(IMAGE_DIR))
            os.mkdir(os.path.join(IMAGE_DIR))
        
        self.current_save_path = 'none'
        try:
            os.mkdir(os.path.join(SAVE_DIR))
        except OSError:
            pass

        self.setMinimumSize(QtCore.QSize(*self.current_size))
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.mouse_predictor = Network(self.current_size, NETWORK_INPUT, BUFFER_SIZE, IMAGE_DIR)

        self.capture_on = True

        keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        keyboard_listener.start()
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        threading.Thread(target=self.background_thread, daemon=True).start()
        threading.Thread(target=self.mouse_mover, daemon=True).start()
    
    def on_click(self, x, y, button, pressed):
        if DEBUG:
            print('{0} at {1}'.format('Pressed' if pressed else 'Released', (x, y)))
        if self.mode == 'record':
            if pressed and (button == mouse.Button.left or button == mouse.Button.right):
                self.click_buffer[self.cur_session].append((self.cur_index, self.full_to_window((x, y)), 'right' if button == mouse.Button.right else 'left'))
        if self.mode == 'control':
            if pressed and (button == mouse.Button.left or button == mouse.Button.right):
                self.click_control_buffer.append((self.cur_index, self.full_to_window((x, y)), 'right' if button == mouse.Button.right else 'left'))
        if not self.capture_on:
            # Stop listener
            return False

    def on_press(self, key):
        if DEBUG:
            try:
                print('alphanumeric key {0} pressed'.format(key.char))
            except AttributeError:
                print('special key {0} pressed'.format(key))

    def new_control_session(self):
        self.cur_index = 0
        self.click_control_buffer = []

    def new_session(self):
        if len(self.position_buffer) > 0 and len(self.position_buffer[self.cur_session]) < BUFFER_SIZE + 2:
            self.position_buffer.pop(-1)
            self.movement_buffer.pop(-1)
            shutil.rmtree(os.path.join(IMAGE_DIR, str(self.cur_session)))
        else:
            self.cur_session += 1
        self.cur_index = 0
        self.position_buffer.append([])
        self.movement_buffer.append([])
        self.click_buffer.append([])
        os.mkdir(os.path.join(IMAGE_DIR, str(self.cur_session)))
        self.creating_new_session = True

    def new_recording(self):
        shutil.rmtree(os.path.join(IMAGE_DIR))
        os.mkdir(os.path.join(IMAGE_DIR))
        self.cur_session = -1
        self.position_buffer = []
        self.movement_buffer = []
        self.click_buffer = []
        self.total_size = 0
        self.creating_new_session = True

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
        elif key == self.config['prediction']:
            if self.draw_predictions:
                print('Draw predictions: OFF')
                self.draw_predictions = False
            else:
                print('Draw predictions: ON')
                self.draw_predictions = True
        elif key == self.config['record']:
            if self.mode == 'record':
                print('Starting new session')
            else:
                print('Record mode: ON')
            self.new_session()
            self.mode = 'record'
        elif key == self.config['control']:
            print('Control mode: ON')
            self.new_control_session()
            self.mode = 'control'
        elif key == self.config['idle']:
            print('Recording/Controlling: OFF')
            self.mode = 'idle'
        elif key == self.config['train']:
            print('Training mode: ON')
            self.mode = 'training'
        elif key == self.config['save_network']:
            if not self.idle_on:
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
            if not self.idle_on:
                print('You must be in idle mode to load a network, press', self.config['idle'], 'then try again')
            else:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askdirectory(initialdir=SAVE_DIR, title='Select network folder')
                self.mouse_predictor.load(file_path)
        elif key == self.config['new_network']:
            if not self.idle_on:
                print('You must be in idle mode to create a new network, press', self.config['idle'], 'then try again')
            else:
                print('Creating new network, wiping loaded weights')
                self.current_save_path = 'none'
                self.new_recording()
                self.mouse_predictor.new_network()
        elif key == self.config['discard_training_data']:
            if not self.idle_on:
                print('You must be in idle mode to clear training data, press', self.config['idle'], 'then try again')
            else:
                self.new_recording()
        elif key == self.config['help']:
            self.print_help()

    def mouse_mover(self):
        while self.capture_on:
            if self.next_move_available:
                if USE_PREDICTED_CLICK:
                    predicted_length = np.sqrt(pow(self.predicted_movement[0], 2) + pow(self.predicted_movement[1], 2))
                    correction0 = self.position[0] - self.predicted_click[0] * self.current_size[0]
                    correction1 = self.position[1] - self.predicted_click[1] * self.current_size[1]
                    correction_length = np.sqrt(pow(correction0, 2) + pow(correction1, 2))
                    new_direction0 = predicted_length * ((self.predicted_movement[0] / predicted_length) + (correction0 / correction_length)) / 2
                    new_direction1 = predicted_length * ((self.predicted_movement[1] / predicted_length) + (correction1 / correction_length)) / 2
                    self.move_mouse(-1 * int(new_direction0), -1 * int(new_direction1))
                else:
                    self.move_mouse(-1 * int(self.predicted_movement[0]), -1 * int(self.predicted_movement[1]))
                if self.choice > 0.99 or self.time_last_click == self.max_time_last_click:
                    pyautogui.mouseDown()
                    pyautogui.mouseUp()
                self.next_move_available = False
            else:
                time.sleep(0.001)
    
    def move_mouse(self, x, y):
        xi = x // MOUSE_FILL
        yi = y // MOUSE_FILL
        xr = np.random.choice(MOUSE_FILL, x % MOUSE_FILL)
        yr = np.random.choice(MOUSE_FILL, y % MOUSE_FILL)
        for i in range(MOUSE_FILL): 
            start_time = time.perf_counter()
            xr_in = i in xr
            yr_in = i in yr
            x_pos, y_pos = win32gui.GetCursorInfo()[2]
            x_dest = x_pos + xi + 1
            y_dest = y_pos + yi + 1
            if xr_in:
                x_dest += 1
            if yr_in:
                y_dest += 1
            if x_dest == 0 and y_dest == 0:
                continue
            x_dest, y_dest = self.box_movement(x_dest, y_dest)
            #print('next dest', x_dest, y_dest)
            x_conv = int(65535 * x_dest / x_size)
            y_conv = int(65535 * y_dest / y_size)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE | win32con.MOUSEEVENTF_ABSOLUTE, x_conv, y_conv)
            time_taken = time.perf_counter() - start_time
            #time.sleep(max((self.average_time / MOUSE_FILL) - time_taken, 0) * .8)

    # Prevents predicted mouse movements from going outside the application area
    def box_movement(self, x, y):
        new_x = min(max(self.left_corner[0], x), self.right_corner[0])
        new_y = min(max(self.left_corner[1], y), self.right_corner[1])
        return (new_x, new_y)

    def background_thread(self):
        past_positions = []
        past_screen_caps = []
        total_time = 0
        time_buffer = []
        movement_vectors = []
        # This value should be imported at a later time
        max_movement = 0
        while self.capture_on:
            # Wipe local variables on start of new session
            if self.creating_new_session:
                self.creating_new_session = False
                past_positions = []
                past_screen_caps = []
                total_time = 0
                time_buffer = []
                movement_vectors = []
            
            if self.mode == 'idle':
                self.update()
                self.idle_on = True
                time.sleep(0.5)
                continue
            else:
                self.idle_on = False
            
            if self.mode == 'training':
                self.update()
                self.mouse_predictor.train(self.position_buffer, self.movement_buffer, self.click_buffer)
                print('Training complete press', config['record'], 'to begin recording or', config['control'], 'to allow for control')
                self.mode = 'idle'
            else: # record mode or control mode
                last_time = time.perf_counter()
                # Mouse position
                self.position = self.full_to_window(win32gui.GetCursorInfo()[2])
                past_positions.append(self.position)
                # Screen capture
                cap = pyautogui.screenshot(region=(*self.left_corner, *self.current_size))
                processed_capture = cap.resize(NETWORK_INPUT)
                past_screen_caps.append(processed_capture)
                # Can only calculate movement if we already already have past position recorded
                if len(past_positions) > 1:
                    self.movement = (past_positions[-2][0] - self.position[0], past_positions[-2][1] - self.position[1])
                    movement_vectors.append(self.movement)
                    # For clipping predicted values
                    current_max = max(abs(self.movement[0]), abs(self.movement[1]))
                    if current_max > max_movement:
                        max_movement = current_max
                    if self.mode == 'record':
                        try:
                            processed_capture.save(IMAGE_DIR + str(self.cur_session) + '\\' + str(self.cur_index) + '.jpg')
                        except:
                            self.mode = 'idle'
                            print('Memory limit reached. Start training using', config['train'])
                        self.position_buffer[self.cur_session].append(self.position)
                        self.movement_buffer[self.cur_session].append(self.movement)
                    self.cur_index += 1
                # Release oldest capture
                if len(past_positions) > BUFFER_SIZE:
                    past_positions.pop(0)
                    past_screen_caps.pop(0)
                    movement_vectors.pop(0)
                    total_time -= time_buffer.pop(0)
                    self.average_time = total_time / BUFFER_SIZE
                    if self.mode == 'record':
                        if len(self.click_buffer[self.cur_session]) == 0:
                            self.time_last_click = self.cur_index
                        else:
                            self.time_last_click = self.cur_index - self.click_buffer[self.cur_session][-1][0]
                    else: # control mode
                        if len(self.click_control_buffer) == 0:
                            self.time_last_click = self.cur_index
                        else:
                            self.time_last_click = self.cur_index - self.click_control_buffer[-1][0]
                    if self.time_last_click > self.max_time_last_click:
                        self.max_time_last_click = self.time_last_click
                    # Predict based on current capture
                    self.predicted_movement, self.predicted_click, self.choice = self.mouse_predictor.predict(past_screen_caps, past_positions, self.time_last_click)
                    print('Predicted movement:', self.predicted_movement, 'Predicted choice', self.choice, 'Predicted click', self.predicted_click)
                    self.predicted_movement = self.config['prediction_scale'] * np.clip(self.predicted_movement, -1 * max_movement, max_movement)
                    self.update()
                    if DEBUG:
                        print(self.predicted_movement)
                    if self.mode == 'control':
                        # Move mouse using the predicted vector
                        self.next_move_available = True
                difference = time.perf_counter() - last_time
                total_time += difference
                time_buffer.append(difference)  

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
        clipped0 = np.clip(self.position[0] - int(self.predicted_movement[0]), 0, self.current_size[0])
        clipped1 = np.clip(self.position[1] - int(self.predicted_movement[1]), 0, self.current_size[1])
        if self.draw_predictions:
            painter.setPen(QtCore.Qt.yellow)
            painter.drawEllipse(self.position[0] - 5, self.position[1] - 5, 10, 10)
            predicted_length = np.sqrt(np.square(self.predicted_movement[0]) + np.square(self.predicted_movement[1]))
            if predicted_length > 5:
                painter.setPen(QtGui.QColor(255,160,0))
                move0 = 5 * (self.predicted_movement[0] / predicted_length)
                move1 = 5 * (self.predicted_movement[1] / predicted_length)
                painter.drawLine(self.position[0] - move0, self.position[1] - move1, clipped0, clipped1)
            movement_length = np.sqrt(np.square(self.movement[0]) + np.square(self.movement[1]))
            if movement_length > 5:
                painter.setPen(QtGui.QColor(255,160,0))
                move0 = 5 * (self.movement[0] / movement_length)
                move1 = 5 * (self.movement[1] / movement_length)
                painter.drawLine(self.position[0] + move0, self.position[1] + move1, self.position[0] + self.movement[0], self.position[1] + self.movement[1])
            painter.setPen(QtGui.QColor(128,0,255))
            painter.drawEllipse(int(self.predicted_click[0] * self.current_size[0]) - 5, int(self.predicted_click[1] * self.current_size[1]) - 5, 10, 10)

    def print_help(self):
        print('Keybinds can be set in config.txt')
        print(self.config['close'], '- close program')
        print(self.config['prediction'], '- show predictions')
        print(self.config['record'], '- record mode')
        print(self.config['control'], '- control mode')
        print(self.config['idle'], '- idle mode (does nothing)')
        print(self.config['save_network'], '- save current network')
        print(self.config['load_network'], '- load a saved network')
        print(self.config['new_network'], '- create new network')
        print(self.config['discard_last_session'], '- discards the last session (since last press of', config['record'] + ') [NOT IMPLEMENTED]')
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

