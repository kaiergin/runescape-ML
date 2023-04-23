from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Flatten, Convolution2D, Input, Dense
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import backend
import tensorflow as tf
import numpy as np
from PIL import ImageFilter

MAX_WAIT_TIME = 15
LEARNING_RATE = 0.0001
EPOCHS = 200
DEBUG = True

def swap(a, b):
    return (b, a)

def process_screenshot(screenshot):
    screenshot = screenshot.filter(ImageFilter.BLUR)
    screenshot = np.array(screenshot, dtype='float32') / 255.0
    return screenshot

# For mouse prediction

class Network:
    def __init__(self, capture_size, network_size):
        self.network_size = swap(*network_size)
        self.capture_size = capture_size
        self.network = self.build_network()
        self.epochs = EPOCHS
        if DEBUG:
            print('Network size ', network_size)
            print('Capture size ', capture_size)
            self.network.summary()

    def build_network(self):
        image_input = Input(shape=(*self.network_size, 3), dtype='float32')
        x = Convolution2D(64, activation='relu', padding='same', kernel_size=(5,5), strides=3)(image_input)
        x = Convolution2D(32, activation='relu', padding='same', kernel_size=(4,4), strides=2)(x)
        x = Convolution2D(16, activation='relu', padding='same', kernel_size=(3,3), strides=2)(x)
        x = Convolution2D(8, activation='relu', padding='same', kernel_size=(3,3))(x)
        x = Flatten()(x)
        x = Dense(256, activation='relu')(x)
        coords = Dense(2, activation='relu')(x)
        wait_time = Dense(1, activation='relu')(x)
        m = Model(inputs=(image_input), outputs=(coords, wait_time))
        m.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE), loss='mse', metrics=['mse'])
        return m
    
    def train(self, screen_caps, click_positions, timeouts):
        inputs = [process_screenshot(x) for x in screen_caps]
        click_positions = [(x[0] / self.capture_size[0], x[1] / self.capture_size[1]) for x in click_positions]
        timeouts = [min(x, MAX_WAIT_TIME) / MAX_WAIT_TIME for x in timeouts]
        self.network.fit(x=np.array(inputs), y=(np.array(click_positions), np.array(timeouts)), epochs=self.epochs)

    # This predicts target click position and how long to wait until next click
    def predict(self, screen_cap):
        screen_cap = np.array([process_screenshot(screen_cap)])
        network_output = self.network(inputs=(screen_cap))
        click_locs, wait_time = [x.numpy()[0] for x in network_output]
        click_locs = min(click_locs[0] * self.capture_size[0], self.capture_size[0]), min(click_locs[1] * self.capture_size[1], self.capture_size[1])
        wait_time = min(wait_time[0] * MAX_WAIT_TIME, MAX_WAIT_TIME)
        return click_locs, wait_time

    def save(self, network_path):
        self.network.save(network_path)

    def load(self, network_path):
        try:
            self.network = load_model(network_path)
            print('Successfully loaded network from', network_path)
        except:
            print('Error loading network')

    def update_learning_rate(self, new_learning_rate):
        backend.set_value(self.network.optimizer.learning_rate, new_learning_rate)
    
    def update_epochs(self, new_epochs):
        self.epochs = new_epochs

    def new_network(self):
        reinitialize(self.network)

def reinitialize(model):
    for ix, layer in enumerate(model.layers):
        if hasattr(model.layers[ix], 'kernel_initializer') and \
                hasattr(model.layers[ix], 'bias_initializer'):
            weight_initializer = model.layers[ix].kernel_initializer
            bias_initializer = model.layers[ix].bias_initializer

            old_weights, old_biases = model.layers[ix].get_weights()

            model.layers[ix].set_weights([
                weight_initializer(shape=old_weights.shape),
                bias_initializer(shape=len(old_biases))])