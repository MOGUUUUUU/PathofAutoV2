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

pyautogui.PAUSE = 0.03

STATE_INIT = "init"
STATE_AUGMENT = "augment"
STATE_CHECK_AUG = "check_aug"
STATE_ALTER = "alter"
STATE_CHECK_ALT = "check_alt"

class PoeOrbBot:
    def __init__(self):
        self.running = False
        self.transmutation_count = 0
        self.alter_count = 0
        self.augment_count = 0
        self.start_time = 0
        self.status_var = None

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
                        loaded[key] = [list(pos) if isinstance(pos, (list, tuple)) else pos for pos in loaded[key]]
                self.config.update(loaded)
            except:
                pass

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
        cnt = 0
        for t in self.config["target_affixes"]:
            if t in text:
                cnt += 1
        return cnt >= need_count

    def check_item(self, item_pos, need_count):
        pyautogui.moveTo(item_pos, duration=0.05)
        self.rand_sleep()
        txt = self.get_item_info()
        return self.has_target_affix(txt, need_count)

    def use_orb(self, orb_name, item_pos=None):
        if orb_name == "alter":
            poses = self.config.get("alter_positions")
        elif orb_name == "augment":
            poses = self.config.get("augment_positions")
        else:
            p = self.config.get(f"{orb_name}_pos")
            if not p:
                raise RuntimeError(f"{orb_name} 未设置")
            poses = [p]

        if not poses:
            raise RuntimeError(f"{orb_name} 坐标为空")

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

    def process_one_item(self, item_pos) -> bool:
        if not self.running:
            return False

        state = STATE_INIT
        target = 1

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
                    if self.check_item(item_pos, target):
                        self.beep(1200, 600)
                        return True
                    state = STATE_ALTER

                elif state == STATE_ALTER:
                    self.use_orb("alter", item_pos)
                    self.rand_sleep(0.05)
                    state = STATE_CHECK_ALT

                elif state == STATE_CHECK_ALT:
                    if self.check_item(item_pos, target):
                        self.beep(1200, 600)
                        return True
                    state = STATE_AUGMENT

                time.sleep(0.01)

            except Exception as e:
                print("异常:", e)
                self.rand_sleep(0.1)
        return False

class PoeOrbBotGUI:
    ORB_NAMES = {
        "transmutation": "蜕变石",
        "alter": "改造石",
        "augment": "增幅石",
    }

    def __init__(self, bot):
        self.bot = bot
        self.root = tk.Tk()
        self.root.title("POE 洗词缀工具")
        self.root.geometry("540x720")
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

        self.bot.status_var = self.status_var
        self._init_vars()
        self.create_widgets()
        self.root.bind('<equal>', lambda e: self.get_coord(self.coord_type.get()))
        self.time_thread = None
        self.update_all()

    def _init_vars(self):
        for k in self.ORB_NAMES:
            if k not in ["alter", "augment"]:
                pos = self.bot.config.get(f"{k}_pos")
                self.orb_coord_vars[k] = tk.StringVar(value=f"({pos[0]},{pos[1]})" if pos else "未设置")
            self.orb_count_vars[k] = tk.StringVar(value="0")

    def create_widgets(self):
        # 坐标
        f_coord = ttk.LabelFrame(self.root, text="坐标设置（鼠标移过去按 =）")
        f_coord.pack(padx=5, pady=3, fill=tk.BOTH, expand=True)
        row = 0
        for k, name in self.ORB_NAMES.items():
            if k in ["alter", "augment"]:
                ttk.Radiobutton(f_coord, text=name, variable=self.coord_type, value=k).grid(row=row, column=0, sticky=tk.W)
                tree = ttk.Treeview(f_coord, columns=("i", "p"), show="headings", height=2)
                tree.heading("i", text="序号")
                tree.heading("p", text="坐标")
                tree.column("i", width=50)
                tree.column("p", width=120)
                tree.grid(row=row, column=1, columnspan=2, sticky=tk.NSEW)
                if k == "alter":
                    self.alter_tree = tree
                    self.update_alter_tree()
                else:
                    self.augment_tree = tree
                    self.update_augment_tree()
                ttk.Button(f_coord, text="删除", command=lambda k=k: self.del_orb(k)).grid(row=row, column=3)
                row += 1
            else:
                ttk.Radiobutton(f_coord, text=name, variable=self.coord_type, value=k).grid(row=row, column=0, sticky=tk.W)
                ttk.Entry(f_coord, textvariable=self.orb_coord_vars[k], state="readonly", width=16).grid(row=row, column=1)
                row += 1
        ttk.Radiobutton(f_coord, text="物品坐标", variable=self.coord_type, value="item").grid(row=row, column=0, columnspan=4, sticky=tk.W)

        # 物品列表
        f_item = ttk.LabelFrame(self.root, text="物品列表")
        f_item.pack(padx=5, pady=3, fill=tk.BOTH, expand=True)
        self.item_tree = ttk.Treeview(f_item, columns=("i", "p"), show="headings", height=3)
        self.item_tree.heading("i", text="序号")
        self.item_tree.heading("p", text="坐标")
        self.item_tree.column("i", width=50)
        self.item_tree.column("p", width=120)
        self.item_tree.grid(row=0, column=0, columnspan=3, sticky=tk.NSEW)
        sb = ttk.Scrollbar(f_item, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=3, sticky=tk.NS)
        f_btn = ttk.Frame(f_item)
        f_btn.grid(row=1, column=0, columnspan=4)
        ttk.Button(f_btn, text="添加物品", command=lambda: self.get_coord("item")).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(f_btn, text="删除选中", command=self.del_item).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(f_btn, text="清空", command=self.clear_item).pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.update_item_tree()

        # 词缀
        f_affix = ttk.LabelFrame(self.root, text="目标词缀")
        f_affix.pack(padx=5, pady=3, fill=tk.X)
        ttk.Label(f_affix, text="词缀：").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(f_affix, textvariable=self.affix_input_var).grid(row=0, column=1)
        ttk.Button(f_affix, text="添加", command=self.add_affix).grid(row=0, column=2)
        self.affix_list = Listbox(f_affix, height=3)
        self.affix_list.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)
        sba = ttk.Scrollbar(f_affix, command=self.affix_list.yview)
        self.affix_list.configure(yscrollcommand=sba.set)
        sba.grid(row=1, column=2, sticky=tk.NS)
        ttk.Button(f_affix, text="删除选中", command=self.del_affix).grid(row=2, column=0, columnspan=3, fill=tk.X)
        self.update_affix()

        # 控制
        ttk.Label(self.root, text="F3 开始/停止").pack()

        # 统计
        f_stat = ttk.LabelFrame(self.root, text="统计")
        f_stat.pack(padx=5, pady=3, fill=tk.X)
        for i, (k, name) in enumerate(self.ORB_NAMES.items()):
            r = i // 3
            c = i % 3 * 2
            ttk.Label(f_stat, text=f"{name}：").grid(row=r, column=c)
            ttk.Entry(f_stat, textvariable=self.orb_count_vars[k], state="readonly", width=7).grid(row=r, column=c+1)
        ttk.Label(f_stat, text="物品：").grid(row=1, column=0)
        ttk.Entry(f_stat, textvariable=self.current_item_var, state="readonly", width=7).grid(row=1, column=1)
        ttk.Label(f_stat, text="时间：").grid(row=1, column=2)
        ttk.Entry(f_stat, textvariable=self.time_var, state="readonly", width=7).grid(row=1, column=3)

        # 状态
        ttk.Label(self.root, textvariable=self.status_var, foreground="blue").pack(pady=2)

        # 配置
        f_cfg = ttk.Frame(self.root)
        f_cfg.pack(pady=2)
        ttk.Button(f_cfg, text="保存配置", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(f_cfg, text="加载配置", command=self.load).pack(side=tk.LEFT, padx=5)

    def get_coord(self, t):
        x, y = pyautogui.position()
        if t == "item":
            self.bot.config["item_positions"].append((x, y))
            self.update_item_tree()
            self.status_var.set(f"已加物品 ({x},{y})")
        elif t == "alter":
            self.bot.config["alter_positions"].append((x, y))
            self.update_alter_tree()
        elif t == "augment":
            self.bot.config["augment_positions"].append((x, y))
            self.update_augment_tree()
        else:
            self.bot.config[f"{t}_pos"] = (x, y)
            self.orb_coord_vars[t].set(f"({x},{y})")
            self.status_var.set(f"已设置 {self.ORB_NAMES[t]}")

    def update_alter_tree(self):
        for i in self.alter_tree.get_children():
            self.alter_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["alter_positions"], 1):
            self.alter_tree.insert("", "end", values=(idx, f"({x},{y})"))

    def update_augment_tree(self):
        for i in self.augment_tree.get_children():
            self.augment_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["augment_positions"], 1):
            self.augment_tree.insert("", "end", values=(idx, f"({x},{y})"))

    def del_orb(self, k):
        if k == "alter":
            lst = self.bot.config["alter_positions"]
            tree = self.alter_tree
        elif k == "augment":
            lst = self.bot.config["augment_positions"]
            tree = self.augment_tree
        else:
            return
        sel = tree.selection()
        if not sel:
            return
        idx = int(tree.item(sel[0])["values"][0]) - 1
        del lst[idx]
        if k == "alter":
            self.update_alter_tree()
        else:
            self.update_augment_tree()

    def update_item_tree(self):
        for i in self.item_tree.get_children():
            self.item_tree.delete(i)
        for idx, (x, y) in enumerate(self.bot.config["item_positions"], 1):
            self.item_tree.insert("", "end", values=(idx, f"({x},{y})"))
        self.current_item_var.set(f"0/{len(self.bot.config['item_positions'])}")

    def del_item(self):
        sel = self.item_tree.selection()
        if not sel:
            return
        idx = int(self.item_tree.item(sel[0])["values"][0]) - 1
        del self.bot.config["item_positions"][idx]
        self.update_item_tree()

    def clear_item(self):
        self.bot.config["item_positions"].clear()
        self.update_item_tree()

    def update_affix(self):
        self.affix_list.delete(0, tk.END)
        for a in self.target_affixes:
            self.affix_list.insert(tk.END, a)

    def add_affix(self):
        a = self.affix_input_var.get().strip()
        if a and a not in self.target_affixes:
            self.target_affixes.append(a)
            self.update_affix()
            self.affix_input_var.set("")

    def del_affix(self):
        sel = self.affix_list.curselection()
        if not sel:
            return
        for i in reversed(sel):
            del self.target_affixes[i]
        self.update_affix()

    def save(self):
        self.bot.config["target_affixes"] = self.target_affixes.copy()
        self.bot.save_config()
        messagebox.showinfo("OK", "保存成功")

    def load(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        tmp = PoeOrbBot()
        tmp.config_file = p
        tmp.load_config()
        self.bot.config.update(tmp.config)
        self.update_item_tree()
        self.update_alter_tree()
        self.update_augment_tree()
        self.target_affixes = self.bot.config["target_affixes"].copy()
        self.update_affix()
        for k in self.ORB_NAMES:
            if k not in ["alter", "augment"]:
                pos = self.bot.config.get(f"{k}_pos")
                self.orb_coord_vars[k].set(f"({pos[0]},{pos[1]})" if pos else "未设置")
        messagebox.showinfo("OK", "加载成功")

    def toggle_run(self):
        if self.bot.running:
            self.bot.running = False
            self.status_var.set("已停止")
        else:
            self.start()

    def start(self):
        if not self.bot.config["item_positions"]:
            messagebox.showwarning("!", "请加物品坐标")
            return
        if not self.target_affixes:
            messagebox.showwarning("!", "请加目标词缀")
            return
        self.bot.config["target_affixes"] = self.target_affixes.copy()
        self.bot.running = True
        self.bot.start_time = time.time()
        self.start_time_thread()
        threading.Thread(target=self.run_loop, daemon=True).start()
        self.status_var.set("运行中...")

    def run_loop(self):
        total = len(self.bot.config["item_positions"])
        for i, pos in enumerate(self.bot.config["item_positions"], 1):
            if not self.bot.running:
                break
            self.current_item_var.set(f"{i}/{total}")
            self.status_var.set(f"正在洗第 {i}/{total} 件")
            self.bot.process_one_item(pos)
        self.bot.running = False
        self.status_var.set("已完成")
        self.bot.beep(1500, 800)

    def start_time_thread(self):
        def upd():
            while self.bot.running:
                for k, v in self.orb_count_vars.items():
                    v.set(str(getattr(self.bot, f"{k}_count", 0)))
                used = int(time.time() - self.bot.start_time)
                h = used // 3600
                m = used % 3600 // 60
                s = used % 60
                self.time_var.set(f"{h:02d}:{m:02d}:{s:02d}")
                time.sleep(0.2)
        threading.Thread(target=upd, daemon=True).start()

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