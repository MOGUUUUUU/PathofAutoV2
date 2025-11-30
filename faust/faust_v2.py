import pyautogui
import pyperclip
import time
import random
import numpy as np
from paddleocr import PaddleOCR
from typing import Optional, List, Dict
import re
import os
import cv2

pyautogui.PAUSE = 0.04
pyautogui.FAILSAFE = True


class FaustMaster:
    def __init__(self, use_gpu: bool = False):
        print("正在初始化PaddleOCR（中文模型）...")
        self.ocr = PaddleOCR(
            use_angle_cls=True, lang="ch", use_gpu=use_gpu,
            det_db_thresh=0.5, rec_char_type='ch',
            det_db_score_mode="slow", use_mkldnn=True
        )

        # ==================== 你的绝对坐标（左上x, 左上y, 右下x, 右下y） ====================
        main_l, main_t, main_r, main_b = 509, 106, 1427, 966
        self.region = (main_l, main_t, main_r - main_l, main_b - main_t)

        # price_l, price_t, price_r, price_b = 857, 211, 1049, 596
        # price_w = price_r - price_l
        # price_h = price_b - price_t
        # half_h = price_h // 2 + 25

        # self.price_open_region = (price_l, price_t, price_w, half_h)
        # self.price_compete_region = (price_l, price_t + half_h - 40, price_w, price_h - half_h + 60)
        self.price_open_region = (858, 264, 100, 130)
        self.price_compete_region = (860, 460, 100, 130)

        # 必须悬停这里 + 按 Alt 才会刷新价格
        self.hover_pos = (947, 182)
        
        self.exit = (1399, 113)

        print("FaustMaster 已就绪（含 Alt 激活价格显示）")

    def _activate_price_display(self):
        """核心：移动到标题栏 + 按下 Alt 激活价格刷新"""
        x, y = self.hover_pos
        pyautogui.moveTo(x, y,
                         duration=0.05 + random.random() * 0.2,
                         tween=pyautogui.easeOutQuad)
        time.sleep(0.15)
        pyautogui.keyDown('alt')
        time.sleep(0.35)        # 关键：按住 Alt 0.35秒以上才会强制刷新价格
        pyautogui.keyUp('alt')
        time.sleep(0.6)         # 等待界面完全刷新价格（实测最稳）

    def _ocr(self, region=None, debug=True, name=None) -> List:
        region = region or self.region
        img = pyautogui.screenshot(region=region)
        img_np = np.array(img)
        result = self.ocr.ocr(img_np, cls=True)
        lines = result[0] if result and result[0] else []

        if debug:
            dbg = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            for line in lines:
                pts = np.array(line[0], np.int32)
                cv2.polylines(dbg, [pts], True, (0, 255, 0), 2)
                cv2.putText(dbg, line[1][0], tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            os.makedirs("debug", exist_ok=True)
            cv2.imwrite(f"debug/{name or int(time.time()*1000)}.jpg", dbg)

        return lines

    def click(self, keyword: str, dx=0, dy=0, wait=0.1, clicks=1, fuzzy=False, debug=True) -> bool:
        """
        完全修复版 click —— 坐标零偏移，点击精准到像素
        """
        for _ in range(12):  # 多试几次更稳
            lines = self._ocr(debug=debug)   # 这里 _ocr 默认截的是 self.region
            for line in lines:
                text = line[1][0]
                confidence = line[1][1]

                # 模糊匹配（支持空格、分号等）
                if fuzzy:
                    if not any(k in text for k in keyword.replace(" ", "").split("|")):
                        continue
                else:
                    if keyword not in text:
                        continue

                # 关键修复：OCR 返回的坐标已经是相对于 region 左上角的！
                box = np.array(line[0])
                center_x, center_y = box.mean(axis=0).astype(int)

                # 最终全局坐标 = region左上角 + OCR相对坐标 + 随机偏移
                global_x = self.region[0] + center_x + dx
                global_y = self.region[1] + center_y + dy
                print('found',keyword, global_x, global_y)
                # if True:
                #     pyautogui.moveTo(global_x, global_y)
                #     # 画一个临时红点（需要安装 opencv 和 numpy）
                #     screen = pyautogui.screenshot()
                #     screen = cv2.circle(np.array(screen), (global_x, global_y), 15, (0, 0, 255), -1)
                #     cv2.imshow("Click Debug", screen)
                #     cv2.waitKey(500)
                #     cv2.destroyAllWindows()

                # 人性化移动 + 点击
                pyautogui.moveTo(global_x, global_y,
                                 duration=0.16 + random.random() * 0.22,
                                 tween=pyautogui.easeOutQuad)
                time.sleep(0.04 + random.random() * 0.08)
                pyautogui.click(clicks=clicks)
                return True

            time.sleep(0.38 + random.random() * 0.3)

        print(f"[×] 点击失败：未找到关键字 → {keyword}")
        return False

    def go_home(self):
        pyautogui.moveTo(self.exit)
        time.sleep(0.05 + random.random() * 0.08)
        pyautogui.click(button='left')

    def search_and_select(self, name: str) -> bool:
        if not self.click("请在此输入关键词", wait=0.1):
            self.go_home()
            self.click("通货兑换", wait=1.8)
            if not self.click("请在此输入关键词", wait=0.1):
                return False

        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.05)
        pyperclip.copy(name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.75)

        for _ in range(8):
            if self.click(name, wait=1.0, fuzzy=True):
                return True
            time.sleep(0.55)
        print(f"[×] 未找到物品: {name}")
        return False

    def set_buy(self, name: str):
        self.click("我需要", dy=40)
        self.search_and_select(name)

    def set_sell(self, name: str):
        self.click("我拥有", dy=40)
        self.search_and_select(name)

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        cleand = text.replace(' ', '').replace(',', '.').replace('，', '.').replace('。', '.').replace('O', '0').replace('o', '0').replace('l', '1').replace('I', '1')
        if ':' in cleand:
            buy, sell = cleand.split(':')
            print(buy, sell)
            return float(buy), float(sell)
        return None

    def read_price(self, max_retry: int = 3) -> Dict:
        result = {"open_sell": [], "open_buy": [], "has_stock": False}

        for attempt in range(max_retry):
            print(f"第 {attempt + 1}/{max_retry} 次尝试读取价格...", end=" ")

            # Step 1: 激活标题栏显示（必须先悬停）
            x, y = self.hover_pos
            pyautogui.moveTo(x, y,
                             duration=0.15 + random.random() * 0.1)

            # Step 2: 按住 Alt 并在按住期间疯狂截图读价
            pyautogui.keyDown('alt')
            time.sleep(0.1)  # 确保界面完全响应

            temp_sell = None
            temp_buy  = None

            # 在按住 Alt 的 0.8 秒内，疯狂截图 6~8 次，取最多数字的一次
            for i in range(random.randint(6, 8)):
                # 上半区：开放卖单
                img1 = pyautogui.screenshot(region=self.price_open_region)
                res1 = self.ocr.ocr(np.array(img1), cls=True)
                if res1 and res1[0]:
                    for line in res1[0]:
                        buy, sell = self._extract_number(line[1][0])
                        temp_sell = sell / buy
                        break

                # 下半区：竞品买单
                img2 = pyautogui.screenshot(region=self.price_compete_region)
                res2 = self.ocr.ocr(np.array(img2), cls=True)
                if res2 and res2[0]:
                    for line in res2[0]:
                        buy, sell = self._extract_number(line[1][0])
                        temp_buy = sell / buy
                        break
                    
                time.sleep(0.01 + random.random() * 0.05)  # 高频截图

            # 放开 Alt
            pyautogui.keyUp('alt')
            time.sleep(0.1)

            # 检查是否读到有效价格
            if temp_sell or temp_buy:
                # 检查是否有“没有库存”
                full_ocr = self._ocr()  # 快速扫一遍整个界面
                full_text = "".join(l[1][0] for l in full_ocr)
                has_stock = not any(k in full_text for k in ["没有库存"])

                result = {
                    "open_sell": temp_sell,
                    "open_buy":  temp_buy,
                    "has_stock": has_stock
                }

            else:
                print("本次完全未读到数字，重试...")

            time.sleep(0.2)

        # 所有尝试结束后返回最优结果
        print("最终价格结果：", result if any(result.values()) else "读取失败")
        return result


# ====================== 一键运行测试 ======================
if __name__ == "__main__":
    bot = FaustMaster(use_gpu=False)

    bot.set_sell("神圣石")
    bot.set_buy("混沌石")

    info = bot.read_price()
    d2c_rate = info['open_buy'] / info['open_sell']
    
    # if info["has_stock"] and info["open_sell"] and info["open_buy"]:
    #     profit = info["open_buy"] - info["open_sell"]
    #     print(f"\n最高买价: {info['open_buy']}")
    #     print(f"最低卖价: {info['open_sell']}")
    #     print(f"可套利利润: {profit:.3f}")
    #     if profit > 0.15:
    #         print("大利润机会！！！")
    #         # 可选：pyautogui.alert("有套利！")
    # else:
    #     print("无库存或无有效报价")