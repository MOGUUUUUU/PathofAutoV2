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
from tkinter import Listbox, Scrollbar, Frame, Label, Button

pyautogui.PAUSE = 0.035

class PoeOrbBot:
    def __init__(self):
        self.running = False
        self.transmutation_count = 0
        self.alter_count = 0
        self.augment_count = 0
        self.regal_count = 0
        self.extend_count = 0
        self.scouring_count = 0
        self.annulment_count = 0
        self.start_time = 0
        self.config = {
            "alter_positions": [],
            "augment_positions": [],
            "regal_pos": None,
            "extend_pos": None,
            "scouring_pos": None,
            "transmutation_pos": None,
            "annulment_pos": None,
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
                    if "item_positions" in loaded:
                        loaded["item_positions"] = [list(pos) if isinstance(pos, (list, tuple)) else pos
                                                  for pos in loaded["item_positions"]]
                    if "alter_positions" not in loaded:
                        loaded["alter_positions"] = []
                    if "augment_positions" not in loaded:
                        loaded["augment_positions"] = []
                    if "target_affixes" not in loaded:
                        loaded["target_affixes"] = []
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
    
    def get_mouse_pos(self):
        return pyautogui.position()
    
    def beep(self, freq=1000, dur=500):
        try:
            winsound.Beep(freq, dur)
        except:
            winsound.MessageBeep()
    
    def get_item_info(self):
        for _ in range(3):
            pyautogui.hotkey('ctrl', 'alt', 'c')
            self.rand_sleep(0.001, 0.001)
        return pyperclip.paste()
    
    def has_target_affix(self, text , need_count):
        if not text or not self.config["target_affixes"]:
            return False
        match_count = 0
        for target in self.config["target_affixes"]:
            if target in text:
                match_count += 1
        return match_count >= need_count
    
    def check_item(self, item_pos, need_count):
        pyautogui.moveTo(item_pos)
        self.rand_sleep()
        info = self.get_item_info()
        return self.has_target_affix(info, need_count)
    
    def use_orb(self, orb_name: str, item_pos=None):
        if orb_name == "alter":
            orb_positions = self.config.get("alter_positions")
        elif orb_name == "augment":
            orb_positions = self.config.get("augment_positions")
        else:
            orb_pos = self.config.get(f"{orb_name}_pos")
            if not orb_pos:
                raise RuntimeError
            orb_positions = [orb_pos]
        if not orb_positions:
            raise RuntimeError
        selected_pos = random.choice(orb_positions)
        pyautogui.moveTo(selected_pos)
        self.rand_sleep()
        pyautogui.click(button='right')
        self.rand_sleep()
        if item_pos:
            pyautogui.moveTo(item_pos)
            self.rand_sleep()
            pyautogui.click(button='left')
            self.rand_sleep()
        count_attr = f"{orb_name}_count"
        if hasattr(self, count_attr):
            setattr(self, count_attr, getattr(self, count_attr) + 1)
        return True
    
    def process_one_item(self, item_pos) -> bool:
        if not self.running:
            return False
        STATE_START = "start"
        STATE_TRANSMUTATION = "transmutation"
        STATE_ALTER = "alter"
        STATE_AUGMENT = "augment"
        STATE_REGAL = "regal"
        STATE_EXTEND = "extend"
        STATE_ANNUL = "annul"
        STATE_SCOUR = "scour"
        STATE_SUCCESS = "success"
        state = STATE_START
        TARGET_AFTER_ALTER = 1
        TARGET_AFTER_AUGMENT = 2
        TARGET_AFTER_REGAL = 3
        TARGET_AFTER_EXTEND = 4
        while self.running:
            if state == STATE_START:
                state = STATE_TRANSMUTATION
            elif state == STATE_TRANSMUTATION:
                self.use_orb("transmutation", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_ALTER):
                    state = STATE_AUGMENT
                else:
                    state = STATE_ALTER
            elif state == STATE_ALTER:
                self.use_orb("alter", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_ALTER):
                    state = STATE_AUGMENT
                else:
                    state = STATE_ALTER
            elif state == STATE_AUGMENT:
                if self.config.get("use_augment", True):
                    self.use_orb("augment", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_AUGMENT):
                    state = STATE_REGAL
                else:
                    state = STATE_ALTER
            elif state == STATE_REGAL:
                if self.config.get("use_regal", True):
                    self.use_orb("regal", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_REGAL):
                    state = STATE_EXTEND
                else:
                    state = STATE_SCOUR
            elif state == STATE_EXTEND:
                if self.config.get("use_extend", True):
                    self.use_orb("extend", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_EXTEND):
                    state = STATE_SUCCESS
                else:
                    state = STATE_ANNUL
            elif state == STATE_ANNUL:
                if self.config.get("use_annulment", True):
                    self.use_orb("annulment", item_pos)
                if self.check_item(item_pos, need_count=TARGET_AFTER_REGAL):
                    state = STATE_EXTEND
                else:
                    state = STATE_SCOUR
            elif state == STATE_SCOUR:
                if self.config.get("use_scouring", True):
                    self.use_orb("scouring", item_pos)
                state = STATE_TRANSMUTATION
            elif state == STATE_SUCCESS:
                return True
            time.sleep(0.001)
        return False

class PoeOrbBotGUI:
    ORB_NAMES = {
        "transmutation": "蜕变石",
        "alter": "改造石",
        "augment": "增幅石",
        "regal": "富豪石",
        "extend": "崇高石",
        "scouring": "重铸石",
        "annulment": "剥离石"
    }
    
    def __init__(self, bot: PoeOrbBot):
        self.bot = bot
        self.root = tk.Tk()
        self.root.title("POEorbBot")
        self.root.geometry("550x880")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.attributes('-topmost', True)
        
        keyboard.add_hotkey('f3', self.toggle_run)
        
        self.coord_type = tk.StringVar(value="transmutation")
        self.current_item_var = tk.StringVar(value="0/0")
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="状态：未运行")
        
        self.affix_input_var = tk.StringVar()
        self.target_affixes = self.bot.config["target_affixes"].copy()
        
        self.orb_coord_vars = {}
        self.orb_count_vars = {}
        self.alter_tree = None
        self.augment_tree = None
        self._init_vars()
        
        self.create_widgets()
        self.bind_shortcuts()
        self.time_thread = None
        self.update_all()
    
    def _init_vars(self):
        for orb_key in self.ORB_NAMES.keys():
            if orb_key not in ["alter", "augment"]:
                coord_var = tk.StringVar()
                pos = self.bot.config.get(f"{orb_key}_pos")
                coord_var.set(f"({pos[0]}, {pos[1]})" if pos else "未设置")
                self.orb_coord_vars[orb_key] = coord_var
            
            count_var = tk.StringVar()
            count = getattr(self.bot, f"{orb_key}_count")
            count_var.set(f"{count}")
            self.orb_count_vars[orb_key] = count_var
    
    def create_widgets(self):
        # 1. 坐标设置区域
        coord_frame = ttk.LabelFrame(self.root, text="坐标设置（快捷键：=）")
        coord_frame.pack(padx=3, pady=2, fill=tk.BOTH, expand=True)
        
        row = 0
        for idx, (orb_key, orb_name) in enumerate(self.ORB_NAMES.items()):
            if orb_key in ["alter", "augment"]:
                ttk.Radiobutton(coord_frame, text=orb_name, variable=self.coord_type, value=orb_key).grid(
                    row=row, column=0, padx=2, pady=2, sticky=tk.W)
                tree = ttk.Treeview(coord_frame, columns=("index", "coord"), show="headings", height=2)
                tree.heading("index", text="序号")
                tree.heading("coord", text="坐标")
                tree.column("index", width=50, anchor=tk.CENTER)
                tree.column("coord", width=100, anchor=tk.CENTER)
                tree.grid(row=row, column=1, columnspan=2, padx=2, pady=2, sticky=tk.NSEW)
                if orb_key == "alter":
                    self.alter_tree = tree
                    self.update_alter_tree()
                else:
                    self.augment_tree = tree
                    self.update_augment_tree()
                del_btn = ttk.Button(coord_frame, text="删除", command=lambda k=orb_key: self.delete_orb_pos(k), width=8)
                del_btn.grid(row=row, column=3, padx=2, pady=2)
                row += 1
            else:
                ttk.Radiobutton(coord_frame, text=orb_name, variable=self.coord_type, value=orb_key).grid(
                    row=row, column=0, padx=2, pady=2, sticky=tk.W)
                ttk.Entry(coord_frame, textvariable=self.orb_coord_vars[orb_key], state="readonly", width=14).grid(
                    row=row, column=1, padx=2, pady=2)
                row += 1
        
        ttk.Radiobutton(coord_frame, text="添加物品坐标", variable=self.coord_type, value='item').grid(
                row=row, column=0, columnspan=5, padx=2, pady=2, sticky=tk.W)
        
        ttk.Label(coord_frame, text="提示：鼠标移到目标位置后按 = 键获取（支持刷新）", foreground="gray", font=('', 8)).grid(
            row=row+1, column=0, columnspan=5, padx=2, pady=1, sticky=tk.W)
        
        # 2. 批量物品设置
        item_frame = ttk.LabelFrame(self.root, text="批量物品设置")
        item_frame.pack(padx=3, pady=2, fill=tk.BOTH, expand=True)
        
        ttk.Label(item_frame, text="物品列表（顺序处理）：").grid(row=0, column=0, padx=2, pady=1, sticky=tk.W)
        self.item_tree = ttk.Treeview(item_frame, columns=("index", "coord"), show="headings", height=3)
        self.item_tree.heading("index", text="序号")
        self.item_tree.heading("coord", text="坐标")
        self.item_tree.column("index", width=50, anchor=tk.CENTER)
        self.item_tree.column("coord", width=100, anchor=tk.CENTER)
        self.item_tree.grid(row=1, column=0, columnspan=3, padx=2, pady=2, sticky=tk.NSEW)
        
        scrollbar = ttk.Scrollbar(item_frame, orient=tk.VERTICAL, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=3, sticky=tk.NS, pady=2)
        
        btn_frame = ttk.Frame(item_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, padx=2, pady=2)
        ttk.Button(btn_frame, text="添加物品（=）", command=lambda: self.get_coord("item")).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="删除选中", command=self.delete_itemment).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_itemment).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # 3. 目标词缀设置
        affix_frame = ttk.LabelFrame(self.root, text="目标词缀管理")
        affix_frame.pack(padx=3, pady=2, fill=tk.X)
        
        ttk.Label(affix_frame, text="添加词缀：").grid(row=0, column=0, padx=2, pady=1, sticky=tk.W)
        ttk.Entry(affix_frame, textvariable=self.affix_input_var, width=23).grid(row=0, column=1, padx=2, pady=1)
        ttk.Button(affix_frame, text="添加", command=self.add_affix, width=8).grid(row=0, column=2, padx=2, pady=1)
        
        ttk.Label(affix_frame, text="已添加：").grid(row=1, column=0, padx=2, pady=1, sticky=tk.W)
        self.affix_listbox = Listbox(affix_frame, width=30, height=3)
        self.affix_listbox.grid(row=2, column=0, columnspan=2, padx=2, pady=1, sticky=tk.NSEW)
        
        affix_scrollbar = ttk.Scrollbar(affix_frame, orient=tk.VERTICAL, command=self.affix_listbox.yview)
        self.affix_listbox.configure(yscrollcommand=affix_scrollbar.set)
        affix_scrollbar.grid(row=2, column=2, sticky=tk.NS, pady=1)
        
        affix_btn_frame = ttk.Frame(affix_frame)
        affix_btn_frame.grid(row=3, column=0, columnspan=3, padx=2, pady=1)
        ttk.Button(affix_btn_frame, text="删除选中", command=self.delete_affix).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(affix_btn_frame, text="清空列表", command=self.clear_affixes).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # 4. 控制按钮
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(padx=3, pady=2, fill=tk.X)
        ttk.Label(ctrl_frame, text="F3 开始/停止").grid(row=0, column=0, columnspan=2, padx=2, pady=1, sticky=tk.W)
        # self.start_btn = ttk.Button(ctrl_frame, text="开始", command=self.start_tool)
        # self.start_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        # self.stop_btn = ttk.Button(ctrl_frame, text="停止", command=self.stop_tool, state="disabled")
        # self.stop_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # 5. 统计信息
        stat_frame = ttk.LabelFrame(self.root, text="统计信息")
        stat_frame.pack(padx=3, pady=2, fill=tk.X)
        
        for idx, (orb_key, orb_name) in enumerate(self.ORB_NAMES.items()):
            row = idx // 4
            col = idx % 4 * 2
            ttk.Label(stat_frame, text=f"{orb_name}：", font=('', 8)).grid(row=row, column=col, padx=1, pady=1, sticky=tk.W)
            ttk.Entry(stat_frame, textvariable=self.orb_count_vars[orb_key], state="readonly", width=8).grid(
                row=row, column=col+1, padx=1, pady=1)
        
        ttk.Label(stat_frame, text="当前物品：", font=('', 8)).grid(row=3, column=0, padx=1, pady=1, sticky=tk.W)
        ttk.Entry(stat_frame, textvariable=self.current_item_var, state="readonly", width=8).grid(
            row=3, column=1, padx=1, pady=1)
        ttk.Label(stat_frame, text="运行时间：", font=('', 8)).grid(row=3, column=2, padx=1, pady=1, sticky=tk.W)
        ttk.Entry(stat_frame, textvariable=self.time_var, state="readonly", width=8).grid(
            row=3, column=3, padx=1, pady=1)
        
        # 6. 状态提示
        status_label = ttk.Label(self.root, textvariable=self.status_var, foreground="blue", font=('', 9))
        status_label.pack(padx=3, pady=2)
        
        # 7. 配置保存/加载
        config_frame = ttk.Frame(self.root)
        config_frame.pack(padx=3, pady=2, fill=tk.X)
        ttk.Button(config_frame, text="保存配置", command=self.save_config, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_frame, text="加载配置", command=self.load_config, width=12).pack(side=tk.LEFT, padx=2)
        
        # 布局权重
        item_frame.grid_rowconfigure(1, weight=1)
        item_frame.grid_columnconfigure(0, weight=1)
        affix_frame.grid_rowconfigure(2, weight=1)
        affix_frame.grid_columnconfigure(1, weight=1)
        coord_frame.grid_columnconfigure(1, weight=1)
        
        self.update_item_tree()
        self.update_affix_listbox()
    
    def bind_shortcuts(self):
        self.root.bind('<equal>', lambda e: self.get_coord(self.coord_type.get()))
        self.root.bind('<backslash>', lambda e: self.stop_tool() if self.bot.running else None)
    
    def get_coord(self, target_type):
        try:
            x, y = pyautogui.position()
            if target_type == "item":
                self.bot.config["item_positions"].append((x, y))
                self.update_item_tree()
                self.status_var.set(f"已添加物品坐标 ({x}, {y}) 共{len(self.bot.config['item_positions'])}个")
            elif target_type == "alter":
                self.bot.config["alter_positions"].append((x, y))
                self.update_alter_tree()
                self.status_var.set(f"已添加改造石坐标 ({x}, {y}) 共{len(self.bot.config['alter_positions'])}个")
            elif target_type == "augment":
                self.bot.config["augment_positions"].append((x, y))
                self.update_augment_tree()
                self.status_var.set(f"已添加增幅石坐标 ({x}, {y}) 共{len(self.bot.config['augment_positions'])}个")
            elif target_type in self.ORB_NAMES.keys():
                self.bot.config[f"{target_type}_pos"] = (x, y)
                self.orb_coord_vars[target_type].set(f"({x}, {y})")
                orb_name = self.ORB_NAMES[target_type]
                self.status_var.set(f"已获取{orb_name}坐标 ({x}, {y})")
            else:
                self.status_var.set("状态：未知类型")
        except Exception as e:
            print(f"获取坐标失败: {e}")
            self.status_var.set("获取坐标失败，请重试")
    
    def update_alter_tree(self):
        for item in self.alter_tree.get_children():
            self.alter_tree.delete(item)
        for idx, (x, y) in enumerate(self.bot.config["alter_positions"], 1):
            self.alter_tree.insert("", tk.END, values=(idx, f"({x}, {y})"))
    
    def update_augment_tree(self):
        for item in self.augment_tree.get_children():
            self.augment_tree.delete(item)
        for idx, (x, y) in enumerate(self.bot.config["augment_positions"], 1):
            self.augment_tree.insert("", tk.END, values=(idx, f"({x}, {y})"))
    
    def delete_orb_pos(self, orb_key):
        if orb_key == "alter":
            tree = self.alter_tree
            positions = self.bot.config["alter_positions"]
        elif orb_key == "augment":
            tree = self.augment_tree
            positions = self.bot.config["augment_positions"]
        else:
            return
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中要删除的坐标")
            return
        item = tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        del positions[idx]
        if orb_key == "alter":
            self.update_alter_tree()
        else:
            self.update_augment_tree()
        self.status_var.set(f"已删除选中{self.ORB_NAMES[orb_key]}坐标（当前共{len(positions)}个）")
    
    def update_item_tree(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        for idx, (x, y) in enumerate(self.bot.config["item_positions"], 1):
            self.item_tree.insert("", tk.END, values=(idx, f"({x}, {y})"))
        total = len(self.bot.config["item_positions"])
        self.current_item_var.set(f"0/{total}")
    
    def delete_itemment(self):
        selected = self.item_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中要删除的物品")
            return
        item = self.item_tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        del self.bot.config["item_positions"][idx]
        self.update_item_tree()
        self.status_var.set(f"已删除选中物品（当前共{len(self.bot.config['item_positions'])}个）")
    
    def clear_itemment(self):
        if messagebox.askyesno("确认", "确定要清空所有物品吗？"):
            self.bot.config["item_positions"].clear()
            self.update_item_tree()
            self.status_var.set("已清空物品列表")
    
    def update_affix_listbox(self):
        self.affix_listbox.delete(0, tk.END)
        for affix in self.target_affixes:
            self.affix_listbox.insert(tk.END, affix)
    
    def add_affix(self):
        affix_text = self.affix_input_var.get().strip()
        if not affix_text:
            messagebox.showwarning("警告", "词缀不能为空！")
            return
        if affix_text in self.target_affixes:
            messagebox.showinfo("提示", "该词缀已存在！")
            return
        self.target_affixes.append(affix_text)
        self.update_affix_listbox()
        self.affix_input_var.set("")
        self.status_var.set(f"已添加词缀「{affix_text}」（当前共{len(self.target_affixes)}个）")
    
    def delete_affix(self):
        selected_indices = self.affix_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选中要删除的词缀")
            return
        for idx in reversed(selected_indices):
            deleted_affix = self.target_affixes.pop(idx)
        self.update_affix_listbox()
        self.status_var.set(f"已删除选中词缀（当前共{len(self.target_affixes)}个）")
    
    def clear_affixes(self):
        if not self.target_affixes:
            messagebox.showinfo("提示", "词缀列表已为空！")
            return
        if messagebox.askyesno("确认", "确定要清空所有目标词缀吗？"):
            self.target_affixes.clear()
            self.update_affix_listbox()
            self.status_var.set("已清空词缀列表")
    
    def save_config(self):
        try:
            self.bot.config["target_affixes"] = self.target_affixes.copy()
            self.bot.save_config()
            messagebox.showinfo("成功", "配置保存成功！")
            self.status_var.set("配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败：{str(e)}")
    
    def load_config(self):
        path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON文件", "*.json")])
        if not path:
            return
        try:
            temp_bot = PoeOrbBot()
            temp_bot.config_file = path
            temp_bot.load_config()
            self.bot.config.update(temp_bot.config)
            
            for orb_key in self.ORB_NAMES.keys():
                if orb_key in ["alter", "augment"]:
                    if orb_key == "alter":
                        self.update_alter_tree()
                    else:
                        self.update_augment_tree()
                else:
                    pos = self.bot.config.get(f"{orb_key}_pos")
                    self.orb_coord_vars[orb_key].set(f"({pos[0]}, {pos[1]})" if pos else "未设置")
            
            self.update_item_tree()
            self.target_affixes = self.bot.config["target_affixes"].copy()
            self.update_affix_listbox()
            
            messagebox.showinfo("成功", "配置加载成功！")
            self.status_var.set("配置已加载")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败：{str(e)}")
    
    def start_tool(self):
        if not self.bot.config["item_positions"]:
            messagebox.showwarning("警告", "请至少添加一个物品坐标！")
            return
        
        if not self.target_affixes:
            messagebox.showwarning("警告", "请至少添加一个目标词缀！")
            return
        
        self.bot.config["target_affixes"] = self.target_affixes.copy()
        self.bot.running = True
        self.bot.start_time = time.time()
        
        # self.start_btn.config(state="disabled")
        # self.stop_btn.config(state="normal")
        
        self.start_time_thread()
        threading.Thread(target=self.run_bot, daemon=True).start()
        
    def toggle_run(self):
        if self.bot.running:
            self.stop_tool()
        else:
            self.start_tool()
    
    def run_bot(self):
        total_item = len(self.bot.config["item_positions"])
        
        for idx, item_pos in enumerate(self.bot.config["item_positions"], 1):
            if not self.bot.running:
                break
            self.current_item_var.set(f"{idx}/{total_item}")
            self.status_var.set(f"运行中（处理物品 {idx}/{total_item}）")
            success = self.bot.process_one_item(item_pos)
            if success:
                self.bot.beep()
                self.status_var.set(f"物品 {idx} 达标！切换下一个")
        
        self.bot.running = False
        self.status_var.set("已停止（所有物品处理完成或手动停止）")
        self.bot.beep(1500, 800)
        self.root.after(0, lambda: self.start_btn.config(state="normal"))
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
    
    def stop_tool(self):
        self.bot.running = False
        self.status_var.set("停止中...")
    
    def start_time_thread(self):
        if self.time_thread and self.time_thread.is_alive():
            return
        def update_time():
            while self.bot.running:
                for orb_key, orb_count_var in self.orb_count_vars.items():
                    count = getattr(self.bot, f"{orb_key}_count")
                    orb_count_var.set(f"{count}")
                
                elapsed = int(time.time() - self.bot.start_time)
                hours = elapsed // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                self.time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                time.sleep(0.1)
        self.time_thread = threading.Thread(target=update_time, daemon=True)
        self.time_thread.start()
    
    def update_all(self):
        self.root.after(100, self.update_all)
    
    def on_closing(self):
        self.bot.running = False
        try:
            self.bot.config["target_affixes"] = self.target_affixes.copy()
            self.bot.save_config()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    bot = PoeOrbBot()
    gui = PoeOrbBotGUI(bot)
    gui.root.mainloop()