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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gwennen.json")

pyautogui.PAUSE = 0.03

# ── 背包固定配置（12列×5行）──
INV_ROWS = 5
INV_COLS = 12
# 用户需在 GUI 中设置背包左上角和右下角坐标
# 格子中心通过等分计算

# 刷新延迟（秒）
REFRESH_DELAY = 1.0


def rand_sleep(base=0.05, jitter=0.02):
    time.sleep(base + random.random() * jitter)


class GwennenBot:
    def __init__(self):
        self.running = False

        # 商店格子配置
        self.shop_rows = 12
        self.shop_cols = 12
        self.shop_top_left = None   # (x, y)
        self.shop_bot_right = None  # (x, y)

        # 背包格子配置
        self.inv_top_left = None    # (x, y)
        self.inv_bot_right = None   # (x, y)

        # 刷新按钮坐标
        self.refresh_pos = None     # (x, y)

        # 关键词
        self.buy_keywords = []      # 购买目标关键词
        self.keep_keywords = []     # 背包保留关键词

        # 每购买多少次检查背包
        self.check_interval = 10

        self.buy_count = 0
        self.total_bought = 0
        self.start_time = 0

    # ── 格子坐标计算 ──
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

    def get_inv_positions(self):
        return self._get_cell_positions(
            self.inv_top_left, self.inv_bot_right,
            INV_ROWS, INV_COLS
        )

    # ── 物品信息读取 ──
    def read_item(self, pos):
        """悬停到格子，用 Ctrl+Alt+C 读取物品信息"""
        pyautogui.moveTo(pos, duration=0.05)
        rand_sleep(0.08)
        pyperclip.copy("")
        for _ in range(3):
            pyautogui.hotkey('ctrl', 'alt', 'c')
            rand_sleep(0.04)
        return pyperclip.paste()

    def matches_keywords(self, text, keywords):
        if not text or not keywords:
            return False
        return any(kw in text for kw in keywords)

    # ── 购买 ──
    def buy_item(self, pos):
        """Ctrl+左键购买"""
        pyautogui.moveTo(pos, duration=0.05)
        rand_sleep(0.05)
        pyautogui.keyDown('ctrl')
        rand_sleep(0.03)
        pyautogui.click(button='left')
        rand_sleep(0.03)
        pyautogui.keyUp('ctrl')
        rand_sleep(0.1)

    # ── 删除物品 ──
    def delete_item(self, pos):
        """鼠标移到物品上，输入 /delete 回车"""
        pyautogui.moveTo(pos, duration=0.05)
        rand_sleep(0.08)
        pyperclip.copy("/delete")
        pyautogui.hotkey('ctrl', 'v')
        rand_sleep(0.05)
        pyautogui.press('enter')
        rand_sleep(0.15)

    # ── 刷新商店 ──
    def refresh_shop(self):
        if not self.refresh_pos:
            return
        pyautogui.moveTo(self.refresh_pos, duration=0.05)
        rand_sleep(0.05)
        pyautogui.click(button='left')
        time.sleep(REFRESH_DELAY)

    # ── 清理背包 ──
    def clean_inventory(self, status_cb=None):
        if not self.inv_top_left or not self.inv_bot_right:
            return
        if status_cb:
            status_cb("清理背包中...")
        positions = self.get_inv_positions()
        for pos in positions:
            if not self.running:
                return
            text = self.read_item(pos)
            if not text:
                continue
            # 没有任何保留关键词匹配 → 删除
            if not self.matches_keywords(text, self.keep_keywords):
                self.delete_item(pos)

    # ── 主循环 ──
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

                    # 检查是否购买失败（货币不足等）：
                    # 再次读取同一格，若物品还在则视为失败，停止
                    rand_sleep(0.15)
                    recheck = self.read_item(pos)
                    if recheck and self.matches_keywords(recheck, self.buy_keywords):
                        self.running = False
                        if status_cb:
                            status_cb("购买失败（可能货币不足），已停止")
                        return

                    # 达到检查间隔 → 清理背包
                    if self.buy_count >= self.check_interval:
                        self.buy_count = 0
                        self.clean_inventory(status_cb)
                        if status_cb:
                            status_cb("背包清理完成，继续购买...")

            # 一页遍历完毕 → 刷新
            if self.running:
                if status_cb:
                    status_cb("刷新商店...")
                self.refresh_shop()


# ── GUI ──
class GwennenGUI:
    def __init__(self):
        self.bot = GwennenBot()

        self.root = tk.Tk()
        self.root.title("Gwennen 自动购买")
        self.root.geometry("560x780")
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        keyboard.add_hotkey('f3', self._toggle_run)

        self.status_var = tk.StringVar(value="状态：未运行")
        self.bought_var = tk.StringVar(value="累计购买：0")
        self.time_var = tk.StringVar(value="运行时间：00:00:00")

        self.coord_mode = tk.StringVar(value="shop_tl")
        self.coord_vars = {
            "shop_tl":  tk.StringVar(value="未设置"),
            "shop_br":  tk.StringVar(value="未设置"),
            "inv_tl":   tk.StringVar(value="未设置"),
            "inv_br":   tk.StringVar(value="未设置"),
            "refresh":  tk.StringVar(value="未设置"),
        }

        self.buy_kw_input = tk.StringVar()
        self.keep_kw_input = tk.StringVar()
        self.buy_keywords = []
        self.keep_keywords = []

        self.check_interval_var = tk.IntVar(value=10)
        self.shop_rows_var = tk.IntVar(value=12)
        self.shop_cols_var = tk.IntVar(value=12)

        self._build_ui()
        self.root.bind('<equal>', lambda _: self._capture(self.coord_mode.get()))
        self._time_thread = None

    def _build_ui(self):
        # ── 坐标设置 ──
        f_coord = ttk.LabelFrame(self.root, text="坐标设置（选择类型后鼠标移过去按 =）")
        f_coord.pack(padx=5, pady=4, fill=tk.X)

        coord_options = [
            ("shop_tl",  "商店左上角"),
            ("shop_br",  "商店右下角"),
            ("inv_tl",   "背包左上角"),
            ("inv_br",   "背包右下角"),
            ("refresh",  "刷新按钮"),
        ]
        for i, (key, label) in enumerate(coord_options):
            r, c = divmod(i, 2)
            ttk.Radiobutton(f_coord, text=label, variable=self.coord_mode, value=key).grid(
                row=r*2, column=c, sticky=tk.W, padx=6, pady=1)
            ttk.Entry(f_coord, textvariable=self.coord_vars[key], state="readonly", width=18).grid(
                row=r*2+1, column=c, padx=6, pady=1, sticky=tk.W)

        # ── 商店格子尺寸 ──
        f_grid = ttk.LabelFrame(self.root, text="商店格子尺寸")
        f_grid.pack(padx=5, pady=4, fill=tk.X)
        ttk.Label(f_grid, text="行数：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_grid, from_=1, to=20, textvariable=self.shop_rows_var, width=6).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(f_grid, text="列数：").grid(row=0, column=2, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_grid, from_=1, to=20, textvariable=self.shop_cols_var, width=6).grid(row=0, column=3, padx=4, pady=2)

        # ── 购买关键词 ──
        f_buy = ttk.LabelFrame(self.root, text="购买目标关键词（匹配任意一个即购买）")
        f_buy.pack(padx=5, pady=4, fill=tk.BOTH, expand=True)
        self._build_kw_panel(f_buy, self.buy_kw_input, self.buy_keywords, "buy")

        # ── 保留关键词 ──
        f_keep = ttk.LabelFrame(self.root, text="背包保留关键词（匹配任意一个则不删除）")
        f_keep.pack(padx=5, pady=4, fill=tk.BOTH, expand=True)
        self._build_kw_panel(f_keep, self.keep_kw_input, self.keep_keywords, "keep")

        # ── 参数 ──
        f_param = ttk.LabelFrame(self.root, text="参数")
        f_param.pack(padx=5, pady=4, fill=tk.X)
        ttk.Label(f_param, text="每购买多少次检查背包：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Spinbox(f_param, from_=1, to=999, textvariable=self.check_interval_var, width=7).grid(row=0, column=1, padx=4, pady=2)

        # ── 控制 ──
        ttk.Label(self.root, text="F3 开始 / 停止", foreground="gray").pack(pady=2)

        # ── 配置按钮 ──
        f_cfg = ttk.Frame(self.root)
        f_cfg.pack(pady=2)
        ttk.Button(f_cfg, text="保存配置", width=12, command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(f_cfg, text="加载配置", width=12, command=self._load_config).pack(side=tk.LEFT, padx=5)

        # ── 状态 / 统计 ──
        f_stat = ttk.LabelFrame(self.root, text="运行状态")
        f_stat.pack(padx=5, pady=4, fill=tk.X)
        ttk.Label(f_stat, textvariable=self.bought_var).grid(row=0, column=0, padx=6, pady=2, sticky=tk.W)
        ttk.Label(f_stat, textvariable=self.time_var).grid(row=0, column=1, padx=6, pady=2, sticky=tk.W)
        ttk.Label(f_stat, textvariable=self.status_var, foreground="blue").grid(row=1, column=0, columnspan=2, padx=6, pady=2, sticky=tk.W)

    def _build_kw_panel(self, parent, input_var, kw_list, tag):
        ttk.Label(parent, text="关键词：").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        ttk.Entry(parent, textvariable=input_var, width=22, font=("Microsoft YaHei", 9)).grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(parent, text="添加", width=7,
                   command=lambda: self._add_kw(input_var, kw_list, lb)).grid(row=0, column=2, padx=4, pady=2)
        lb = Listbox(parent, height=3, font=("Microsoft YaHei", 9))
        lb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=4, pady=2)
        f_btn = ttk.Frame(parent)
        f_btn.grid(row=1, column=2, padx=4, pady=2, sticky=tk.N)
        ttk.Button(f_btn, text="删除", width=7,
                   command=lambda: self._del_kw(kw_list, lb)).pack(pady=1)
        ttk.Button(f_btn, text="清空", width=7,
                   command=lambda: self._clear_kw(kw_list, lb)).pack(pady=1)
        parent.grid_columnconfigure(1, weight=1)
        setattr(self, f"_{tag}_lb", lb)

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

    # ── 坐标捕获 ──
    def _capture(self, mode):
        x, y = pyautogui.position()
        self.coord_vars[mode].set(f"({x}, {y})")
        labels = {
            "shop_tl": "商店左上角", "shop_br": "商店右下角",
            "inv_tl": "背包左上角", "inv_br": "背包右下角",
            "refresh": "刷新按钮",
        }
        self.status_var.set(f"已设置 {labels[mode]}：({x}, {y})")

    def _parse_coords(self):
        """把 GUI 坐标字符串解析回 (x, y) 元组，失败返回 None"""
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

    # ── 运行控制 ──
    def _toggle_run(self):
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
        if not self.keep_keywords:
            if not messagebox.askyesno("提示", "保留关键词为空，清背包时将删除所有物品，确定继续？"):
                return

        self.bot.shop_top_left = coords["shop_tl"]
        self.bot.shop_bot_right = coords["shop_br"]
        self.bot.inv_top_left = coords["inv_tl"]
        self.bot.inv_bot_right = coords["inv_br"]
        self.bot.refresh_pos = coords["refresh"]
        self.bot.shop_rows = self.shop_rows_var.get()
        self.bot.shop_cols = self.shop_cols_var.get()
        self.bot.buy_keywords = self.buy_keywords.copy()
        self.bot.keep_keywords = self.keep_keywords.copy()
        self.bot.check_interval = self.check_interval_var.get()
        self.bot.running = True

        threading.Thread(target=self._run_thread, daemon=True).start()
        self._start_time_thread()
        self.status_var.set("运行中...")

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
        self._time_thread = threading.Thread(target=upd, daemon=True)
        self._time_thread.start()

    # ── 配置保存/加载 ──
    def _save_config(self):
        data = {
            "coords": {k: v.get() for k, v in self.coord_vars.items()},
            "shop_rows": self.shop_rows_var.get(),
            "shop_cols": self.shop_cols_var.get(),
            "check_interval": self.check_interval_var.get(),
            "buy_keywords": self.buy_keywords.copy(),
            "keep_keywords": self.keep_keywords.copy(),
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        self.status_var.set("配置已保存")

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            messagebox.showinfo("提示", "未找到配置文件")
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"加载失败：{e}")
            return

        for k, v in data.get("coords", {}).items():
            if k in self.coord_vars:
                self.coord_vars[k].set(v)
        self.shop_rows_var.set(data.get("shop_rows", 12))
        self.shop_cols_var.set(data.get("shop_cols", 12))
        self.check_interval_var.set(data.get("check_interval", 10))

        self.buy_keywords.clear()
        self._buy_lb.delete(0, tk.END)
        for kw in data.get("buy_keywords", []):
            self.buy_keywords.append(kw)
            self._buy_lb.insert(tk.END, kw)

        self.keep_keywords.clear()
        self._keep_lb.delete(0, tk.END)
        for kw in data.get("keep_keywords", []):
            self.keep_keywords.append(kw)
            self._keep_lb.insert(tk.END, kw)

        self.status_var.set("配置已加载")

    def _on_closing(self):
        self.bot.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    GwennenGUI().run()
