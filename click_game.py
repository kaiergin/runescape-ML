from tkinter import *

WINDOW_SIZE = (800,600)

root = Tk()
canvas= Canvas(root, width=WINDOW_SIZE[0], height=WINDOW_SIZE[1])

click_positions = [(100, 100), (WINDOW_SIZE[0] - 100, WINDOW_SIZE[1] - 100), (100, WINDOW_SIZE[1] - 100), (WINDOW_SIZE[0] - 100, 100)]
cur_position = 0

def draw_circle(pos):
    global canvas
    canvas.delete('all')
    canvas.create_oval(pos[0] - 10, pos[1] - 10, pos[0] + 10, pos[1] + 10, fill='green')

draw_circle(click_positions[cur_position])

def callback(event):
    global cur_position
    global click_positions
    print("clicked at", event.x, event.y)
    if abs(event.x - click_positions[cur_position][0]) <= 10 and abs(event.y - click_positions[cur_position][1]) <= 10:
        cur_position += 1
        if cur_position >= len(click_positions):
            cur_position = 0
        draw_circle(click_positions[cur_position])

        

canvas.bind("<Button-1>", callback)
canvas.pack()

root.mainloop()