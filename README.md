## Machine learning mouse clicker version 0.3  

### How to use  

- Choose a repetative task that requires left clicking in the same locations (agility in RuneScape works well)
- Use record mode to capture the screen and mouse position each time you click
- Train the model with the recorded data
- Let the model do the work, copying where and when to click based on your gameplay

### Setup / Installation

- Download the repo
- Install the latest version of python (I personally use the Anaconda command line)
- CD into the project directory
- Install requirements using pip3
```
pip3 install -r requirements.txt
```
- Might need to install tensorflow separately, I also recommend CUDA for GPU support which makes training faster (pretty sure this requires the tensorflow-gpu package)
- Run main.py to start the program
```
python main.py
```

### Notes / Recommendations

- Set the name of the RuneScape client window in config.txt. If using RuneLite, start this program before logging in so that the client is always moved/resized into the same position (logging in changes the window name)
- Disable the f keys in the RuneScape client. The f keys are used for controlling the program but they also change which tab is currently selected in the game. If the tab selected is different in recording vs training, it will impact where the predicted clicks are
- Make sure mse is close to 0 after training. If dense_1_mse or dense_2_mse is anywhere near 0.1, then the model isn't converging. If the model doesn't converge, I highly recommend wiping the network and retraining with different starting weights
- Keep in mind that while recording data, the last recorded click will always be discarded (since each label requires a sleep time until the next click)
- Closing/minimizing other programs while training will speed up the training process

### Help my model isn't converging

- Reset the network weights (default key f8, sometimes initial weights get stuck in a local minimum)
- Use the data edit mode to confirm all the click locations are correct, edit or delete incorrect clicks (default key f10)
- Record more data (I recommend at least 5 samples of each click location)
- Other parameters that could help convergence
    - Change the number of epochs
    - Change the learning rate
    - Change the model architecture

### Future improvements (ways to contribute)

- The network can only predict left clicks - add support for right clicks and shift clicks
- Add support for other platforms (Currently only support for Windows)
- Improve the model's architecture and efficiency
- The entire problem can probably be simplified by removing ML from the solution
    - Instead of using CNN to guess click positions, use K-means clustering to cluster all the recorded click positions
    - Modify the data edit mode for confirming that all clusters are correct
    - Each time a screenshot is taken, do image comparison to find a past screenshot that has the highest match %
    - Choose a click location inside the cluster for the matching image
- Give the model more information on the state of the task (last click position)
    - Currently, the only way to differentiate between states is the screenshot
    - Sometimes different states of a task look identical in screenshots
    - Example: woodcutting in the same spot. After dropping a log, the screenshot will look identical to when you are still chopping. So the script won't be able to differentiate if it should continue dropping logs or start to chop again

### Special thanks

- Ben Land for his algorithm WindMouse

### Disclosure

- I do not endorse cheating. This is a passion project of mine
- Cheating in any game is a bannable offense
- I am not responsible any bans that may occur from using this program, so use at your own risk!

### Example GIF

- Model was trained on a few laps of agility

![hippo](https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMTJhZDBjNGEyNjRhNGY4OGQxOTk1MjQ2ZGFjZjlkZWVjMWQ2NTQ5MCZjdD1n/YyhcPW1dzRpOekaE6D/giphy.gif)
