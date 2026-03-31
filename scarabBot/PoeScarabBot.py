import pyautogui
import random
from executor import Executor

et = Executor()

class Scarab:
    def __init__(self, name=None, price=None, position=None, num=None):
        self.name = name
        self.price = price if price is not None else float('inf')
        self.position = position
        self.num = num

    def update_price(self, price):
        if price < self.price:
            self.price = price

def get_name_from_info(info):
    pass
def get_num_from_info(info):
    pass
class ScarabList:
    def __init__(self):
        self.scarabs = {}

    def get_scarab_by_name(self, name):
        return self.scarabs.get(name)

    def filter_lower_price_scarab(self, threshold):
        return [scarab for scarab in self.scarabs.values() if scarab.price < threshold]

    def update_scarab(self, start_pos, end_pos, dimension=(10, 10)):
        x_start, y_start = start_pos
        x_end, y_end = end_pos
        step_x, step_y = dimension

        for ii in range(x_start, x_end, step_x):
            for jj in range(y_start, y_end, step_y):  
                info = et.get_item_info((ii, jj))
                if not info.strip():
                    continue  

                lines = info.strip().split('\n')
                name = get_name_from_info(info)  # TODO: get real name
                num = get_num_from_info(info)                           # TODO: get real number

                if name not in self.scarabs:
                    self.scarabs[name] = Scarab(name=name, position=(ii, jj), num=num)
                else:
                    continue

    def update_scarab_price(self, price_fetcher_func):
        """
        Update prices for all scarabs using a provided price-fetching function.
        
        :param price_fetcher_func: A function that takes scarab name and returns price (float).
        """
        if not self.scarabs:
            raise ValueError("No scarabs to update. Call update_scarab() first.")

        for name, scarab in self.scarabs.items():
            try:
                current_price = price_fetcher_func(name)
                scarab.update_price(current_price)
            except Exception as e:
                print(f"Failed to update price for {name}: {e}")
   
class ScarabConvertTool:
    def __init__(self, scarab_list) -> None:
        self.scarab_list = scarab_list
        
    def convert_low_price_scarab(self, threshold):
        cheap_scarabs = self.scarab_list.filter_lower_price_scarab(threshold)
        while True:
            cheap_scarabs.sort(key=lambda d:d.num, reversed=True)
            count = 0
            target = 180
            for cheap in cheap_scarabs:
                while True:
                    if cheap.num == 0:
                        break
                    nn = min(cheap.num, 20)
                    if count + nn > target:
                        break
                    count += nn
                    cheap.num -= nn
                    pyautogui.moveTo(cheap.position)
                    pyautogui.keyDown('ctrl')
                    pyautogui.click(button='left')
                    pyautogui.keyUp('ctrl')
            print('final count:', count)
            
            
                        