import pyautogui
import pyperclip
import keyboard
import threading
import time
import random
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import Listbox
import cv2
import numpy as np

pyautogui.PAUSE = 0.03

REFRESH_DELAY = 1.0


def rand_sleep(base=0.05, jitter=0.02):
    time.sleep(base + random.random() * jitter)


# ──────────────────────────────────────────────
# 公共 Bot 基类
# ──────────────────────────────────────────────
class ExpeditionBotBase:
    """远征商人机器人基类"""

    def __init__(self):
        self.running = False
        self.shop_rows = 12
        self.shop_cols = 12
        self.shop_top_left = None
        self.shop_bot_right = None
        self.refresh_pos = None
        self.buy_keywords = []
        self.buy_count = 0
        self.total_bought = 0
        self.start_time = 0
        # 图像识别
        self.target_img_paths = []
        self._target_images = []
        self._img_match_threshold = 0.3

    def _get_cell_positions(self, top_left, bot_right, rows, cols):
        """根据左上、右下角坐标等分计算所有格子中心坐标（行优先）"""
        x0, y0 = top_left
        x1, y1 = bot_right
        cell_w = (x1 - x0) / cols
        cell_h = (y1 - y0) / rows
        positions = []
        for r in range(rows):
            for c in range(cols):
                cx = int(x0 + cell_w * c + cell_w / 2) + random.randint(-1, 1)
                cy = int(y0 + cell_h * r + cell_h / 2) + random.randint(-1, 1)
                positions.append((cx, cy))
        return positions

    def get_shop_positions(self):
        return self._get_cell_positions(
            self.shop_top_left, self.shop_bot_right,
            self.shop_rows, self.shop_cols
        )

    def read_item(self, pos):
        """悬停到格子，用 Ctrl+Alt+C 读取物品信息"""
        pyautogui.moveTo(pos)
        pyperclip.copy("")
        for _ in range(3):
            pyautogui.hotkey('ctrl', 'alt', 'c')
            rand_sleep(0.01)
        return pyperclip.paste()

    # ── 图像识别（ORB 特征匹配）──
    def _capture_shop_screenshot(self):
        """截取商店区域，返回 cv2 图片"""
        x0, y0 = self.shop_top_left
        x1, y1 = self.shop_bot_right
        region = (x0, y0, x1 - x0, y1 - y0)
        screenshot = pyautogui.screenshot(region=region)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    def _load_target_images(self, paths):
        """加载目标图片，提取 ORB 特征"""
        orb = cv2.ORB_create()
        self._target_images = []
        for p in paths:
            img = cv2.imread(p)
            if img is None:
                continue
            kp, des = orb.detectAndCompute(img, None)
            if des is not None and len(des) > 0:
                self._target_images.append((img, kp, des))

    def _get_cell_image(self, shop_img, col, row):
        """从商店截图中切割指定行列的格子"""
        h, w = shop_img.shape[:2]
        cell_w = w / self.shop_cols
        cell_h = h / self.shop_rows
        x1 = int(col * cell_w)
        y1 = int(row * cell_h)
        x2 = int((col + 1) * cell_w)
        y2 = int((row + 1) * cell_h)
        return shop_img[y1:y2, x1:x2]

    def _match_cell(self, cell_img):
        """用 ORB 特征匹配，返回与所有目标图片中最高的相似度"""
        if not self._target_images:
            return 0.0
        orb = cv2.ORB_create()
        kp, des = orb.detectAndCompute(cell_img, None)
        if des is None or len(des) < 2:
            return 0.0

        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        best_score = 0.0
        for _, _, target_des in self._target_images:
            if target_des is None or len(target_des) < 2:
                continue
            matches = bf.knnMatch(des, target_des, k=2)
            good = 0
            for m in matches:
                if len(m) == 2 and m[0].distance < 0.75 * m[1].distance:
                    good += 1
            score = good / max(len(des), len(target_des))
            best_score = max(best_score, score)
        return best_score

    def _get_cell_positions_with_image_check(self, status_cb=None):
        """截图 → 切割格子 → 图像匹配 → 返回通过的格子中心坐标"""
        shop_img = self._capture_shop_screenshot()
        debug_img = shop_img.copy()
        passed = []
        for r in range(self.shop_rows):
            for c in range(self.shop_cols):
                if not self.running:
                    return passed
                cell = self._get_cell_image(shop_img, c, r)
                score = self._match_cell(cell)

                # 在 debug 图上标注每个格子的相似度
                h, w = debug_img.shape[:2]
                cell_w = w / self.shop_cols
                cell_h = h / self.shop_rows
                tx = int(c * cell_w + 3)
                ty = int(r * cell_h + cell_h / 2 + 4)
                color = (0, 255, 0) if score >= self._img_match_threshold else (0, 0, 255)
                cv2.putText(debug_img, f"{score:.2f}", (tx, ty),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

                if score >= self._img_match_threshold:
                    x0, y0 = self.shop_top_left
                    cx = int(x0 + cell_w * c + cell_w / 2) + random.randint(-1, 1)
                    cy = int(y0 + cell_h * r + cell_h / 2) + random.randint(-1, 1)
                    passed.append((cx, cy))
                    if status_cb:
                        status_cb(f"图像匹配通过 ({r},{c}) 相似度 {score:.2f}")

        self._save_debug_image(debug_img)
        return passed

    def _save_debug_image(self, img):
        """保存 debug 图片，最多保留 10 份"""
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"match_{ts}.png")
        cv2.imwrite(path, img)
        # 清理旧文件，只保留最新 10 份
        files = sorted([
            os.path.join(debug_dir, f) for f in os.listdir(debug_dir)
            if f.startswith("match_") and f.endswith(".png")
        ])
        while len(files) > 10:
            os.remove(files.pop(0))

    def matches_keywords(self, text, keywords):
        if not text or not keywords:
            return False
        return any(kw in text for kw in keywords)

    def buy_item(self, pos):
        """子类实现具体购买逻辑"""
        raise NotImplementedError

    def refresh_shop(self):
        if not self.refresh_pos:
            return
        pyautogui.moveTo(self.refresh_pos, duration=0.05)
        rand_sleep(0.05)
        pyautogui.click(button='left')
        time.sleep(REFRESH_DELAY)

    def run(self, status_cb=None, bought_cb=None):
        self.buy_count = 0
        self.total_bought = 0
        self.start_time = time.time()

        while self.running:
            shop_positions = self.get_shop_positions()

            for pos in shop_positions:
                if not self.running:
                    return

                text = self.read_item(pos)
                if not text:
                    continue

                if self.matches_keywords(text, self.buy_keywords):
                    self.buy_item(pos)
                    self.buy_count += 1
                    self.total_bought += 1
                    if bought_cb:
                        bought_cb(self.total_bought)
                    if status_cb:
                        status_cb(f"购买成功！累计 {self.total_bought} 件")

                    rand_sleep(0.15)
                    recheck = self.read_item(pos)
                    if recheck and self.matches_keywords(recheck, self.buy_keywords):
                        self.running = False
                        if status_cb:
                            status_cb("购买失败（可能货币不足），已停止")
                        return

            if self.running:
                if status_cb:
                    status_cb("刷新商店...")
                self.refresh_shop()


# ──────────────────────────────────────────────
# Gwennen（Ctrl+左键购买，有背包清理）
# ──────────────────────────────────────────────
class GwennenBot(ExpeditionBotBase):
    def __init__(self):
        super().__init__()
        self.inv_top_left = None
        self.inv_bot_right = None
        self.keep_keywords = []
        self.check_interval = 10

    def delete_item(self, pos):
        """鼠标移到物品上，输入 /destroy 回车"""
        pyautogui.moveTo(pos, duration=0.01)
        rand_sleep(0.08)
        pyautogui.click(button='left')
        pyautogui.press('enter')
        pyperclip.copy("/destroy")
        pyautogui.hotkey('ctrl', 'v')
        rand_sleep(0.05)
        pyautogui.press('enter')
        rand_sleep(0.15)

    def clean_inventory(self, status_cb=None):
        # 保留关键词为空时不清理背包
        if not self.keep_keywords:
            return
        if not self.inv_top_left or not self.inv_bot_right:
            return
        if status_cb:
            status_cb("清理背包中...")
        positions = self._get_cell_positions(
            self.inv_top_left, self.inv_bot_right, 5, 12
        )
        for pos in positions:
            if not self.running:
                return
            text = self.read_item(pos)
            if not text:
                continue
            if not self.matches_keywords(text, self.keep_keywords):
                self.delete_item(pos)

    def buy_item(self, pos):
        """Ctrl+左键购买"""
        pyautogui.moveTo(pos, duration=0.01)
        rand_sleep(0.05)
        pyautogui.keyDown('ctrl')
        rand_sleep(0.03)
        pyautogui.click(button='left')
        rand_sleep(0.03)
        pyautogui.keyUp('ctrl')
        rand_sleep(0.1)

    def run(self, status_cb=None, bought_cb=None):
        self.buy_count = 0
        self.total_bought = 0
        self.start_time = time.time()

        while self.running:
            shop_positions = self.get_shop_positions()

            for pos in shop_positions:
                if not self.running:
                    return

                text = self.read_item(pos)
                if not text:
                    continue

                if self.matches_keywords(text, self.buy_keywords):
                    self.buy_item(pos)
                    self.buy_count += 1
                    self.total_bought += 1
                    if bought_cb:
                        bought_cb(self.total_bought)
                    if status_cb:
                        status_cb(f"购买成功！累计 {self.total_bought} 件")

                    rand_sleep(0.15)
                    recheck = self.read_item(pos)
                    if recheck and self.matches_keywords(recheck, self.buy_keywords):
                        self.running = False
                        if status_cb:
                            status_cb("购买失败（可能货币不足），已停止")
                        return

                    if self.buy_count >= self.check_interval:
                        self.buy_count = 0
                        self.clean_inventory(status_cb)
                        if status_cb:
                            status_cb("背包清理完成，继续购买...")

            if self.running:
                if status_cb:
                    status_cb("刷新商店...")
                self.refresh_shop()


# ──────────────────────────────────────────────
# Tugen（左键点击 + 确认按钮）
# ──────────────────────────────────────────────
class TugenBot(ExpeditionBotBase):
    def __init__(self):
        super().__init__()
        self.confirm_pos = None
        self.bargain_enabled = False
        self.bargain_ratio = 0.45  # 砍价比例
        self.bargain_threshold = 10  # 价格差阈值，低于此值不砍价
        self.price_tl = None  # 价格输入框区域左上角
        self.price_br = None  # 价格输入框区域右下角
        self.bargain_confirm_pos = None  # 砍价确认按钮

    def _read_price(self):
        """读取当前价格输入框中的数字"""
        pyperclip.copy("")
        rand_sleep(0.05)
        # 双击价格框选中文字
        pyautogui.hotkey('ctrl', 'a')
        rand_sleep(0.02)
        pyautogui.hotkey('ctrl', 'c')
        rand_sleep(0.05)
        text = pyperclip.paste().strip()
        try:
            return int(text)
        except (ValueError, TypeError):
            return None

    def bargain(self, status_cb=None):
        """砍价逻辑：按比例压低价格"""
        min_price = 0
        max_iter = 10  # 防止死循环
        for _ in range(max_iter):
            if not self.running:
                return

            # 点击价格输入框区域
            px = random.randint(self.price_tl[0], self.price_br[0])
            py = random.randint(self.price_tl[1], self.price_br[1])
            pyautogui.moveTo(px, py, duration=0.02)
            rand_sleep(0.08)
            pyautogui.click(button='left', clicks=2, interval=0.02)
            rand_sleep(0.05)

            max_price = self._read_price()
            if max_price is None:
                if min_price == 0:
                    continue
                else:
                    return  # 无法读取价格，砍价结束

            if abs(max_price - min_price) <= self.bargain_threshold:
                return  # 价格差小于阈值，停止砍价

            new_price = int((min_price + max_price) * self.bargain_ratio)
            min_price = new_price

            if status_cb:
                status_cb(f"砍价：{max_price} → {new_price}")

            # 输入新价格
            pyautogui.hotkey('ctrl', 'a')
            rand_sleep(0.02)
            pyautogui.typewrite(str(new_price), interval=0.01)
            rand_sleep(0.05)

            # 点击砍价确认按钮
            pyautogui.moveTo(self.bargain_confirm_pos, duration=0.02)
            rand_sleep(0.08)
            pyautogui.click(button='left')
            rand_sleep(0.3)

    def buy_item(self, pos, status_cb=None):
        """左键点击物品，砍价（可选），然后点击确认按钮"""
        pyautogui.moveTo(pos, duration=0.01)
        rand_sleep(0.05)
        pyautogui.click(button='left')
        rand_sleep(0.1)

        if self.bargain_enabled and self.price_tl and self.price_br and self.bargain_confirm_pos:
            self.bargain(status_cb=status_cb)

        if self.confirm_pos:
            pyautogui.moveTo(self.confirm_pos, duration=0.01)
            rand_sleep(0.05)
            pyautogui.click(button='left')
            rand_sleep(0.1)

    def run(self, status_cb=None, bought_cb=None):
        """Tugen 运行逻辑：支持砍价 + 图像识别过滤"""
        self.buy_count = 0
        self.total_bought = 0
        self.start_time = time.time()

        while self.running:
            # 有目标图片时，先图像匹配过滤格子
            if self._target_images:
                shop_positions = self._get_cell_positions_with_image_check(status_cb)
                if status_cb:
                    status_cb(f"图像匹配完成，{len(shop_positions)} 个格子通过")
            else:
                shop_positions = self.get_shop_positions()

            for pos in shop_positions:
                if not self.running:
                    return

                text = self.read_item(pos)
                if not text:
                    continue

                if self.matches_keywords(text, self.buy_keywords):
                    self.buy_item(pos, status_cb=status_cb)
                    self.buy_count += 1
                    self.total_bought += 1
                    if bought_cb:
                        bought_cb(self.total_bought)
                    if status_cb:
                        status_cb(f"购买成功！累计 {self.total_bought} 件")

                    rand_sleep(0.15)
                    recheck = self.read_item(pos)
                    if recheck and self.matches_keywords(recheck, self.buy_keywords):
                        self.running = False
                        if status_cb:
                            status_cb("购买失败（可能货币不足），已停止")
                        return

            if self.running:
                if status_cb:
                    status_cb("刷新商店...")
                self.refresh_shop()


# ──────────────────────────────────────────────
# Dannig（Ctrl+左键）
# ──────────────────────────────────────────────
class DannigBot(ExpeditionBotBase):
    def __init__(self):
        super().__init__()
        self.single_row_only = False  # 只购买日志模式

    def _get_cell_positions_reverse(self, top_left, bot_right, rows, cols):
        """从右下到左上遍历商店格子"""
        positions = self._get_cell_positions(top_left, bot_right, rows, cols)
        positions.reverse()
        return positions

    def get_shop_positions(self):
        """Dannig 使用反向遍历"""
        return self._get_cell_positions_reverse(
            self.shop_top_left, self.shop_bot_right,
            self.shop_rows, self.shop_cols
        )

    def buy_item(self, pos):
        """按下 Ctrl，左键点击物品"""
        pyautogui.moveTo(pos, duration=0.01)
        rand_sleep(0.05)
        pyautogui.keyDown('ctrl')
        rand_sleep(0.03)
        pyautogui.click(button='left')
        rand_sleep(0.03)
        pyautogui.keyUp('ctrl')
        rand_sleep(0.1)

    def run(self, status_cb=None, bought_cb=None):
        """Dannig 运行逻辑：支持只购买日志模式"""
        self.buy_count = 0
        self.total_bought = 0
        self.start_time = time.time()

        while self.running:
            shop_positions = self.get_shop_positions()
            cols = self.shop_cols

            if self.single_row_only:
                # 只购买日志模式：从最后一行开始找第一个有物品的行
                # 反转后 shop_positions[0:cols] 是最后一行，shop_positions[cols:2*cols] 是倒数第二行...
                row_positions = None
                for row_idx in range(self.shop_rows):
                    start = row_idx * cols
                    end = start + cols
                    row_cells = shop_positions[start:end]

                    # 检测这一行是否有物品
                    has_item = False
                    for pos in row_cells:
                        if not self.running:
                            return
                        text = self.read_item(pos)
                        if text:
                            has_item = True
                            break

                    if has_item:
                        row_positions = row_cells
                        break
            else:
                row_positions = shop_positions

            if row_positions:
                for pos in row_positions:
                    if not self.running:
                        return

                    text = self.read_item(pos)
                    if not text:
                        continue

                    if self.matches_keywords(text, self.buy_keywords):
                        self.buy_item(pos)
                        self.buy_count += 1
                        self.total_bought += 1
                        if bought_cb:
                            bought_cb(self.total_bought)
                        if status_cb:
                            status_cb(f"购买成功！累计 {self.total_bought} 件")

                        rand_sleep(0.15)
                        recheck = self.read_item(pos)
                        if recheck and self.matches_keywords(recheck, self.buy_keywords):
                            self.running = False
                            if status_cb:
                                status_cb("购买失败（可能货币不足），已停止")
                            return

            if self.running:
                if status_cb:
                    status_cb("刷新商店...")
                self.refresh_shop()


# ──────────────────────────────────────────────
# 通用 Tab 面板
# ──────────────────────────────────────────────
class ExpeditionTabPanel:
    """远征商人 Tab 面板基类"""

    def __init__(self, parent, bot, coord_labels):
        self.bot = bot
        self.coord_labels = coord_labels  # {key: "显示名称"}

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="状态：未运行")
        self.bought_var = tk.StringVar(value="累计购买：0")
        self.time_var = tk.StringVar(value="运行时间：00:00:00")
        self.coord_mode = tk.StringVar(value=list(coord_labels.keys())[0])
        self.coord_vars = {k: tk.StringVar(value="未设置") for k in coord_labels}
        self.buy_kw_input = tk.StringVar()
        self.buy_keywords = []
        self.shop_rows_var = tk.IntVar(value=12)
        self.shop_cols_var = tk.IntVar(value=12)
        self.time_thread = None

        self._build_ui()

    def _build_ui(self):
        # ── 坐标设置 ──
        f_coord = ttk.LabelFrame(self.frame, text="坐标设置（选择类型后鼠标移过去按 =）")
        f_coord.pack(padx=6, pady=(6, 3), fill=tk.X)

        keys = list(self.coord_labels.keys())
        for i, key in enumerate(keys):
            r, c = divmod(i, 2)
            ttk.Radiobutton(f_coord, text=self.coord_labels[key],
                           variable=self.coord_mode, value=key).grid(
                row=r*2, column=c, sticky=tk.W, padx=6, pady=1)
            ttk.Entry(f_coord, textvariable=self.coord_vars[key],
                     state="readonly", width=18).grid(
                row=r*2+1, column=c, padx=6, pady=1, sticky=tk.W)

        # ── 商店格子尺寸 ──
        f_grid = ttk.LabelFrame(self.frame, text="商店格子尺寸")
        f_grid.pack(padx=6, pady=3, fill=tk.X)
        ttk.Label(f_grid, text="行数：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_grid, from_=1, to=20, textvariable=self.shop_rows_var,
                   width=6).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(f_grid, text="列数：").grid(row=0, column=2, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_grid, from_=1, to=20, textvariable=self.shop_cols_var,
                   width=6).grid(row=0, column=3, padx=4, pady=2)

        # ── 子类额外 UI ──
        self._build_extra_ui()

        # ── 购买关键词 ──
        f_buy = ttk.LabelFrame(self.frame, text="购买目标关键词（匹配任意一个即购买）")
        f_buy.pack(padx=6, pady=3, fill=tk.BOTH, expand=False)
        self._build_kw_panel(f_buy, self.buy_kw_input, self.buy_keywords, "buy")

        # ── 控制 ──
        ttk.Label(self.frame, text="F3 开始 / 停止", foreground="gray").pack(pady=(1, 2))

        # ── 状态 ──
        f_stat = ttk.LabelFrame(self.frame, text="运行状态")
        f_stat.pack(padx=6, pady=(3, 6), fill=tk.X)
        ttk.Label(f_stat, textvariable=self.bought_var).grid(
            row=0, column=0, padx=6, pady=2, sticky=tk.W)
        ttk.Label(f_stat, textvariable=self.time_var).grid(
            row=0, column=1, padx=6, pady=2, sticky=tk.W)
        ttk.Label(f_stat, textvariable=self.status_var,
                 foreground="blue").grid(row=1, column=0, columnspan=2, padx=6, pady=2, sticky=tk.W)

    def _build_extra_ui(self):
        """子类可覆盖以添加额外 UI"""
        pass

    def _build_kw_panel(self, parent, input_var, kw_list, tag):
        ttk.Label(parent, text="关键词：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Entry(parent, textvariable=input_var, width=22,
                 font=("Microsoft YaHei", 9)).grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(parent, text="添加", width=7,
                  command=lambda: self._add_kw(input_var, kw_list, lb)).grid(
            row=0, column=2, padx=4, pady=2)
        lb = Listbox(parent, height=4, font=("Microsoft YaHei", 9))
        lb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=4, pady=2)

        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=2, sticky=tk.NS, pady=2)

        f_btn = ttk.Frame(parent)
        f_btn.grid(row=1, column=3, padx=4, pady=2, sticky=tk.N)
        ttk.Button(f_btn, text="删除", width=7,
                  command=lambda: self._del_kw(kw_list, lb)).pack(pady=1)
        ttk.Button(f_btn, text="清空", width=7,
                  command=lambda: self._clear_kw(kw_list, lb)).pack(pady=1)

        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        setattr(self, f"_{tag}_lb", lb)
        # Store lambda with reference to lb
        self._kw_lb = lb

    def _add_kw(self, input_var, kw_list, lb):
        kw = input_var.get().strip()
        if not kw:
            return
        if kw in kw_list:
            messagebox.showinfo("提示", "关键词已存在")
            return
        kw_list.append(kw)
        lb.insert(tk.END, kw)
        input_var.set("")

    def _del_kw(self, kw_list, lb):
        sel = lb.curselection()
        if not sel:
            return
        for i in reversed(sel):
            del kw_list[i]
            lb.delete(i)

    def _clear_kw(self, kw_list, lb):
        kw_list.clear()
        lb.delete(0, tk.END)

    def get_coord(self, mode):
        x, y = pyautogui.position()
        if mode in self.coord_vars:
            self.coord_vars[mode].set(f"({x}, {y})")
            self.status_var.set(f"已设置 {self.coord_labels[mode]}：({x}, {y})")

    def _parse_coords(self):
        def parse(s):
            s = s.strip().strip("()")
            parts = s.split(",")
            if len(parts) != 2:
                return None
            try:
                return (int(parts[0].strip()), int(parts[1].strip()))
            except ValueError:
                return None

        result = {}
        for key, var in self.coord_vars.items():
            result[key] = parse(var.get())
        return result

    def toggle_run(self):
        if self.bot.running:
            self.bot.running = False
            self.status_var.set("已停止")
        else:
            self._start()

    def _start(self):
        coords = self._parse_coords()
        missing = [k for k, v in coords.items() if v is None]
        if missing:
            messagebox.showwarning("警告", f"以下坐标未设置：{', '.join(missing)}")
            return
        if not self.buy_keywords:
            messagebox.showwarning("警告", "请至少添加一个购买关键词")
            return

        self._apply_coords(coords)
        self.bot.shop_rows = self.shop_rows_var.get()
        self.bot.shop_cols = self.shop_cols_var.get()
        self.bot.buy_keywords = self.buy_keywords.copy()
        self.bot.running = True

        threading.Thread(target=self._run_thread, daemon=True).start()
        self._start_time_thread()
        self.status_var.set("运行中...")

    def _apply_coords(self, coords):
        """子类可覆盖以应用额外坐标"""
        self.bot.shop_top_left = coords.get("shop_tl")
        self.bot.shop_bot_right = coords.get("shop_br")
        self.bot.refresh_pos = coords.get("refresh")

    def _run_thread(self):
        self.bot.run(
            status_cb=lambda s: self.status_var.set(s),
            bought_cb=lambda n: self.bought_var.set(f"累计购买：{n}"),
        )
        self.bot.running = False
        self.status_var.set("已停止")

    def _start_time_thread(self):
        def upd():
            while self.bot.running:
                used = int(time.time() - self.bot.start_time)
                h, m, s = used // 3600, used % 3600 // 60, used % 60
                self.time_var.set(f"运行时间：{h:02d}:{m:02d}:{s:02d}")
                time.sleep(0.5)
        self.time_thread = threading.Thread(target=upd, daemon=True)
        self.time_thread.start()

    def _get_extra_config(self):
        """子类可覆盖以返回额外配置字典"""
        return {}

    def _apply_extra_config(self, cfg):
        """子类可覆盖以应用额外配置"""
        pass

    def on_tab_deselect(self):
        if self.bot.running:
            self.bot.running = False
            self.status_var.set("切换模式，已停止")


# ──────────────────────────────────────────────
# Gwennen Tab 面板（有背包清理）
# ──────────────────────────────────────────────
class GwennenTabPanel(ExpeditionTabPanel):
    def __init__(self, parent):
        self.keep_kw_input = tk.StringVar()
        self.keep_keywords = []
        self.check_interval_var = tk.IntVar(value=10)
        super().__init__(
            parent,
            GwennenBot(),
            coord_labels={
                "shop_tl": "商店左上角",
                "shop_br": "商店右下角",
                "inv_tl": "背包左上角",
                "inv_br": "背包右下角",
                "refresh": "刷新按钮",
            }
        )

    def _build_extra_ui(self):
        # ── 背包保留关键词 ──
        f_keep = ttk.LabelFrame(self.frame, text="背包保留关键词（匹配任意一个则不删除）")
        f_keep.pack(padx=6, pady=3, fill=tk.BOTH, expand=False)
        self._build_keep_kw_panel(f_keep, self.keep_kw_input, self.keep_keywords, "keep")

        # ── 检查间隔 ──
        f_param = ttk.LabelFrame(self.frame, text="参数")
        f_param.pack(padx=6, pady=3, fill=tk.X)
        ttk.Label(f_param, text="每购买多少次检查背包：").grid(
            row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_param, from_=1, to=999,
                   textvariable=self.check_interval_var, width=7).grid(
            row=0, column=1, padx=4, pady=2)

    def _build_keep_kw_panel(self, parent, input_var, kw_list, tag):
        ttk.Label(parent, text="关键词：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Entry(parent, textvariable=input_var, width=22,
                 font=("Microsoft YaHei", 9)).grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(parent, text="添加", width=7,
                  command=lambda: self._add_kw(input_var, kw_list, self._keep_lb)).grid(
            row=0, column=2, padx=4, pady=2)
        self._keep_lb = Listbox(parent, height=3, font=("Microsoft YaHei", 9))
        self._keep_lb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=4, pady=2)

        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._keep_lb.yview)
        self._keep_lb.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=2, sticky=tk.NS, pady=2)

        f_btn = ttk.Frame(parent)
        f_btn.grid(row=1, column=3, padx=4, pady=2, sticky=tk.N)
        ttk.Button(f_btn, text="删除", width=7,
                  command=lambda: self._del_kw(kw_list, self._keep_lb)).pack(pady=1)
        ttk.Button(f_btn, text="清空", width=7,
                  command=lambda: self._clear_kw(kw_list, self._keep_lb)).pack(pady=1)

        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)

    def _apply_coords(self, coords):
        self.bot.shop_top_left = coords.get("shop_tl")
        self.bot.shop_bot_right = coords.get("shop_br")
        self.bot.inv_top_left = coords.get("inv_tl")
        self.bot.inv_bot_right = coords.get("inv_br")
        self.bot.refresh_pos = coords.get("refresh")
        self.bot.check_interval = self.check_interval_var.get()
        self.bot.keep_keywords = self.keep_keywords.copy()

    def _get_extra_config(self):
        return {
            "keep_keywords": self.keep_keywords.copy(),
            "check_interval": self.check_interval_var.get(),
        }

    def _apply_extra_config(self, cfg):
        self.check_interval_var.set(cfg.get("check_interval", 10))
        self.keep_keywords.clear()
        if hasattr(self, '_keep_lb'):
            self._keep_lb.delete(0, tk.END)
        for kw in cfg.get("keep_keywords", []):
            self.keep_keywords.append(kw)
            if hasattr(self, '_keep_lb'):
                self._keep_lb.insert(tk.END, kw)


# ──────────────────────────────────────────────
# Tugen Tab 面板（有确认按钮 + 砍价）
# ──────────────────────────────────────────────
class TugenTabPanel(ExpeditionTabPanel):
    def __init__(self, parent):
        self.bargain_var = tk.BooleanVar(value=False)
        self.bargain_ratio_var = tk.DoubleVar(value=0.45)
        self.bargain_threshold_var = tk.IntVar(value=10)
        self.target_img_paths = []
        self.img_threshold_var = tk.DoubleVar(value=0.3)
        super().__init__(
            parent,
            TugenBot(),
            coord_labels={
                "shop_tl": "商店左上角",
                "shop_br": "商店右下角",
                "confirm": "确认购买按钮",
                "refresh": "刷新按钮",
                "price_tl": "价格框左上角",
                "price_br": "价格框右下角",
                "bargain_confirm": "砍价确认按钮",
            }
        )

    def _build_extra_ui(self):
        # ── 砍价选项 ──
        f_opt = ttk.LabelFrame(self.frame, text="砍价选项")
        f_opt.pack(padx=6, pady=3, fill=tk.X)
        ttk.Checkbutton(f_opt, text="启用砍价（购买前先压低价格）",
                       variable=self.bargain_var).pack(padx=6, pady=3, anchor=tk.W)
        fr = ttk.Frame(f_opt)
        fr.pack(padx=6, pady=2, fill=tk.X)
        ttk.Label(fr, text="砍价比例：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(fr, from_=0.1, to=0.9, increment=0.05,
                   textvariable=self.bargain_ratio_var, width=6).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(fr, text="价格差阈值：").grid(row=0, column=2, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(fr, from_=1, to=100,
                   textvariable=self.bargain_threshold_var, width=6).grid(row=0, column=3, padx=4, pady=2)

        # ── 图像识别 ──
        f_img = ttk.LabelFrame(self.frame, text="图像识别（先匹配图片，再读取文字）")
        f_img.pack(padx=6, pady=3, fill=tk.BOTH, expand=False)

        # 目标图片列表
        self._img_lb = Listbox(f_img, height=4, font=("Microsoft YaHei", 9))
        self._img_lb.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW, padx=4, pady=2)

        sb = ttk.Scrollbar(f_img, orient=tk.VERTICAL, command=self._img_lb.yview)
        self._img_lb.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=2, sticky=tk.NS, pady=2)

        f_img_btn = ttk.Frame(f_img)
        f_img_btn.grid(row=0, column=3, padx=4, pady=2, sticky=tk.N)
        ttk.Button(f_img_btn, text="添加图片", width=8,
                  command=self._add_target_images).pack(pady=1)
        ttk.Button(f_img_btn, text="删除", width=8,
                  command=self._del_target_image).pack(pady=1)
        ttk.Button(f_img_btn, text="清空", width=8,
                  command=self._clear_target_images).pack(pady=1)

        # 相似度阈值
        fr2 = ttk.Frame(f_img)
        fr2.grid(row=1, column=0, columnspan=4, padx=4, pady=2, sticky=tk.W)
        ttk.Label(fr2, text="相似度阈值：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(fr2, from_=0.1, to=1.0, increment=0.05,
                   textvariable=self.img_threshold_var, width=6).grid(row=0, column=1, padx=4, pady=2)

        f_img.grid_columnconfigure(0, weight=1)
        f_img.grid_rowconfigure(0, weight=1)

    def _add_target_images(self):
        paths = filedialog.askopenfilenames(
            title="选择目标图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp")]
        )
        for p in paths:
            if p not in self.target_img_paths:
                self.target_img_paths.append(p)
                self._img_lb.insert(tk.END, p)

    def _del_target_image(self):
        sel = self._img_lb.curselection()
        if not sel:
            return
        for i in reversed(sel):
            del self.target_img_paths[i]
            self._img_lb.delete(i)

    def _clear_target_images(self):
        self.target_img_paths.clear()
        self._img_lb.delete(0, tk.END)

    def _apply_coords(self, coords):
        self.bot.shop_top_left = coords.get("shop_tl")
        self.bot.shop_bot_right = coords.get("shop_br")
        self.bot.confirm_pos = coords.get("confirm")
        self.bot.refresh_pos = coords.get("refresh")
        self.bot.price_tl = coords.get("price_tl")
        self.bot.price_br = coords.get("price_br")
        self.bot.bargain_confirm_pos = coords.get("bargain_confirm")
        self.bot.bargain_enabled = self.bargain_var.get()
        self.bot.bargain_ratio = self.bargain_ratio_var.get()
        self.bot.bargain_threshold = self.bargain_threshold_var.get()
        # 图像识别
        self.bot._img_match_threshold = self.img_threshold_var.get()
        if self.target_img_paths:
            self.bot._load_target_images(self.target_img_paths)
        else:
            self.bot._target_images = []

    def _get_extra_config(self):
        return {
            "bargain_enabled": self.bargain_var.get(),
            "bargain_ratio": self.bargain_ratio_var.get(),
            "bargain_threshold": self.bargain_threshold_var.get(),
            "target_img_paths": self.target_img_paths.copy(),
            "img_threshold": self.img_threshold_var.get(),
        }

    def _apply_extra_config(self, cfg):
        self.bargain_var.set(cfg.get("bargain_enabled", False))
        self.bargain_ratio_var.set(cfg.get("bargain_ratio", 0.45))
        self.bargain_threshold_var.set(cfg.get("bargain_threshold", 10))
        # 图像识别
        self.img_threshold_var.set(cfg.get("img_threshold", 0.3))
        self.target_img_paths.clear()
        self._img_lb.delete(0, tk.END)
        for p in cfg.get("target_img_paths", []):
            self.target_img_paths.append(p)
            self._img_lb.insert(tk.END, p)


# ──────────────────────────────────────────────
# Dannig Tab 面板
# ──────────────────────────────────────────────
class DannigTabPanel(ExpeditionTabPanel):
    def __init__(self, parent):
        self.single_row_var = tk.BooleanVar(value=False)
        super().__init__(
            parent,
            DannigBot(),
            coord_labels={
                "shop_tl": "商店左上角",
                "shop_br": "商店右下角",
                "refresh": "刷新按钮",
            }
        )

    def _build_extra_ui(self):
        # ── 只购买日志选项 ──
        f_opt = ttk.LabelFrame(self.frame, text="购买选项")
        f_opt.pack(padx=6, pady=3, fill=tk.X)
        ttk.Checkbutton(f_opt, text="只购买日志（从最后一行找起，有物品则购买后刷新）",
                       variable=self.single_row_var).pack(padx=6, pady=3, anchor=tk.W)

    def _apply_coords(self, coords):
        self.bot.shop_top_left = coords.get("shop_tl")
        self.bot.shop_bot_right = coords.get("shop_br")
        self.bot.refresh_pos = coords.get("refresh")
        self.bot.single_row_only = self.single_row_var.get()

    def _get_extra_config(self):
        return {"single_row_only": self.single_row_var.get()}

    def _apply_extra_config(self, cfg):
        self.single_row_var.set(cfg.get("single_row_only", False))


# ──────────────────────────────────────────────
# Home Tab 面板（使用说明）
# ──────────────────────────────────────────────
class HomeTabPanel:
    """首页：使用说明和全局配置"""

    def __init__(self, parent, tabs):
        self.tabs = tabs  # [GwennenTabPanel, TugenTabPanel, DannigTabPanel]
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expedition.json")

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()

    def _build_ui(self):
        # ── 使用说明 ──
        f_doc = ttk.LabelFrame(self.frame, text="使用说明")
        f_doc.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        docs = [
            ("Gwennen（远征商人）",
             "• 需设置5个坐标：商店左上角、商店右下角、背包左上角、背包右下角、刷新按钮\n"
             "• 支持背包清理：每购买一定次数后检查背包，删除不匹配保留关键词的物品"),
            ("Tugen（远征商人）",
             "• 需设置4个坐标：商店左上角、商店右下角、确认购买按钮、刷新按钮\n"
             "• 可选砍价功能：需额外设置3个坐标（价格框左上角、价格框右下角、砍价确认按钮）\n"
             "• 砍价使用二分法自动压低价格，直到价格差≤10停止"),
            ("Dannig（远征商人）",
             "• 需设置3个坐标：商店左上角、商店右下角、刷新按钮\n"
             "• 无背包清理功能\n"
             "• 可选\"只购买日志\"模式：从最后一行开始探测，找到第一个有物品的行后遍历购买，然后刷新"),
        ]

        for i, (title, content) in enumerate(docs):
            ttk.Label(f_doc, text=title, font=("Microsoft YaHei", 10, "bold")).grid(
                row=i*2, column=0, sticky=tk.W, padx=10, pady=(10, 2))
            ttk.Label(f_doc, text=content, font=("Microsoft YaHei", 9),
                     justify=tk.LEFT, wraplength=550).grid(
                row=i*2+1, column=0, sticky=tk.W, padx=20, pady=(0, 5))

        # ── 通用说明 ──
        f_common = ttk.LabelFrame(self.frame, text="通用操作")
        f_common.pack(padx=10, pady=5, fill=tk.X)

        common_text = (
            "• F3：开始/停止运行\n"
            "• = ：捕获当前鼠标位置设置为选中的坐标类型\n"
            "• 购买关键词：物品信息包含任意一个关键词即购买（Ctrl+Alt+C 复制物品信息）\n"
        )
        ttk.Label(f_common, text=common_text, font=("Microsoft YaHei", 9),
                 justify=tk.LEFT).pack(padx=10, pady=5, anchor=tk.W)

        # ── 配置管理 ──
        f_cfg = ttk.LabelFrame(self.frame, text="配置管理")
        f_cfg.pack(padx=10, pady=10, fill=tk.X)

        ttk.Label(f_cfg, text="所有工具配置保存在同一文件 (expedition.json)：",
                 font=("Microsoft YaHei", 9)).pack(padx=10, pady=5, anchor=tk.W)

        btn_frame = ttk.Frame(f_cfg)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="保存所有配置", width=15,
                  command=self._save_all).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="加载所有配置", width=15,
                  command=self._load_all).pack(side=tk.LEFT, padx=10)

        # 启动时自动加载配置
        self._load_all(silent=True)

    def _save_all(self):
        """保存所有工具配置到单一文件"""
        data = {
            "gwennen": self._collect_tab_config(self.tabs[0]),
            "tugen": self._collect_tab_config(self.tabs[1]),
            "dannig": self._collect_tab_config(self.tabs[2]),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("成功", f"配置已保存到：\n{self.config_file}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")

    def _collect_tab_config(self, tab):
        """从 Tab 面板收集配置"""
        return {
            "coords": {k: v.get() for k, v in tab.coord_vars.items()},
            "shop_rows": tab.shop_rows_var.get(),
            "shop_cols": tab.shop_cols_var.get(),
            "buy_keywords": tab.buy_keywords.copy(),
            **tab._get_extra_config(),
        }

    def _load_all(self, silent=False):
        """从单一文件加载所有工具配置"""
        if not os.path.exists(self.config_file):
            if not silent:
                messagebox.showinfo("提示", "未找到配置文件")
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"加载失败：{e}")
            return

        # 加载各 Tab 配置
        for key, tab in [("gwennen", self.tabs[0]), ("tugen", self.tabs[1]), ("dannig", self.tabs[2])]:
            if key in data:
                self._apply_tab_config(tab, data[key])

        if not silent:
            messagebox.showinfo("成功", f"配置已加载：\n{self.config_file}")

    def _apply_tab_config(self, tab, cfg):
        """应用配置到 Tab 面板"""
        for k, v in cfg.get("coords", {}).items():
            if k in tab.coord_vars:
                tab.coord_vars[k].set(v)
        tab.shop_rows_var.set(cfg.get("shop_rows", 12))
        tab.shop_cols_var.set(cfg.get("shop_cols", 12))

        tab.buy_keywords.clear()
        tab._buy_lb.delete(0, tk.END)
        for kw in cfg.get("buy_keywords", []):
            tab.buy_keywords.append(kw)
            tab._buy_lb.insert(tk.END, kw)

        tab._apply_extra_config(cfg)


# ──────────────────────────────────────────────
# 主 GUI（Notebook 四个 Tab）
# ──────────────────────────────────────────────
class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("远征商人自动购买")
        self.root.geometry("620x720")
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 先创建三个工具 Tab（不加入 Notebook）
        self.tab_gwennen = GwennenTabPanel(nb)
        self.tab_tugen = TugenTabPanel(nb)
        self.tab_dannig = DannigTabPanel(nb)

        tabs_list = [self.tab_gwennen, self.tab_tugen, self.tab_dannig]

        # Home Tab 需要引用其他 Tab
        self.tab_home = HomeTabPanel(nb, tabs_list)

        # 添加到 Notebook，Home 放第一位
        nb.add(self.tab_home.frame, text="Home")
        nb.add(self.tab_gwennen.frame, text="Gwennen")
        nb.add(self.tab_tugen.frame, text="Tugen")
        nb.add(self.tab_dannig.frame, text="Dannig")

        self._active_tab = None
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_change(nb))

        keyboard.add_hotkey('f3', self._toggle_active)
        self.root.bind('<equal>', lambda e: self._capture_active())

    def _on_tab_change(self, nb):
        idx = nb.index(nb.select())
        # Home 页无 bot，不需要处理
        if idx == 0:
            self._active_tab = None
            return

        tabs = [self.tab_gwennen, self.tab_tugen, self.tab_dannig]
        bot_idx = idx - 1  # 跳过 Home

        for i, tab in enumerate(tabs):
            if i != bot_idx:
                tab.on_tab_deselect()
        self._active_tab = tabs[bot_idx]

    def _toggle_active(self):
        if self._active_tab:
            self._active_tab.toggle_run()

    def _capture_active(self):
        if self._active_tab:
            self._active_tab.get_coord(self._active_tab.coord_mode.get())

    def _on_closing(self):
        for tab in [self.tab_gwennen, self.tab_tugen, self.tab_dannig]:
            tab.bot.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    MainApp().run()