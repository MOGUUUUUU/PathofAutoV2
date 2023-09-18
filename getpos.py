import pyautogui

print(pyautogui.position())

times = 71
subs = [30]*(times//30) + [times%30]
print(subs)