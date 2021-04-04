from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Flatten, Convolution2D, Input, Dense, MaxPooling2D
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import Sequence
import tensorflow as tf
import numpy as np
from PIL import Image
import math
import random

DEBUG = True
EPOCHS = 100
BATCH_SIZE = 100

def swap(a, b):
    return (b, a)

def process_screenshot(screenshot):
    screenshot = np.array(screenshot, dtype='float32') / 255.0
    return screenshot

# For mouse prediction

class Network:
    def __init__(self, capture_size, network_size, buffer_size, data_path):
        self.network_size = swap(*network_size)
        self.capture_size = swap(*capture_size)
        self.buffer_size = buffer_size
        self.data_path = data_path
        self.network = self.build_network()
        self.save('saves\\init_network')
        if DEBUG:
            self.network.summary()

    def build_network(self):
        image_mouse_input = Input(shape=(*self.network_size, 4*self.buffer_size), dtype='float32')
        self.max_click = 1
        click_input = Input(shape=(1), dtype='float32')
        scaled_cursor_position = Input(shape=(2), dtype='float32')
        x = Convolution2D(64, activation='relu', kernel_size=(5,5), strides=3)(image_mouse_input)
        x = Convolution2D(32, activation='relu', kernel_size=(4,4), strides=2)(x)
        x = Convolution2D(16, activation='relu', kernel_size=(3,3), strides=2)(x)
        x = Convolution2D(8, activation='relu', kernel_size=(3,3))(x)
        x = Flatten()(x)
        x = Dense(256, activation='relu')(x)
        y = tf.slice(image_mouse_input, (0,0,0,0), (-1, *self.network_size, 3*self.buffer_size))
        y = Convolution2D(64, activation='relu', kernel_size=(5,5), strides=3)(y)
        y = Convolution2D(32, activation='relu', kernel_size=(4,4), strides=2)(y)
        y = Convolution2D(16, activation='relu', kernel_size=(3,3), strides=2)(y)
        y = Convolution2D(8, activation='relu', kernel_size=(3,3))(y)
        y = Flatten()(y)
        y = Dense(256, activation='relu')(y)
        mouse_output = Dense(2, activation='linear')(x)
        click_prediction = Dense(2, activation='sigmoid')(y)
        z = tf.concat([click_prediction, click_input, scaled_cursor_position], axis=-1)
        z = tf.stop_gradient(z)
        x = tf.concat([y, z], axis=-1)
        x = Dense(256, activation='relu')(y)
        choice_output = Dense(1, activation='sigmoid')(x)
        m = Model(inputs=(image_mouse_input, click_input, scaled_cursor_position), outputs=(mouse_output, click_prediction, choice_output))
        m.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001), loss='mae', metrics=['acc'])
        return m

    def bin(self, positions):
        xbin = self.network_size[0] / self.capture_size[0]
        ybin = self.network_size[1] / self.capture_size[1]
        x = int(positions[0] * xbin)
        y = int(positions[1] * ybin)
        return (x,y)

    def convert_positions(self, positions):
        new_pos = np.zeros(shape=(*self.network_size, self.buffer_size), dtype='float32')
        i = 0
        for p in positions:
            b = self.bin(p)
            new_pos[b[1], b[0], i] = 1.0
            i += 1
        return new_pos
    
    def train(self, positions, movements, clicks):
        generator = BatchGenerator(self.network_size, self.buffer_size, BATCH_SIZE, self.capture_size, self.data_path, positions, movements, clicks, self.max_click)
        self.network.fit(generator, epochs=EPOCHS)

    # This predicts movement and target click position
    def predict(self, past_screen_caps, past_positions, time_last_click):
        assert(len(past_positions) == self.buffer_size)
        assert(len(past_screen_caps) == self.buffer_size)
        # Turn past_positions into a vector the size of network_size 
        converted = self.convert_positions(past_positions)
        stacked_images = []
        for x in past_screen_caps:
            stacked_images.append(process_screenshot(x))
        scaled_input = np.array([[past_positions[-1][0] / self.capture_size[1], past_positions[-1][1] / self.capture_size[0]]], dtype='float32')
        stacked_images = np.concatenate(stacked_images, axis=2)
        network_input = np.expand_dims(np.concatenate([stacked_images, converted], axis=2), 0)
        if time_last_click > self.max_click:
            self.max_click = time_last_click
        time_input = np.array([[time_last_click / self.max_click]], dtype='float32')
        network_output = self.network(inputs=(network_input, time_input, scaled_input))
        return [x.numpy()[0] for x in network_output]

    def save(self, network_path):
        self.network.save(network_path)

    def load(self, network_path):
        try:
            self.network = load_model(network_path)
            print('Successfully loaded network from', network_path)
        except:
            print('Error loading network')

    def new_network(self):
        self.load('saves\\init_network')

# Here, `data_path` is the directory with images
# and `movements` is a list of lists with each element being the target value
# Each training element has buffer_size images concatenated with converted positions and a single pair of target values

class BatchGenerator(Sequence):

    def __init__(self, network_size, buffer_size, batch_size, capture_size, data_path, positions, movements, clicks, max_click):
        self.network_size = network_size
        self.batch_size = batch_size
        self.capture_size = capture_size
        self.buffer_size = buffer_size
        self.data_path = data_path
        self.movements = movements
        self.positions = positions
        self.scaled_cursor_position = [[[f[0] / self.capture_size[1], f[1] / self.capture_size[0]] for f in session] for session in self.positions]
        self.click_inputs = []
        self.click_positions = []
        self.choice_label = []
        for session in clicks:
            temp_inputs = []
            temp_positions = []
            temp_choice = []
            last_click = 0
            for click in session:
                for x in range(click[0] - last_click):
                    temp_inputs.append(x / max_click)
                    temp_positions.append(self.normalize(click[1]))
                    if x == 0 and last_click != 0:
                        temp_choice.append(1)
                    else:
                        temp_choice.append(x/(click[0] - last_click))
                last_click = click[0]
            self.click_inputs.append(temp_inputs)
            self.click_positions.append(temp_positions)
            self.choice_label.append(temp_choice)
        self.absolute_sum = []
        sum_len = 0
        for session in self.click_inputs:
            # The first buffer_size elements cannot be used because the buffer isn't fully filled yet
            # The last element cannot be used because it doesn't have a target value
            sum_len += len(session) - (buffer_size + 1)
            self.absolute_sum.append(sum_len)
        self.indices = list(range(self.absolute_sum[-1]))

    # CAPTURE_SIZE IS SWAPPED ON INPUT!
    def normalize(self, position):
        x = position[0] / self.capture_size[1]
        y = position[1] / self.capture_size[0]
        return (x, y)

    def bin(self, positions):
        xbin = self.network_size[0] / self.capture_size[0]
        ybin = self.network_size[1] / self.capture_size[1]
        x = int(positions[0] * xbin)
        y = int(positions[1] * ybin)
        return (x, y)

    def convert_absolute(self, absolute_value):
        index_session = 0
        for cur_sum in self.absolute_sum:
            if cur_sum >= absolute_value:
                break
            index_session += 1
        if index_session != 0:
            index = absolute_value - self.absolute_sum[index_session - 1]
        else:
            index = absolute_value
        return index_session, index + self.buffer_size

    def build_network_input(self, images, positions):
        new_pos = np.zeros(shape=(*self.network_size, self.buffer_size), dtype='float32')
        i = 0
        for p in positions:
            b = self.bin(p)
            new_pos[b[1], b[0], i] = 1.0
            i += 1
        stacked = []
        for x in images:
            stacked.append(process_screenshot(x))
        stacked = np.concatenate(stacked, axis=2)
        network_input = np.concatenate([stacked, new_pos], axis=2)
        return network_input

    def on_epoch_end(self):
        random.shuffle(self.indices)

    def __len__(self):
        return math.ceil(self.absolute_sum[-1] / self.batch_size)

    def __getitem__(self, idx):
        indices = self.indices[idx * self.batch_size:(idx + 1) * self.batch_size]
        batch_images = []
        batch_clicks = []
        batch_scaled_position = []
        batch_movements = []
        batch_future_clicks = []
        batch_choices = []
        for element in indices:
            session, index = self.convert_absolute(element)
            images = [Image.open(self.data_path + str(session) + '\\' + str(index - x) + '.jpg') for x in reversed(range(1, self.buffer_size + 1))]
            batch_images.append(self.build_network_input(images, self.positions[session][index - self.buffer_size : index]))
            batch_scaled_position.append(self.scaled_cursor_position[session][index - 1])
            batch_clicks.append(self.click_inputs[session][index])
            batch_movements.append(self.movements[session][index])
            batch_future_clicks.append(self.click_positions[session][index])
            batch_choices.append(self.choice_label[session][index])
        return (np.array(batch_images, dtype='float32'), np.array(batch_clicks, dtype='float32'), np.array(batch_scaled_position, dtype='float32')), \
                (np.array(batch_movements, dtype='float32'), np.array(batch_future_clicks, dtype='float32'), np.array(batch_choices, dtype='float32'))