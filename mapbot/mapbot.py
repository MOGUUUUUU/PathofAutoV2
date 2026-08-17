import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import keyboard
import pyautogui
import pyperclip

pyautogui.PAUSE = 0.03
pyautogui.FAILSAFE = True


class MapBot:
    """扫描物品网格并根据目标正则判断物品是否达标。"""

    RESULT_MATCHED = "matched"
    RESULT_EMPTY = "empty"
    RESULT_CORRUPTED = "corrupted"
    RESULT_CURRENCY_FAILED = "currency_failed"
    RESULT_STOPPED = "stopped"

    MODE_SCOUR_ALCHEMY = "scour_alchemy"
    MODE_CHAOS = "chaos"

    def __init__(self):
        self.running = False
        self.top_left = None
        self.bottom_right = None
        self.rows = 12
        self.cols = 12
        self.target_regex = ""
        self.interval = 0.05
        self.start_time = 0
        self.craft_mode = self.MODE_SCOUR_ALCHEMY
        self.scour_pos = None
        self.alchemy_pos = None
        self.chaos_pos = None
        self.last_error = ""

    @staticmethod
    def get_cell_positions(top_left, bottom_right, rows, cols):
        """按行优先计算网格中心坐标。"""
        if not top_left or not bottom_right:
            raise ValueError("物品区域坐标未设置")
        if rows <= 0 or cols <= 0:
            raise ValueError("行数和列数必须大于 0")
        if bottom_right[0] <= top_left[0] or bottom_right[1] <= top_left[1]:
            raise ValueError("右下角坐标必须位于左上角右下方")

        x0, y0 = top_left
        x1, y1 = bottom_right
        cell_w = (x1 - x0) / cols
        cell_h = (y1 - y0) / rows
        positions = []
        for row in range(rows):
            for col in range(cols):
                x = int(x0 + cell_w * (col + 0.5))
                y = int(y0 + cell_h * (row + 0.5))
                positions.append((x, y))
        return positions

    @staticmethod
    def compile_pattern(pattern):
        """编译目标正则，统一扫描和测试工具的匹配语义。"""
        pattern = pattern.strip()
        if not pattern:
            raise ValueError("目标正则不能为空")
        try:
            return re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"目标正则无效：{exc}") from exc

    @classmethod
    def matches_target(cls, text, pattern):
        """在完整物品信息中查找目标正则。"""
        if not text:
            return False
        return cls.compile_pattern(pattern).search(text) is not None

    def compile_target(self):
        """编译当前配置的目标正则。"""
        return self.compile_pattern(self.target_regex)

    def read_item(self, pos):
        """悬停到物品格子，用 Ctrl+Alt+C 读取物品信息。"""
        if not self.running:
            return ""
        pyautogui.moveTo(pos)
        pyperclip.copy("")
        for _ in range(3):
            if not self.running:
                return ""
            pyautogui.hotkey("ctrl", "alt", "c")
            self.rand_sleep(0.01)
        return pyperclip.paste()

    def rand_sleep(self, base=None, jitter=0.01):
        """等待一小段时间，并在停止时尽快返回。"""
        delay = self.interval if base is None else base
        end = time.monotonic() + delay + jitter
        while self.running and time.monotonic() < end:
            time.sleep(min(0.01, end - time.monotonic()))

    @staticmethod
    def is_corrupted(text):
        """物品信息包含独立的“已腐化”状态行时视为腐化。"""
        return any(line.strip() == "已腐化" for line in text.splitlines())

    def use_orb(self, orb_pos, item_pos):
        """右键选中通货，再左键应用到物品。"""
        if not self.running:
            return False
        pyautogui.moveTo(orb_pos, duration=0.05)
        self.rand_sleep()
        if not self.running:
            return False
        pyautogui.click(button="right")
        self.rand_sleep()
        if not self.running:
            return False
        pyautogui.moveTo(item_pos, duration=0.05)
        self.rand_sleep()
        if not self.running:
            return False
        pyautogui.click(button="left")
        self.rand_sleep()
        return self.running

    def use_currency(self, item_pos):
        """按当前模式完成一轮洗图通货操作。"""
        if self.craft_mode == self.MODE_CHAOS:
            return self.use_orb(self.chaos_pos, item_pos)
        if not self.use_orb(self.scour_pos, item_pos):
            return False
        return self.use_orb(self.alchemy_pos, item_pos)

    def process_one_item(self, pos, pattern):
        """循环洗当前物品，直到达标、跳过或通货操作失败。"""
        previous_text = None
        while self.running:
            text = self.read_item(pos)
            if not self.running:
                return self.RESULT_STOPPED
            if not text:
                return self.RESULT_EMPTY
            if previous_text is not None and text == previous_text:
                self.last_error = "通货操作未改变物品，可能通货不足、坐标错误或物品不可使用该通货"
                return self.RESULT_CURRENCY_FAILED
            if self.is_corrupted(text):
                return self.RESULT_CORRUPTED
            if pattern.search(text):
                return self.RESULT_MATCHED

            previous_text = text
            if not self.use_currency(pos):
                return self.RESULT_STOPPED
        return self.RESULT_STOPPED

    def run(self, status_cb=None, item_cb=None):
        """按行优先扫描一轮物品区域。"""
        self.last_error = ""
        pattern = self.compile_target()
        positions = self.get_cell_positions(
            self.top_left, self.bottom_right, self.rows, self.cols
        )
        total = len(positions)
        self.start_time = time.time()

        for index, pos in enumerate(positions, 1):
            if not self.running:
                return False
            if status_cb:
                status_cb(f"正在读取第 {index}/{total} 个物品")
            matched = self.process_one_item(pos, pattern)
            if not self.running:
                return False
            if item_cb:
                item_cb(index, total, matched)
            if matched == self.RESULT_MATCHED:
                if status_cb:
                    status_cb(f"第 {index} 个物品满足目标，切换下一个")
            elif matched == self.RESULT_EMPTY:
                if status_cb:
                    status_cb(f"第 {index} 个格子为空，切换下一个")
            elif matched == self.RESULT_CORRUPTED:
                if status_cb:
                    status_cb(f"第 {index} 个物品已腐化，跳过")
            elif matched == self.RESULT_CURRENCY_FAILED:
                detail = self.last_error or "通货操作未生效"
                if status_cb:
                    status_cb(f"第 {index} 个物品{detail}，停止扫描")
                return False
            else:
                return False
            self.rand_sleep()

        if status_cb:
            status_cb("本轮物品扫描完成")
        return True


class MapBotPanel:
    """MapBot 的紧凑 Tk 面板。"""

    def __init__(self, root):
        self.root = root
        self.bot = MapBot()
        self.config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "mapbot.json"
        )
        self.hotkeys = []
        self.time_job = None

        self.status_var = tk.StringVar(value="状态：未运行")
        self.current_var = tk.StringVar(value="物品：0/0")
        self.time_var = tk.StringVar(value="运行时间：00:00:00")
        self.coord_mode = tk.StringVar(value="top_left")
        self.coord_vars = {
            "top_left": tk.StringVar(value="未设置"),
            "bottom_right": tk.StringVar(value="未设置"),
            "scour_pos": tk.StringVar(value="未设置"),
            "alchemy_pos": tk.StringVar(value="未设置"),
            "chaos_pos": tk.StringVar(value="未设置"),
        }
        self.rows_var = tk.IntVar(value=12)
        self.cols_var = tk.IntVar(value=12)
        self.craft_mode_var = tk.StringVar(value=MapBot.MODE_SCOUR_ALCHEMY)
        self.target_var = tk.StringVar()
        self.interval_var = tk.StringVar(value="0.05")
        self.test_pattern_var = tk.StringVar()
        self.test_result_var = tk.StringVar(value="请输入目标正则和物品文本")
        self.test_text = None

        self._build_ui()
        self._load_config(silent=True)
        self._register_hotkeys()

    def _build_ui(self):
        self.root.title("POE 地图物品机器人")
        self.root.geometry("580x650")
        self.root.minsize(540, 590)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        scan_frame = ttk.Frame(notebook)
        test_frame = ttk.Frame(notebook)
        notebook.add(scan_frame, text="地图扫描")
        notebook.add(test_frame, text="正则测试")

        self._build_scan_tab(scan_frame)
        self._build_regex_tab(test_frame)

    def _build_scan_tab(self, parent):
        f_coord = ttk.LabelFrame(
            parent, text="坐标设置（选择类型后将鼠标移到位置按 =）"
        )
        f_coord.pack(padx=8, pady=(8, 4), fill=tk.X)
        for row, (key, label) in enumerate(
            (
                ("top_left", "左上角格子"),
                ("bottom_right", "右下角格子"),
                ("scour_pos", "重铸石"),
                ("alchemy_pos", "点金石"),
                ("chaos_pos", "混沌石"),
            )
        ):
            ttk.Radiobutton(
                f_coord, text=label, variable=self.coord_mode, value=key
            ).grid(row=row, column=0, padx=6, pady=3, sticky=tk.W)
            ttk.Entry(
                f_coord, textvariable=self.coord_vars[key], state="readonly", width=20
            ).grid(row=row, column=1, padx=6, pady=3, sticky=tk.W)
        f_coord.columnconfigure(1, weight=1)

        f_grid = ttk.LabelFrame(parent, text="网格尺寸")
        f_grid.pack(padx=8, pady=4, fill=tk.X)
        ttk.Label(f_grid, text="行数：").grid(
            row=0, column=0, padx=6, pady=4, sticky=tk.W
        )
        ttk.Spinbox(f_grid, from_=1, to=100, textvariable=self.rows_var, width=8).grid(
            row=0, column=1, padx=4, pady=4, sticky=tk.W
        )
        ttk.Label(f_grid, text="列数：").grid(
            row=0, column=2, padx=6, pady=4, sticky=tk.W
        )
        ttk.Spinbox(f_grid, from_=1, to=100, textvariable=self.cols_var, width=8).grid(
            row=0, column=3, padx=4, pady=4, sticky=tk.W
        )

        f_target = ttk.LabelFrame(parent, text="目标设置")
        f_target.pack(padx=8, pady=4, fill=tk.X)
        ttk.Label(f_target, text="目标正则：").grid(
            row=0, column=0, padx=6, pady=5, sticky=tk.W
        )
        ttk.Entry(f_target, textvariable=self.target_var, width=42).grid(
            row=0, column=1, padx=6, pady=5, sticky=tk.EW
        )
        ttk.Label(f_target, text="匹配成功后切换下一个物品").grid(
            row=1, column=1, padx=6, pady=(0, 5), sticky=tk.W
        )
        f_target.columnconfigure(1, weight=1)

        f_craft = ttk.LabelFrame(parent, text="制作方式")
        f_craft.pack(padx=8, pady=4, fill=tk.X)
        ttk.Radiobutton(
            f_craft,
            text="重铸点金洗",
            variable=self.craft_mode_var,
            value=MapBot.MODE_SCOUR_ALCHEMY,
        ).pack(side=tk.LEFT, padx=6, pady=5)
        ttk.Radiobutton(
            f_craft,
            text="混沌洗",
            variable=self.craft_mode_var,
            value=MapBot.MODE_CHAOS,
        ).pack(side=tk.LEFT, padx=6, pady=5)

        f_control = ttk.LabelFrame(parent, text="运行设置")
        f_control.pack(padx=8, pady=4, fill=tk.X)
        ttk.Label(f_control, text="操作间隔（秒）：").pack(
            side=tk.LEFT, padx=(6, 2), pady=5
        )
        ttk.Entry(f_control, textvariable=self.interval_var, width=8).pack(
            side=tk.LEFT, padx=3, pady=5
        )
        ttk.Label(f_control, text="F3 开始 / 停止", foreground="gray").pack(
            side=tk.RIGHT, padx=6, pady=5
        )

        f_stat = ttk.LabelFrame(parent, text="运行状态")
        f_stat.pack(padx=8, pady=4, fill=tk.X)
        ttk.Label(f_stat, textvariable=self.current_var).grid(
            row=0, column=0, padx=6, pady=3, sticky=tk.W
        )
        ttk.Label(f_stat, textvariable=self.time_var).grid(
            row=0, column=1, padx=6, pady=3, sticky=tk.W
        )
        ttk.Label(f_stat, textvariable=self.status_var, foreground="blue").grid(
            row=1, column=0, columnspan=2, padx=6, pady=3, sticky=tk.W
        )
        f_stat.columnconfigure(1, weight=1)

        f_config = ttk.Frame(parent)
        f_config.pack(pady=5)
        ttk.Button(f_config, text="保存配置", command=self._save_config).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(f_config, text="加载配置", command=self._load_config).pack(
            side=tk.LEFT, padx=5
        )

    def _build_regex_tab(self, parent):
        f_pattern = ttk.LabelFrame(parent, text="目标正则")
        f_pattern.pack(padx=8, pady=(8, 4), fill=tk.X)
        ttk.Entry(f_pattern, textvariable=self.test_pattern_var).pack(
            padx=6, pady=6, fill=tk.X
        )

        f_text = ttk.LabelFrame(parent, text="物品文本（粘贴 Ctrl+Alt+C 内容）")
        f_text.pack(padx=8, pady=4, fill=tk.BOTH, expand=True)
        self.test_text = tk.Text(f_text, wrap=tk.WORD, height=16, undo=True)
        scrollbar = ttk.Scrollbar(f_text, command=self.test_text.yview)
        self.test_text.configure(yscrollcommand=scrollbar.set)
        self.test_text.grid(row=0, column=0, padx=(6, 0), pady=6, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, padx=(0, 6), pady=6, sticky=tk.NS)
        self.test_text.tag_configure("match", background="#fff2a8")
        f_text.rowconfigure(0, weight=1)
        f_text.columnconfigure(0, weight=1)

        f_actions = ttk.Frame(parent)
        f_actions.pack(padx=8, pady=4, fill=tk.X)
        ttk.Button(f_actions, text="测试正则", command=self._test_regex).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(f_actions, text="导入到主页面", command=self._import_test_regex).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(f_actions, text="清空文本", command=self._clear_test_text).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            f_actions, textvariable=self.test_result_var, foreground="blue"
        ).pack(side=tk.LEFT, padx=10)

    def _test_regex(self):
        self.test_text.tag_remove("match", "1.0", tk.END)
        text = self.test_text.get("1.0", "end-1c")
        if not text:
            self.test_result_var.set("请输入物品文本")
            return
        try:
            pattern = MapBot.compile_pattern(self.test_pattern_var.get())
        except ValueError as exc:
            self.test_result_var.set(str(exc))
            return

        match = pattern.search(text)
        if not match:
            self.test_result_var.set("未匹配")
            return

        self.test_result_var.set("匹配成功")
        start, end = match.span()
        if start != end:
            self.test_text.tag_add("match", f"1.0+{start}c", f"1.0+{end}c")
            self.test_text.see(f"1.0+{start}c")

    def _import_test_regex(self):
        pattern = self.test_pattern_var.get().strip()
        try:
            MapBot.compile_pattern(pattern)
        except ValueError as exc:
            self.test_result_var.set(str(exc))
            return

        self.target_var.set(pattern)
        self.test_result_var.set("正则已导入主页面")

    def _clear_test_text(self):
        self.test_text.delete("1.0", tk.END)
        self.test_result_var.set("请输入目标正则和物品文本")

    def _register_hotkeys(self):
        self.hotkeys.append(keyboard.add_hotkey("f3", self._toggle_run))
        self.hotkeys.append(keyboard.add_hotkey("=", self._capture_coord))

    def _capture_coord(self):
        x, y = pyautogui.position()
        key = self.coord_mode.get()
        self.root.after(0, self._set_coord, key, x, y)

    def _set_coord(self, key, x, y):
        self.coord_vars[key].set(f"({x}, {y})")
        labels = {
            "top_left": "左上角格子",
            "bottom_right": "右下角格子",
            "scour_pos": "重铸石",
            "alchemy_pos": "点金石",
            "chaos_pos": "混沌石",
        }
        self.status_var.set(f"已设置 {labels[key]}：({x}, {y})")

    @staticmethod
    def _parse_coord(value):
        value = value.strip().strip("()")
        parts = value.split(",")
        if len(parts) != 2:
            return None
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except ValueError:
            return None

    def _read_form(self):
        top_left = self._parse_coord(self.coord_vars["top_left"].get())
        bottom_right = self._parse_coord(self.coord_vars["bottom_right"].get())
        try:
            rows = int(self.rows_var.get())
            cols = int(self.cols_var.get())
            interval = float(self.interval_var.get())
        except (TypeError, ValueError) as exc:
            raise ValueError("行数、列数和操作间隔格式不正确") from exc

        if top_left is None or bottom_right is None:
            raise ValueError("请先设置左上角和右下角坐标")
        if rows <= 0 or cols <= 0:
            raise ValueError("行数和列数必须大于 0")
        if interval < 0:
            raise ValueError("操作间隔必须大于等于 0")
        if bottom_right[0] <= top_left[0] or bottom_right[1] <= top_left[1]:
            raise ValueError("右下角坐标必须位于左上角右下方")
        scour_pos = self._parse_coord(self.coord_vars["scour_pos"].get())
        alchemy_pos = self._parse_coord(self.coord_vars["alchemy_pos"].get())
        chaos_pos = self._parse_coord(self.coord_vars["chaos_pos"].get())
        craft_mode = self.craft_mode_var.get()
        if craft_mode not in (MapBot.MODE_SCOUR_ALCHEMY, MapBot.MODE_CHAOS):
            raise ValueError("制作方式无效")
        if craft_mode == MapBot.MODE_SCOUR_ALCHEMY:
            if scour_pos is None or alchemy_pos is None:
                raise ValueError("重铸点金洗需要设置重铸石和点金石坐标")
        elif chaos_pos is None:
            raise ValueError("混沌洗需要设置混沌石坐标")
        target = self.target_var.get().strip()
        MapBot.compile_pattern(target)
        return (
            top_left,
            bottom_right,
            rows,
            cols,
            target,
            interval,
            craft_mode,
            scour_pos,
            alchemy_pos,
            chaos_pos,
        )

    def _apply_form(self):
        values = self._read_form()
        (
            self.bot.top_left,
            self.bot.bottom_right,
            self.bot.rows,
            self.bot.cols,
            self.bot.target_regex,
            self.bot.interval,
            self.bot.craft_mode,
            self.bot.scour_pos,
            self.bot.alchemy_pos,
            self.bot.chaos_pos,
        ) = values

    def _toggle_run(self):
        if self.bot.running:
            self.bot.running = False
            self._set_status("已停止")
            return
        self._start()

    def _start(self):
        try:
            self._apply_form()
        except ValueError as exc:
            self.root.after(0, lambda: messagebox.showwarning("警告", str(exc)))
            return

        self.bot.running = True
        self.bot.start_time = time.time()
        self._set_status("运行中...")
        threading.Thread(target=self._run_worker, daemon=True).start()
        self._start_time_update()

    def _run_worker(self):
        completed = False
        error = None
        try:
            completed = self.bot.run(
                status_cb=lambda text: self._set_status(text),
                item_cb=self._set_current,
            )
        except Exception as exc:
            error = exc
        finally:
            failure_detail = self.bot.last_error
            self.bot.running = False
            if error:
                self._set_status(f"运行异常：{error}")
            elif completed:
                self._set_status("本轮物品扫描完成")
            elif failure_detail:
                self._set_status(failure_detail)
            else:
                self._set_status("已停止")

    def _set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(f"状态：{text}"))

    def _set_current(self, index, total, matched):
        labels = {
            MapBot.RESULT_MATCHED: "匹配",
            MapBot.RESULT_EMPTY: "空格",
            MapBot.RESULT_CORRUPTED: "腐化跳过",
            MapBot.RESULT_CURRENCY_FAILED: "通货失败",
            MapBot.RESULT_STOPPED: "已停止",
        }
        result = labels.get(matched, "未知")
        self.root.after(
            0, lambda: self.current_var.set(f"物品：{index}/{total}（{result}）")
        )

    def _start_time_update(self):
        if self.time_job:
            self.root.after_cancel(self.time_job)
        self._update_time()

    def _update_time(self):
        if self.bot.running:
            used = int(time.time() - self.bot.start_time)
            self.time_var.set(
                f"运行时间：{used // 3600:02d}:{used % 3600 // 60:02d}:{used % 60:02d}"
            )
            self.time_job = self.root.after(200, self._update_time)
        else:
            self.time_job = None

    def _config_data(self):
        return {
            "top_left": self._parse_coord(self.coord_vars["top_left"].get()),
            "bottom_right": self._parse_coord(self.coord_vars["bottom_right"].get()),
            "rows": self.rows_var.get(),
            "cols": self.cols_var.get(),
            "target_regex": self.target_var.get(),
            "interval": self.interval_var.get(),
            "craft_mode": self.craft_mode_var.get(),
            "scour_pos": self._parse_coord(self.coord_vars["scour_pos"].get()),
            "alchemy_pos": self._parse_coord(self.coord_vars["alchemy_pos"].get()),
            "chaos_pos": self._parse_coord(self.coord_vars["chaos_pos"].get()),
        }

    def _save_config(self):
        try:
            self._apply_form()
            with open(self.config_file, "w", encoding="utf-8") as file:
                json.dump(self._config_data(), file, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as exc:
            messagebox.showerror("错误", f"配置保存失败：{exc}")
            return
        self.status_var.set(f"配置已保存：{self.config_file}")

    def _load_config(self, silent=False):
        if not os.path.exists(self.config_file):
            if not silent:
                messagebox.showinfo("提示", "未找到配置文件")
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as file:
                config = json.load(file)
            for key in (
                "top_left",
                "bottom_right",
                "scour_pos",
                "alchemy_pos",
                "chaos_pos",
            ):
                coord = config.get(key)
                if isinstance(coord, (list, tuple)) and len(coord) == 2:
                    self.coord_vars[key].set(f"({int(coord[0])}, {int(coord[1])})")
                else:
                    self.coord_vars[key].set("未设置")
            craft_mode = str(config.get("craft_mode", MapBot.MODE_SCOUR_ALCHEMY))
            if craft_mode not in (MapBot.MODE_SCOUR_ALCHEMY, MapBot.MODE_CHAOS):
                craft_mode = MapBot.MODE_SCOUR_ALCHEMY
            self.craft_mode_var.set(craft_mode)
            self.rows_var.set(int(config.get("rows", 12)))
            self.cols_var.set(int(config.get("cols", 12)))
            self.target_var.set(str(config.get("target_regex", "")))
            self.interval_var.set(str(config.get("interval", 0.05)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if not silent:
                messagebox.showerror("错误", f"配置加载失败：{exc}")
            return
        if not silent:
            self.status_var.set("配置已加载")

    def _on_closing(self):
        self.bot.running = False
        for hotkey in self.hotkeys:
            try:
                keyboard.remove_hotkey(hotkey)
            except (KeyError, ValueError):
                pass
        if self.time_job:
            self.root.after_cancel(self.time_job)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    MapBotPanel(root)
    root.mainloop()
