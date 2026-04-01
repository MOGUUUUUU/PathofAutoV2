import pyautogui
import pyperclip
import keyboard
import threading
import time
import random
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import Listbox

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

    def _get_cell_positions(self, top_left, bot_right, rows, cols):
        """根据左上、右下角坐标等分计算所有格子中心坐标（行优先）"""
        x0, y0 = top_left
        x1, y1 = bot_right
        cell_w = (x1 - x0) / cols
        cell_h = (y1 - y0) / rows
        positions = []
        for r in range(rows):
            for c in range(cols):
                cx = x0 + cell_w * c + cell_w / 2
                cy = y0 + cell_h * r + cell_h / 2
                positions.append((int(cx), int(cy)))
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

    def buy_item(self, pos):
        """左键点击物品，然后点击确认按钮"""
        pyautogui.moveTo(pos, duration=0.01)
        rand_sleep(0.05)
        pyautogui.click(button='left')
        rand_sleep(0.1)

        if self.confirm_pos:
            pyautogui.moveTo(self.confirm_pos, duration=0.01)
            rand_sleep(0.05)
            pyautogui.click(button='left')
            rand_sleep(0.1)


# ──────────────────────────────────────────────
# Dannig（Ctrl+左键）
# ──────────────────────────────────────────────
class DannigBot(ExpeditionBotBase):
    def __init__(self):
        super().__init__()
        self.single_row_only = False  # 只购买日志模式

    def _get_cell_positions_reverse(self, top_left, bot_right, rows, cols):
        """从右下到左上遍历商店格子"""
        x0, y0 = top_left
        x1, y1 = bot_right
        cell_w = (x1 - x0) / cols
        cell_h = (y1 - y0) / rows
        positions = []
        for r in range(rows - 1, -1, -1):  # 从最后一行到第一行
            for c in range(cols - 1, -1, -1):  # 从最后一列到第一列
                cx = x0 + cell_w * c + cell_w / 2
                cy = y0 + cell_h * r + cell_h / 2
                positions.append((int(cx), int(cy)))
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

            if self.single_row_only:
                # 只购买日志模式：只遍历最后一行（反向遍历时的前 cols 个）
                row_positions = shop_positions[:self.shop_cols]
            else:
                row_positions = shop_positions

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
# Tugen Tab 面板（有确认按钮）
# ──────────────────────────────────────────────
class TugenTabPanel(ExpeditionTabPanel):
    def __init__(self, parent):
        super().__init__(
            parent,
            TugenBot(),
            coord_labels={
                "shop_tl": "商店左上角",
                "shop_br": "商店右下角",
                "confirm": "确认购买按钮",
                "refresh": "刷新按钮",
            }
        )

    def _apply_coords(self, coords):
        self.bot.shop_top_left = coords.get("shop_tl")
        self.bot.shop_bot_right = coords.get("shop_br")
        self.bot.confirm_pos = coords.get("confirm")
        self.bot.refresh_pos = coords.get("refresh")


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
        ttk.Checkbutton(f_opt, text="只购买日志（仅遍历最后一行）",
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
             "• 无背包清理功能"),
            ("Dannig（远征商人）",
             "• 需设置3个坐标：商店左上角、商店右下角、刷新按钮\n"
             "• 无背包清理功能\n"
             "• 可选\"只购买日志\"模式：仅遍历最后一行，遍历完后刷新"),
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