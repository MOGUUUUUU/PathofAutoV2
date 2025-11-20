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


class PoeOrbBot:
    def __init__(self):
        self.running = False
        self.paused = False
        self.transmutation_count = 0
        self.alter_count = 0
        self.augment_count = 0
        self.regal_count = 0
        self.extend_count = 0
        self.scouring_count = 0
        self.annulment_count = 0
        self.start_time = 0

        self.config = {
            "alter_pos": None,
            "augment_pos": None,
            "regal_pos": None,
            "extend_pos": None,
            "scouring_pos": None,
            "transmutation_pos": None,
            "annulment_pos": None,
            "item_positions": [], 
            "target_affixes": [], 
            "interval": None,
        }
        

        self.config_file = "poe_orb_config.json"
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # 确保 item_positions 是列表格式
                    if "item_positions" in loaded:
                        loaded["item_positions"] = [list(pos) if isinstance(pos, (list, tuple)) else pos 
                                                  for pos in loaded["item_positions"]]
                    if "target_affixes" not in loaded:
                        loaded["target_affixes"] = []
                    self.config.update(loaded)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self, path=None):
        path = path or self.config_file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def rand_sleep(self, base=None, rand_range=0.01):
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
            self.rand_sleep(0.01, 0.01)
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
        orb_pos = self.config.get(f"{orb_name}_pos")
        if not orb_pos:
            raise RuntimeError
        pyautogui.moveTo(orb_pos)
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
            if self.paused:
                time.sleep(0.1)
                continue

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


# ========== GUI 界面（按需求修改） ==========
class PoeOrbBotGUI:
    # 所有通货平等显示，无特殊强调
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
        self.root.geometry("800x950")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 状态变量
        self.coord_type = tk.StringVar(value="transmutation")
        self.current_item_var = tk.StringVar(value="0/0")
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="状态：未运行")
        
        # 词缀相关变量
        self.affix_input_var = tk.StringVar()
        self.target_affixes = self.bot.config["target_affixes"].copy()
        
        # orb 相关变量
        self.orb_coord_vars = {}
        self.orb_count_vars = {}
        self._init_vars()
        
        # 创建界面组件
        self.create_widgets()
        # 绑定快捷键
        self.bind_shortcuts()
        # 启动时间统计线程
        self.time_thread = None
        self.update_all()

    def _init_vars(self):
        """初始化所有通货坐标显示变量"""
        for orb_key in self.ORB_NAMES.keys():
            coord_var = tk.StringVar()
            pos = self.bot.config.get(f"{orb_key}_pos")
            coord_var.set(f"({pos[0]}, {pos[1]})" if pos else "未设置")
            self.orb_coord_vars[orb_key] = coord_var
            
            count_var = tk.StringVar()
            count = getattr(self.bot, f"{orb_key}_count")
            count_var.set(f"{count}")
            self.orb_count_vars[orb_key] = count_var

    def create_widgets(self):
        # 1. 坐标设置总区域（合并坐标选择和坐标显示）
        coord_frame = ttk.LabelFrame(self.root, text="坐标设置（快捷键：=）")
        coord_frame.pack(padx=10, pady=5, fill=tk.X)

        # 单选按钮：
        for idx, (orb_key, orb_name) in enumerate(self.ORB_NAMES.items()):
            row = idx // 4
            col = idx % 4 * 2
            ttk.Radiobutton(coord_frame, text=orb_name, variable=self.coord_type, value=orb_key).grid(
                row=row, column=col, padx=5, pady=5, sticky=tk.W)
            ttk.Entry(coord_frame, textvariable=self.orb_coord_vars[orb_key], state="readonly", width=12).grid(
                row=row, column=col+1, padx=5, pady=5)
        ttk.Radiobutton(coord_frame, text="添加物品坐标", variable=self.coord_type, value='item').grid(
                row=row+1, column=0, columnspan=5, padx=5, pady=5, sticky=tk.W)
        
        # 提示信息
        ttk.Label(coord_frame, text="操作提示：鼠标移到目标位置后按 = 键，一键获取坐标（支持刷新）", foreground="gray").grid(
            row=row+2, column=0, columnspan=5, padx=5, pady=5, sticky=tk.W)

        # 2. 批量物品设置
        item_frame = ttk.LabelFrame(self.root, text="批量物品设置")
        item_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        ttk.Label(item_frame, text="物品列表（顺序处理）：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.item_tree = ttk.Treeview(item_frame, columns=("index", "coord"), show="headings", height=6)
        self.item_tree.heading("index", text="序号")
        self.item_tree.heading("coord", text="坐标")
        self.item_tree.column("index", width=60, anchor=tk.CENTER)
        self.item_tree.column("coord", width=150, anchor=tk.CENTER)
        self.item_tree.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)

        # 滚动条
        scrollbar = ttk.Scrollbar(item_frame, orient=tk.VERTICAL, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=3, sticky=tk.NS, pady=5)

        # 物品操作按钮
        btn_frame = ttk.Frame(item_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5)

        ttk.Button(btn_frame, text="一键添加物品（=）", command=lambda: self.get_coord("item")).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="删除选中物品", command=self.delete_itemment).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="清空物品列表", command=self.clear_itemment).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 3. 目标词缀设置（列表管理）
        affix_frame = ttk.LabelFrame(self.root, text="目标词缀管理")
        affix_frame.pack(padx=10, pady=5, fill=tk.X)

        # 词缀输入区
        ttk.Label(affix_frame, text="添加词缀：").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(affix_frame, textvariable=self.affix_input_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(affix_frame, text="添加", command=self.add_affix).grid(row=0, column=2, padx=5, pady=5)

        # 词缀列表区
        ttk.Label(affix_frame, text="已添加词缀：").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.affix_listbox = Listbox(affix_frame, width=40, height=6)
        self.affix_listbox.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.NSEW)
        
        # 词缀列表滚动条
        affix_scrollbar = ttk.Scrollbar(affix_frame, orient=tk.VERTICAL, command=self.affix_listbox.yview)
        self.affix_listbox.configure(yscrollcommand=affix_scrollbar.set)
        affix_scrollbar.grid(row=2, column=2, sticky=tk.NS, pady=5)

        # 词缀操作按钮
        affix_btn_frame = ttk.Frame(affix_frame)
        affix_btn_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5)
        ttk.Button(affix_btn_frame, text="删除选中词缀", command=self.delete_affix).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(affix_btn_frame, text="清空词缀列表", command=self.clear_affixes).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 5. 控制按钮
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(padx=10, pady=10, fill=tk.X)

        self.start_btn = ttk.Button(ctrl_frame, text="开始", command=self.start_tool)
        self.start_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.pause_btn = ttk.Button(ctrl_frame, text="暂停", command=self.pause_tool, state="disabled")
        self.pause_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.stop_btn = ttk.Button(ctrl_frame, text="停止", command=self.stop_tool, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 6. 统计信息
        stat_frame = ttk.LabelFrame(self.root, text="统计信息")
        stat_frame.pack(padx=10, pady=5, fill=tk.X)

        for idx, (orb_key, orb_name) in enumerate(self.ORB_NAMES.items()):
            row = idx // 4
            col = idx % 4 * 2
            ttk.Label(stat_frame, text=f"{orb_name}：").grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
            ttk.Entry(stat_frame, textvariable=self.orb_count_vars[orb_key], state="readonly", width=12).grid(
                row=row, column=col+1, padx=5, pady=5)

        ttk.Label(stat_frame, text="当前物品：").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(stat_frame, textvariable=self.current_item_var, state="readonly", width=10).grid(
            row=3, column=1, padx=5, pady=5)

        ttk.Label(stat_frame, text="运行时间：").grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(stat_frame, textvariable=self.time_var, state="readonly", width=12).grid(
            row=3, column=3, padx=5, pady=5)

        # 7. 状态提示
        status_label = ttk.Label(self.root, textvariable=self.status_var, foreground="blue")
        status_label.pack(padx=10, pady=5)

        # 8. 配置保存/加载
        config_frame = ttk.Frame(self.root)
        config_frame.pack(padx=10, pady=5, fill=tk.X)
        ttk.Button(config_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_frame, text="加载配置", command=self.load_config).pack(side=tk.LEFT, padx=5)


        # 布局权重设置
        item_frame.grid_rowconfigure(1, weight=1)
        item_frame.grid_columnconfigure(0, weight=1)
        affix_frame.grid_rowconfigure(2, weight=1)
        affix_frame.grid_columnconfigure(1, weight=1)
        coord_frame.grid_columnconfigure(0, weight=1)
        coord_frame.grid_columnconfigure(1, weight=1)
        coord_frame.grid_columnconfigure(2, weight=1)

        # 初始化列表
        self.update_item_tree()
        self.update_affix_listbox()

    def bind_shortcuts(self):
        """绑定所有快捷键"""
        # 获取坐标（= 键）- 支持所有通货和物品
        self.root.bind('<equal>', lambda e: self.get_coord(self.coord_type.get()))
        # 暂停（[ 键）
        self.root.bind('<bracketleft>', lambda e: self.pause_tool() if self.bot.running else None)
        # 继续（] 键）
        self.root.bind('<bracketright>', lambda e: self.resume_tool() if self.bot.running and self.bot.paused else None)
        # 停止（\ 键）
        self.root.bind('<backslash>', lambda e: self.stop_tool() if self.bot.running else None)

    def get_coord(self, target_type):
        """一键获取坐标（支持所有通货和物品）"""
        try:
            x, y = pyautogui.position()
            if target_type == "item":
                # 添加物品坐标到列表
                self.bot.config["item_positions"].append((x, y))
                self.update_item_tree()
                self.status_var.set(f"状态：已添加物品坐标 ({x}, {y})（当前共{len(self.bot.config['item_positions'])}个）")
            elif target_type in self.ORB_NAMES.keys():
                # 保存通货坐标
                self.bot.config[f"{target_type}_pos"] = (x, y)
                self.orb_coord_vars[target_type].set(f"({x}, {y})")
                orb_name = self.ORB_NAMES[target_type]
                self.status_var.set(f"状态：已获取{orb_name}坐标 ({x}, {y})（按 = 键可刷新）")
            else:
                self.status_var.set("状态：未知的坐标类型")
        except Exception as e:
            print(f"获取坐标失败: {e}")
            self.status_var.set("状态：获取坐标失败，请重试")

    def update_item_tree(self):
        """更新物品列表树"""
        # 清空现有内容
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        # 添加新内容
        for idx, (x, y) in enumerate(self.bot.config["item_positions"], 1):
            self.item_tree.insert("", tk.END, values=(idx, f"({x}, {y})"))
        # 更新当前物品计数
        total = len(self.bot.config["item_positions"])
        self.current_item_var.set(f"0/{total}")

    def delete_itemment(self):
        """删除选中的物品"""
        selected = self.item_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中要删除的物品")
            return
        # 获取选中行的索引
        item = self.item_tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        # 删除配置中的坐标
        del self.bot.config["item_positions"][idx]
        # 更新列表
        self.update_item_tree()
        self.status_var.set(f"状态：已删除选中物品（当前共{len(self.bot.config['item_positions'])}个）")

    def clear_itemment(self):
        """清空物品列表"""
        if messagebox.askyesno("确认", "确定要清空所有物品吗？"):
            self.bot.config["item_positions"].clear()
            self.update_item_tree()
            self.status_var.set("状态：已清空物品列表")

    # 目标词缀列表管理方法
    def update_affix_listbox(self):
        """更新词缀列表框"""
        self.affix_listbox.delete(0, tk.END)
        for affix in self.target_affixes:
            self.affix_listbox.insert(tk.END, affix)

    def add_affix(self):
        """添加词缀"""
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
        self.status_var.set(f"状态：已添加词缀「{affix_text}」（当前共{len(self.target_affixes)}个）")

    def delete_affix(self):
        """删除选中词缀"""
        selected_indices = self.affix_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选中要删除的词缀")
            return
        # 倒序删除，避免索引错乱
        for idx in reversed(selected_indices):
            deleted_affix = self.target_affixes.pop(idx)
        self.update_affix_listbox()
        self.status_var.set(f"状态：已删除选中词缀（当前共{len(self.target_affixes)}个）")

    def clear_affixes(self):
        """清空词缀列表"""
        if not self.target_affixes:
            messagebox.showinfo("提示", "词缀列表已为空！")
            return
        if messagebox.askyesno("确认", "确定要清空所有目标词缀吗？"):
            self.target_affixes.clear()
            self.update_affix_listbox()
            self.status_var.set("状态：已清空词缀列表")

    def save_config(self):
        """保存配置"""
        try:
            # 更新目标词缀
            self.bot.config["target_affixes"] = self.target_affixes.copy()
            # 保存配置文件
            self.bot.save_config()
            messagebox.showinfo("成功", "配置保存成功！")
            self.status_var.set("状态：配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败：{str(e)}")

    def load_config(self):
        """加载配置"""
        path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON文件", "*.json")])
        if not path:
            return
        try:
            # 先加载到临时配置
            temp_bot = PoeOrbBot()
            temp_bot.config_file = path
            temp_bot.load_config()
            
            # 更新主配置
            self.bot.config.update(temp_bot.config)
            
            # 更新坐标显示
            for orb_key in self.ORB_NAMES.keys():
                pos = self.bot.config.get(f"{orb_key}_pos")
                self.orb_coord_vars[orb_key].set(f"({pos[0]}, {pos[1]})" if pos else "未设置")
            
            # 更新物品列表
            self.update_item_tree()
            
            # 更新目标词缀
            self.target_affixes = self.bot.config["target_affixes"].copy()
            self.update_affix_listbox()
            
            
            messagebox.showinfo("成功", "配置加载成功！")
            self.status_var.set("状态：配置已加载")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败：{str(e)}")

    def start_tool(self):
        """启动工具"""
        
        if not self.bot.config["item_positions"]:
            messagebox.showwarning("警告", "请至少添加一个物品坐标！")
            return
        
        if not self.target_affixes:
            messagebox.showwarning("警告", "请至少添加一个目标词缀！")
            return
        
        # 更新配置
        self.bot.config["target_affixes"] = self.target_affixes.copy()

        # 重置状态
        self.bot.running = True
        self.bot.paused = False
        self.bot.start_time = time.time()
        
        # 更新按钮状态
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        
        # 启动统计线程
        self.start_time_thread()
        
        # 启动工作线程
        threading.Thread(target=self.run_bot, daemon=True).start()

    def run_bot(self):
        """运行核心逻辑"""
        total_item = len(self.bot.config["item_positions"])
        
        for idx, item_pos in enumerate(self.bot.config["item_positions"], 1):
            if not self.bot.running:
                break
            # 更新当前物品计数
            self.current_item_var.set(f"{idx}/{total_item}")
            self.status_var.set(f"状态：运行中（处理物品 {idx}/{total_item}）")
            # 处理单个物品
            success = self.bot.process_one_item(item_pos)
            if success:
                self.bot.beep()
                self.status_var.set(f"状态：物品 {idx} 达标！切换到下一个物品")
        
        # 运行结束
        self.bot.running = False
        self.bot.paused = False
        self.status_var.set("状态：已停止（所有物品处理完成或手动停止）")
        self.bot.beep(1500, 800)
        # 重置按钮状态
        self.root.after(0, lambda: self.start_btn.config(state="normal"))
        self.root.after(0, lambda: self.pause_btn.config(state="disabled"))
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))

    def pause_tool(self):
        """暂停工具"""
        self.bot.paused = True
        self.status_var.set("状态：已暂停（按 F1 键或点击继续按钮恢复）")
        self.pause_btn.config(text="继续", command=self.resume_tool)

    def resume_tool(self):
        """恢复工具"""
        self.bot.paused = False
        total_item = len(self.bot.config["item_positions"])
        current = self.current_item_var.get().split("/")[0]
        self.status_var.set(f"状态：运行中（处理物品 {current}/{total_item}）")
        self.pause_btn.config(text="暂停", command=self.pause_tool)

    def stop_tool(self):
        """停止工具"""
        self.bot.running = False
        self.bot.paused = False
        self.status_var.set("状态：停止中...")

    def start_time_thread(self):
        """启动时间统计线程"""
        if self.time_thread and self.time_thread.is_alive():
            return
        def update_time():
            while self.bot.running:
                if self.bot.paused:
                    time.sleep(0.1)
                    continue

                for orb_key, orb_count_var in self.orb_coord_vars.items():
                    count = getattr(self.bot, f"{orb_key}_count")
                    orb_count_var.set(f"{count}")
                
                # 计算运行时间
                elapsed = int(time.time() - self.bot.start_time)
                hours = elapsed // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                self.time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                time.sleep(1)
        self.time_thread = threading.Thread(target=update_time, daemon=True)
        self.time_thread.start()

    def update_all(self):
        """定期更新界面"""
        self.root.after(100, self.update_all)

    def on_closing(self):
        """关闭窗口时的处理"""
        self.bot.running = False
        self.bot.paused = False
        # 保存配置
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