import pyautogui
import random
import time
import json
import os
import pyperclip
import threading
import winsound
import keyboard
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import Listbox, Scrollbar

pyautogui.PAUSE = 0.035

# ──────────────────────────────────────────────
# 公共 Bot 基类
# ──────────────────────────────────────────────
class PoeOrbBotBase:
    def __init__(self):
        self.running = False
        self.transmutation_count = 0
        self.alter_count = 0
        self.augment_count = 0
        self.start_time = 0
        self.config = {
            "alter_positions": [],
            "augment_positions": [],
            "transmutation_pos": None,
            "item_positions": [],
            "target_affixes": [],
            "interval": 0.02,
        }
        self.config_file = "poe_orb_config.json"
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for key in ["item_positions", "alter_positions", "augment_positions"]:
                    if key in loaded:
                        loaded[key] = [list(p) if isinstance(p, (list, tuple)) else p for p in loaded[key]]
                self.config.update(loaded)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self, path=None):
        path = path or self.config_file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def rand_sleep(self, base=None, rand_range=0.001):
        if not base:
            base = self.config["interval"]
        time.sleep(base + random.random() * rand_range)

    def beep(self, freq=1000, dur=500):
        try:
            winsound.Beep(freq, dur)
        except:
            winsound.MessageBeep()

    def get_item_info(self):
        pyperclip.copy("")
        for _ in range(3):
            pyautogui.hotkey('ctrl', 'alt', 'c')
            self.rand_sleep(0.05)
        return pyperclip.paste()

    def has_target_affix(self, text, need_count):
        if not text or not self.config["target_affixes"]:
            return False
        cnt = sum(1 for t in self.config["target_affixes"] if t in text)
        return cnt >= need_count

    def check_item(self, item_pos, need_count):
        pyautogui.moveTo(item_pos, duration=0.05)
        self.rand_sleep()
        return self.has_target_affix(self.get_item_info(), need_count)

    def use_orb(self, orb_name, item_pos=None):
        if orb_name in ("alter", "augment"):
            poses = self.config.get(f"{orb_name}_positions")
        else:
            p = self.config.get(f"{orb_name}_pos")
            if not p:
                raise RuntimeError(f"{orb_name} 未设置坐标")
            poses = [p]
        if not poses:
            raise RuntimeError(f"{orb_name} 坐标列表为空")

        pos = random.choice(poses)
        pyautogui.moveTo(pos, duration=0.05)
        self.rand_sleep()
        pyautogui.click(button='right')
        self.rand_sleep()
        if item_pos:
            pyautogui.moveTo(item_pos, duration=0.05)
            self.rand_sleep()
            pyautogui.click(button='left')
            self.rand_sleep()
        attr = f"{orb_name}_count"
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + 1)


# ──────────────────────────────────────────────
# 简化版 Bot（3种宝珠：蜕变→增幅⟷改造）
# ──────────────────────────────────────────────
class PoeOrbBotSimple(PoeOrbBotBase):
    def process_one_item(self, item_pos) -> bool:
        if not self.running:
            return False
        STATE_INIT, STATE_AUGMENT, STATE_CHECK_AUG, STATE_ALTER, STATE_CHECK_ALT = (
            "init", "augment", "check_aug", "alter", "check_alt"
        )
        state = STATE_INIT
        while self.running:
            try:
                if state == STATE_INIT:
                    self.use_orb("transmutation", item_pos)
                    self.rand_sleep(0.15)
                    state = STATE_AUGMENT
                elif state == STATE_AUGMENT:
                    self.use_orb("augment", item_pos)
                    self.rand_sleep(0.05)
                    state = STATE_CHECK_AUG
                elif state == STATE_CHECK_AUG:
                    if self.check_item(item_pos, 1):
                        self.beep(1200, 600)
                        return True
                    state = STATE_ALTER
                elif state == STATE_ALTER:
                    self.use_orb("alter", item_pos)
                    self.rand_sleep(0.05)
                    state = STATE_CHECK_ALT
                elif state == STATE_CHECK_ALT:
                    if self.check_item(item_pos, 1):
                        self.beep(1200, 600)
                        return True
                    state = STATE_AUGMENT
                time.sleep(0.01)
            except Exception as e:
                print("异常:", e)
                self.rand_sleep(0.1)
        return False


# ──────────────────────────────────────────────
# 完整版 Bot（7种宝珠：蜕变→改造→增幅→富豪→崇高→剥离→重铸）
# ──────────────────────────────────────────────
class PoeOrbBotFull(PoeOrbBotBase):
    def __init__(self):
        self.regal_count = 0
        self.extend_count = 0
        self.scouring_count = 0
        self.annulment_count = 0
        super().__init__()
        # 补充完整版独有配置默认值
        self.config.setdefault("regal_pos", None)
        self.config.setdefault("extend_pos", None)
        self.config.setdefault("scouring_pos", None)
        self.config.setdefault("annulment_pos", None)

    def process_one_item(self, item_pos) -> bool:
        if not self.running:
            return False
        (STATE_START, STATE_TRANSMUTATION, STATE_ALTER, STATE_AUGMENT,
         STATE_REGAL, STATE_EXTEND, STATE_ANNUL, STATE_SCOUR, STATE_SUCCESS) = (
            "start", "transmutation", "alter", "augment",
            "regal", "extend", "annul", "scour", "success"
        )
        state = STATE_START
        while self.running:
            if state == STATE_START:
                state = STATE_TRANSMUTATION
            elif state == STATE_TRANSMUTATION:
                self.use_orb("transmutation", item_pos)
                state = STATE_AUGMENT if self.check_item(item_pos, 1) else STATE_ALTER
            elif state == STATE_ALTER:
                self.use_orb("alter", item_pos)
                state = STATE_AUGMENT if self.check_item(item_pos, 1) else STATE_ALTER
            elif state == STATE_AUGMENT:
                if self.config.get("use_augment", True):
                    self.use_orb("augment", item_pos)
                state = STATE_REGAL if self.check_item(item_pos, 2) else STATE_ALTER
            elif state == STATE_REGAL:
                if self.config.get("use_regal", True):
                    self.use_orb("regal", item_pos)
                state = STATE_EXTEND if self.check_item(item_pos, 3) else STATE_SCOUR
            elif state == STATE_EXTEND:
                if self.config.get("use_extend", True):
                    self.use_orb("extend", item_pos)
                state = STATE_SUCCESS if self.check_item(item_pos, 4) else STATE_ANNUL
            elif state == STATE_ANNUL:
                if self.config.get("use_annulment", True):
                    self.use_orb("annulment", item_pos)
                state = STATE_EXTEND if self.check_item(item_pos, 3) else STATE_SCOUR
            elif state == STATE_SCOUR:
                if self.config.get("use_scouring", True):
                    self.use_orb("scouring", item_pos)
                state = STATE_TRANSMUTATION
            elif state == STATE_SUCCESS:
                return True
            time.sleep(0.001)
        return False


# ──────────────────────────────────────────────
# 通用 Tab 面板（坐标+物品+词缀+统计）
# ──────────────────────────────────────────────
class BotTabPanel:
    """为一个 bot 实例构建完整的 Tab 面板，可传入不同的 ORB_NAMES 定制显示。"""

    def __init__(self, parent_notebook, bot: PoeOrbBotBase, tab_name: str, orb_names: dict):
        self.bot = bot
        self.orb_names = orb_names  # {key: 中文名}
        self.target_affixes = bot.config["target_affixes"].copy()

        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text=tab_name)

        self.coord_type = tk.StringVar(value=next(iter(orb_names)))
        self.current_item_var = tk.StringVar(value="0/0")
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="状态：未运行")
        self.affix_input_var = tk.StringVar()

        self.orb_coord_vars = {}
        self.orb_count_vars = {}
        self.alter_tree = None
        self.augment_tree = None
        self.time_thread = None

        self._init_vars()
        self._create_widgets()

    def _init_vars(self):
        for k in self.orb_names:
            if k not in ("alter", "augment"):
                pos = self.bot.config.get(f"{k}_pos")
                self.orb_coord_vars[k] = tk.StringVar(value=f"({pos[0]},{pos[1]})" if pos else "未设置")
            self.orb_count_vars[k] = tk.StringVar(value="0")
        self.interval_var = tk.StringVar(value=str(self.bot.config.get("interval", 0.02)))

    def _create_widgets(self):
        # 1. 坐标设置
        f_coord = ttk.LabelFrame(self.frame, text="坐标设置（鼠标移过去按 =）")
        f_coord.pack(padx=5, pady=3, fill=tk.BOTH, expand=False)
        row = 0
        for k, name in self.orb_names.items():
            if k in ("alter", "augment"):
                ttk.Radiobutton(f_coord, text=name, variable=self.coord_type, value=k).grid(
                    row=row, column=0, sticky=tk.W, padx=2, pady=1)
                tree = ttk.Treeview(f_coord, columns=("i", "p"), show="headings", height=2)
                tree.heading("i", text="序号"); tree.heading("p", text="坐标")
                tree.column("i", width=50, anchor=tk.CENTER)
                tree.column("p", width=120, anchor=tk.CENTER)
                tree.grid(row=row, column=1, columnspan=2, sticky=tk.NSEW, padx=2, pady=1)
                if k == "alter":
                    self.alter_tree = tree
                    self._update_alter_tree()
                else:
                    self.augment_tree = tree
                    self._update_augment_tree()
                ttk.Button(f_coord, text="删除", width=6,
                           command=lambda k=k: self._del_orb(k)).grid(row=row, column=3, padx=2)
                row += 1
            else:
                ttk.Radiobutton(f_coord, text=name, variable=self.coord_type, value=k).grid(
                    row=row, column=0, sticky=tk.W, padx=2, pady=1)
                ttk.Entry(f_coord, textvariable=self.orb_coord_vars[k],
                          state="readonly", width=16).grid(row=row, column=1, padx=2, pady=1)
                row += 1
        ttk.Radiobutton(f_coord, text="物品坐标", variable=self.coord_type, value="item").grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=2, pady=1)
        f_coord.grid_columnconfigure(1, weight=1)

        # 2. 物品列表
        f_item = ttk.LabelFrame(self.frame, text="物品列表")
        f_item.pack(padx=5, pady=3, fill=tk.BOTH, expand=True)
        self.item_tree = ttk.Treeview(f_item, columns=("i", "p"), show="headings", height=3)
        self.item_tree.heading("i", text="序号"); self.item_tree.heading("p", text="坐标")
        self.item_tree.column("i", width=50, anchor=tk.CENTER)
        self.item_tree.column("p", width=120, anchor=tk.CENTER)
        self.item_tree.grid(row=0, column=0, columnspan=3, sticky=tk.NSEW, padx=2, pady=2)
        sb = ttk.Scrollbar(f_item, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=3, sticky=tk.NS, pady=2)
        f_btn = ttk.Frame(f_item)
        f_btn.grid(row=1, column=0, columnspan=4)
        ttk.Button(f_btn, text="添加物品", command=lambda: self.get_coord("item")).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(f_btn, text="删除选中", command=self._del_item).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(f_btn, text="清空", command=self._clear_item).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        f_item.grid_rowconfigure(0, weight=1)
        f_item.grid_columnconfigure(0, weight=1)
        self._update_item_tree()

        # 3. 目标词缀
        f_affix = ttk.LabelFrame(self.frame, text="目标词缀")
        f_affix.pack(padx=5, pady=3, fill=tk.X)
        ttk.Label(f_affix, text="词缀：").grid(row=0, column=0, sticky=tk.W, padx=2, pady=1)
        ttk.Entry(f_affix, textvariable=self.affix_input_var, width=22).grid(row=0, column=1, padx=2, pady=1)
        ttk.Button(f_affix, text="添加", command=self._add_affix, width=8).grid(row=0, column=2, padx=2, pady=1)
        self.affix_list = Listbox(f_affix, height=3)
        self.affix_list.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=2, pady=1)
        sba = ttk.Scrollbar(f_affix, command=self.affix_list.yview)
        self.affix_list.configure(yscrollcommand=sba.set)
        sba.grid(row=1, column=2, sticky=tk.NS, pady=1)
        f_abtn = ttk.Frame(f_affix)
        f_abtn.grid(row=2, column=0, columnspan=3, pady=1)
        ttk.Button(f_abtn, text="删除选中", command=self._del_affix).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(f_abtn, text="清空", command=self._clear_affixes).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        f_affix.grid_columnconfigure(1, weight=1)
        self._update_affix()

        # 4. 运行设置（操作间隔 + 控制提示）
        f_ctrl = ttk.LabelFrame(self.frame, text="运行设置")
        f_ctrl.pack(padx=5, pady=3, fill=tk.X)
        ttk.Label(f_ctrl, text="操作间隔(秒)：").pack(side=tk.LEFT, padx=(5, 2), pady=3)
        ttk.Entry(f_ctrl, textvariable=self.interval_var, width=8).pack(side=tk.LEFT, padx=2, pady=3)
        ttk.Label(f_ctrl, text="（各操作之间的基础等待时间）", foreground="gray").pack(side=tk.LEFT, padx=2)
        ttk.Label(f_ctrl, text="F3 开始 / 停止", foreground="gray").pack(side=tk.RIGHT, padx=5)

        # 5. 统计
        f_stat = ttk.LabelFrame(self.frame, text="统计信息")
        f_stat.pack(padx=5, pady=3, fill=tk.X)
        for i, (k, name) in enumerate(self.orb_names.items()):
            r, c = divmod(i, 4)
            c *= 2
            ttk.Label(f_stat, text=f"{name}：", font=('', 8)).grid(row=r, column=c, padx=1, pady=1, sticky=tk.W)
            ttk.Entry(f_stat, textvariable=self.orb_count_vars[k], state="readonly", width=8).grid(
                row=r, column=c + 1, padx=1, pady=1)
        last_row = (len(self.orb_names) - 1) // 4 + 1
        ttk.Label(f_stat, text="物品：", font=('', 8)).grid(row=last_row, column=0, padx=1, pady=1, sticky=tk.W)
        ttk.Entry(f_stat, textvariable=self.current_item_var, state="readonly", width=8).grid(
            row=last_row, column=1, padx=1, pady=1)
        ttk.Label(f_stat, text="时间：", font=('', 8)).grid(row=last_row, column=2, padx=1, pady=1, sticky=tk.W)
        ttk.Entry(f_stat, textvariable=self.time_var, state="readonly", width=8).grid(
            row=last_row, column=3, padx=1, pady=1)

        # 6. 状态
        ttk.Label(self.frame, textvariable=self.status_var, foreground="blue", font=('', 9)).pack(pady=2)

        # 7. 配置
        f_cfg = ttk.Frame(self.frame)
        f_cfg.pack(pady=2)
        ttk.Button(f_cfg, text="保存配置", command=self._save, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(f_cfg, text="加载配置", command=self._load, width=12).pack(side=tk.LEFT, padx=5)

    # ── 坐标获取 ──
    def get_coord(self, t):
        x, y = pyautogui.position()
        if t == "item":
            self.bot.config["item_positions"].append((x, y))
            self._update_item_tree()
            self.status_var.set(f"已添加物品坐标 ({x},{y})")
        elif t == "alter":
            self.bot.config["alter_positions"].append((x, y))
            self._update_alter_tree()
            self.status_var.set(f"已添加改造石坐标 ({x},{y})")
        elif t == "augment":
            self.bot.config["augment_positions"].append((x, y))
            self._update_augment_tree()
            self.status_var.set(f"已添加增幅石坐标 ({x},{y})")
        elif t in self.orb_names:
            self.bot.config[f"{t}_pos"] = (x, y)
            self.orb_coord_vars[t].set(f"({x},{y})")
            self.status_var.set(f"已设置 {self.orb_names[t]} 坐标")

    def bind_equal_key(self, root):
        root.bind('<equal>', lambda e: self.get_coord(self.coord_type.get()))

    # ── 树形控件更新 ──
    def _update_alter_tree(self):
        if not self.alter_tree:
            return
        for i in self.alter_tree.get_children():
            self.alter_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["alter_positions"], 1):
            self.alter_tree.insert("", "end", values=(idx, f"({x},{y})"))

    def _update_augment_tree(self):
        if not self.augment_tree:
            return
        for i in self.augment_tree.get_children():
            self.augment_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["augment_positions"], 1):
            self.augment_tree.insert("", "end", values=(idx, f"({x},{y})"))

    def _del_orb(self, k):
        lst = self.bot.config[f"{k}_positions"]
        tree = self.alter_tree if k == "alter" else self.augment_tree
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要删除的坐标")
            return
        idx = int(tree.item(sel[0])["values"][0]) - 1
        del lst[idx]
        self._update_alter_tree() if k == "alter" else self._update_augment_tree()

    def _update_item_tree(self):
        for i in self.item_tree.get_children():
            self.item_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["item_positions"], 1):
            self.item_tree.insert("", "end", values=(idx, f"({x},{y})"))
        self.current_item_var.set(f"0/{len(self.bot.config['item_positions'])}")

    def _del_item(self):
        sel = self.item_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要删除的物品")
            return
        idx = int(self.item_tree.item(sel[0])["values"][0]) - 1
        del self.bot.config["item_positions"][idx]
        self._update_item_tree()

    def _clear_item(self):
        if messagebox.askyesno("确认", "确定清空所有物品？"):
            self.bot.config["item_positions"].clear()
            self._update_item_tree()

    # ── 词缀 ──
    def _update_affix(self):
        self.affix_list.delete(0, tk.END)
        for a in self.target_affixes:
            self.affix_list.insert(tk.END, a)

    def _add_affix(self):
        a = self.affix_input_var.get().strip()
        if not a:
            messagebox.showwarning("警告", "词缀不能为空！")
            return
        if a in self.target_affixes:
            messagebox.showinfo("提示", "词缀已存在！")
            return
        self.target_affixes.append(a)
        self._update_affix()
        self.affix_input_var.set("")

    def _del_affix(self):
        sel = self.affix_list.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选中词缀")
            return
        for i in reversed(sel):
            del self.target_affixes[i]
        self._update_affix()

    def _clear_affixes(self):
        if messagebox.askyesno("确认", "确定清空所有词缀？"):
            self.target_affixes.clear()
            self._update_affix()

    # ── 配置 ──
    def _save(self):
        self.bot.config["target_affixes"] = self.target_affixes.copy()
        try:
            interval = float(self.interval_var.get())
            if interval < 0:
                raise ValueError
            self.bot.config["interval"] = interval
        except ValueError:
            pass  # 非法的间隔值只在启动时校验，保存时忽略
        self.bot.save_config()
        messagebox.showinfo("成功", "配置保存成功！")
        self.status_var.set("配置已保存")

    def _load(self):
        p = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON文件", "*.json")])
        if not p:
            return
        tmp = PoeOrbBotBase()
        tmp.config_file = p
        tmp.load_config()
        self.bot.config.update(tmp.config)
        self._update_item_tree()
        self._update_alter_tree()
        self._update_augment_tree()
        self.target_affixes = self.bot.config["target_affixes"].copy()
        self._update_affix()
        self.interval_var.set(str(self.bot.config.get("interval", 0.02)))
        for k in self.orb_names:
            if k not in ("alter", "augment"):
                pos = self.bot.config.get(f"{k}_pos")
                self.orb_coord_vars[k].set(f"({pos[0]},{pos[1]})" if pos else "未设置")
        messagebox.showinfo("成功", "配置加载成功！")
        self.status_var.set("配置已加载")

    # ── 运行控制 ──
    def toggle_run(self):
        if self.bot.running:
            self.bot.running = False
            self.status_var.set("已停止")
        else:
            self.start()

    def start(self):
        try:
            interval = float(self.interval_var.get())
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("警告", "操作间隔必须是大于等于 0 的数字！")
            return
        if not self.bot.config["item_positions"]:
            messagebox.showwarning("警告", "请至少添加一个物品坐标！")
            return
        if not self.target_affixes:
            messagebox.showwarning("警告", "请至少添加一个目标词缀！")
            return
        self.bot.config["target_affixes"] = self.target_affixes.copy()
        self.bot.config["interval"] = interval
        self.bot.running = True
        self.bot.start_time = time.time()
        self._start_time_thread()
        threading.Thread(target=self._run_loop, daemon=True).start()
        self.status_var.set("运行中...")

    def _run_loop(self):
        total = len(self.bot.config["item_positions"])
        for i, pos in enumerate(self.bot.config["item_positions"], 1):
            if not self.bot.running:
                break
            self.current_item_var.set(f"{i}/{total}")
            self.status_var.set(f"正在处理第 {i}/{total} 件")
            success = self.bot.process_one_item(pos)
            if success:
                self.bot.beep()
                self.status_var.set(f"物品 {i} 达标！切换下一个")
        self.bot.running = False
        self.status_var.set("已完成（所有物品处理完成或手动停止）")
        self.bot.beep(1500, 800)

    def _start_time_thread(self):
        if self.time_thread and self.time_thread.is_alive():
            return
        def upd():
            while self.bot.running:
                for k, v in self.orb_count_vars.items():
                    v.set(str(getattr(self.bot, f"{k}_count", 0)))
                used = int(time.time() - self.bot.start_time)
                self.time_var.set(f"{used//3600:02d}:{used%3600//60:02d}:{used%60:02d}")
                time.sleep(0.2)
        self.time_thread = threading.Thread(target=upd, daemon=True)
        self.time_thread.start()

    def on_tab_deselect(self):
        """切换 Tab 时停止当前 bot"""
        if self.bot.running:
            self.bot.running = False
            self.status_var.set("切换模式，已停止")


# ──────────────────────────────────────────────
# 主 GUI（Notebook 两个 Tab）
# ──────────────────────────────────────────────
ORB_NAMES_SIMPLE = {
    "transmutation": "蜕变石",
    "alter": "改造石",
    "augment": "增幅石",
}

ORB_NAMES_FULL = {
    "transmutation": "蜕变石",
    "alter": "改造石",
    "augment": "增幅石",
    "regal": "富豪石",
    "extend": "崇高石",
    "scouring": "重铸石",
    "annulment": "剥离石",
}


class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("POE 宝珠制作机器人")
        self.root.geometry("570x760")
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.bot_simple = PoeOrbBotSimple()
        self.bot_full = PoeOrbBotFull()

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tab_simple = BotTabPanel(nb, self.bot_simple, "简化版（蜕变→增幅/改造）", ORB_NAMES_SIMPLE)
        self.tab_full = BotTabPanel(nb, self.bot_full, "完整版（7种宝珠）", ORB_NAMES_FULL)

        self._active_tab = self.tab_simple
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_change(nb))

        # F3 绑定当前激活 tab
        keyboard.add_hotkey('f3', self._toggle_active)

        # = 绑定当前激活 tab
        # 用全局钩子（与 F3 一致）：tkinter 的 <equal> 只在窗口有焦点时生效，
        # 部分用户鼠标移到游戏窗口后 tkinter 失焦，导致 = 监听不到
        keyboard.add_hotkey('=', lambda: self._active_tab.get_coord(self._active_tab.coord_type.get()))

        self.root.after(100, self._periodic_update)

    def _on_tab_change(self, nb):
        idx = nb.index(nb.select())
        # 停止另一个 tab 的 bot
        other = self.tab_full if idx == 0 else self.tab_simple
        other.on_tab_deselect()
        self._active_tab = self.tab_simple if idx == 0 else self.tab_full

    def _toggle_active(self):
        self._active_tab.toggle_run()

    def _periodic_update(self):
        self.root.after(100, self._periodic_update)

    def _on_closing(self):
        self.bot_simple.running = False
        self.bot_full.running = False
        try:
            self.tab_simple.bot.config["target_affixes"] = self.tab_simple.target_affixes.copy()
            self.tab_simple.bot.save_config()
        except:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    MainApp().run()
