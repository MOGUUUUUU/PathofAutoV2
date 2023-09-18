import os
import time
import pyautogui
import random
import win32gui
import pyperclip


r = lambda : random.uniform(0.01, 0.02)

def open_poe(wld_name="Path of Exile"):
    hld = win32gui.FindWindow(None, wld_name)
    win32gui.SetForegroundWindow(hld)
    

def safe_get_info(limit=5):
    text = pyperclip.paste()
    times = 0
    while (len(text) and times < limit):
        os.system('echo off | clip')
        text = pyperclip.paste()
        wait()
        times = times + 1
    times = 0
    while len(text) == 0 and times < limit:
        pyautogui.hotkey('ctrl', 'c', interval=r())
        text = pyperclip.paste()
        wait()
        times = times + 1
    return text


def get_position_args(filepath='db/position.txt'):
    positions = {}
    with open(filepath, 'r', encoding='utf-8') as fp:
        for line in fp:
            ll = line.strip()
            key, value = ll.split()
            positions[key] = value
    return positions


def get_grid_positions(start_pos, end_pos, row_lines, col_lines):
    per_width = (end_pos[0] - start_pos[0]) / col_lines
    per_height = (end_pos[1] - start_pos[1]) / row_lines
    
    grid_positions = []
    xx, yy = start_pos
    for ii in col_lines:
        for jj in row_lines:
            grid_positions.append((xx,yy))
            yy += per_height
        xx += per_width
        yy = start_pos[1]
    return grid_positions


def safe_move_to(position):
    xx = position[0]
    yy = position[1]
    
    xx = random.randint((int)(xx-1), (int)(xx+1))
    yy = random.randint((int)(yy-1), (int)(yy+1))
    
    pyautogui.moveTo((xx,yy), duration=0.02+r())
    wait()
    
    
def safe_move(position):
    xx = position[0]
    yy = position[1]
    
    xx = random.randint((int)(xx-1), (int)(xx+1))
    yy = random.randint((int)(yy-1), (int)(yy+1))
    
    pyautogui.move((xx, yy), duration=0.02+r())
    wait()


def safe_check_target(info=safe_get_info(), needs=[]):
    for need in needs:
        if need in info:
            return True
    return False


def safe_click(button='left'):
    pyautogui.click(button=button, duration=r())
    wait()
    

def safe_double_click(button='left'):
    pyautogui.doubleClick(button=button, duration=r())
    wait()
    

def safe_type(string):
    pyautogui.typewrite(str(string), interval=r())
    wait()


def safe_store():
    
        
def wait(base=r()):
    time.sleep(base)
    