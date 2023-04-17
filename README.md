## Machine learning mouse clicker version 0.3  

### How to use  

- Use record mode to capture the screen and mouse position each time you click
- Train the model with the recorded data
- Let the model do the work, copying where and when to click based on your gameplay

### What is working?  

- The network is fully functional and can be trained to play RuneScape!

### What isn't working?

- The network can only predict left clicks so any tasks that require right clicks or shift clicks won't work
- Currently only support for Windows
- The network architecture could be more efficient

### Help my model isn't converging

- Use the data edit mode to confirm all the click locations are correct, edit or delete incorrect clicks
- Record more data (I recommend at least 5 samples of each click location)
- Reset the network weights (sometimes initial weights get stuck in a local minimum)
- Increase the number of epochs
- Change the learning rate
- Change the model architecture

### Installation

```
pip3 install -r requirements.txt
```

### Special thanks

- Ben Land for his algorithm WindMouse

### Disclosure

- I do not endorse cheating. This is a passion project of mine
- Cheating in any game is a bannable offense
- I am not responsible any bans that may occur from using this program, so use at your own risk!

### Example GIF

- Model was trained on a few laps of agility

![hippo](https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMTJhZDBjNGEyNjRhNGY4OGQxOTk1MjQ2ZGFjZjlkZWVjMWQ2NTQ5MCZjdD1n/YyhcPW1dzRpOekaE6D/giphy.gif)
