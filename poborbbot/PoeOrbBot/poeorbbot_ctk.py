import pyautogui
import random
import re
import time
import json
import os
import sys
import pyperclip
import threading
import winsound
import customtkinter as ctk
from tkinter import messagebox, filedialog

    # ── Windows DPI 感知（解决高分屏模糊） ──
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    # ── 控件缩放（1.0 = 原始, 1.2 = 放大 20%） ──
ctk.set_widget_scaling(1.2)
ctk.set_window_scaling(1.0)  # 窗口尺寸不变，只放大内容

pyautogui.PAUSE = 0.035


class FlowLayout(ctk.CTkFrame):
    """流式布局容器：子控件从左到右排列，超出宽度自动换行"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._widgets = []
        self._bind_id = None
        self._last_width = None
        self._layout_height = None
        self.bind("<Configure>", self._on_configure)

    def add_widget(self, widget):
        self._widgets.append(widget)
        widget.pack_forget()
        self._schedule_reflow()

    def _on_configure(self, event=None):
        width = self.winfo_width()
        if width != self._last_width:
            self._last_width = width
            self._schedule_reflow()

    def destroy(self):
        if self._bind_id is not None:
            self.after_cancel(self._bind_id)
            self._bind_id = None
        super().destroy()

    def _schedule_reflow(self):
        # 合并同一事件循环中的连续布局请求，避免反复同步重排。
        if self._bind_id is None:
            self._bind_id = self.after_idle(self._reflow)

    def _reflow(self):
        # 等待新标签内部的文字和关闭按钮完成尺寸计算后再测量。
        self.update_idletasks()
        self._bind_id = None
        if not self._widgets:
            return
        # winfo_* 返回屏幕像素，CTk 的 place/configure 接收缩放前尺寸。
        # 统一换算为逻辑尺寸，避免 1.2 倍缩放被重复应用导致越界和间距异常。
        max_w = self._reverse_widget_scaling(self.winfo_width())
        if max_w <= 1:
            return
        x = y = 0
        row_h = 0
        for w in self._widgets:
            ww = self._reverse_widget_scaling(w.winfo_reqwidth())
            wh = self._reverse_widget_scaling(w.winfo_reqheight())
            if x + ww > max_w and x > 0:
                x = 0
                y += row_h + 2
                row_h = 0
            w.place(x=x, y=y)
            x += ww + 4
            row_h = max(row_h, wh)
        # 更新容器高度以适应内容
        height = y + row_h + 4
        if height != self._layout_height:
            self._layout_height = height
            self.configure(height=height)

# ──────────────────────────────────────────────
# 词缀数据
# ──────────────────────────────────────────────
import json as _json

_POS_MAP = {"前缀": "prefixes", "后缀": "suffixes"}
_POS_REVERSE = {"prefixes": "前缀", "suffixes": "后缀"}
AFFIX_SOURCES = {"普通": "", "塑界": "塑界者", "裂界": "裂界者",
                 "圣战": "圣战者", "救赎": "救赎者", "狩猎": "狩猎者", "督军": "督军"}

def _load_affix_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    affix_path = os.path.join(base_dir, 'affixes_equipment_types.json')
    try:
        with open(affix_path, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        raw = data.get('equipmentTypes', {})
        # 将英文位置 key 转为中文，保持与 pos_combo 一致
        result = {}
        for equip_type, positions in raw.items():
            result[equip_type] = {}
            for pos_key, affixes in positions.items():
                cn_key = _POS_REVERSE.get(pos_key, pos_key)
                result[equip_type][cn_key] = affixes
        return result, list(raw.keys())
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}, []

def _build_affix_index(affix_data):
    """按词缀种类分组：{(equip_type, position): [affix, ...]}
    每个affix: {name, max_level, total_weight, tiers: [{name, value, tier, weight, req_lvl, types}]}"""
    index = {}
    for equip_type, positions in affix_data.items():
        for position, affixes in positions.items():
            grouped = {}
            normal = []
            for affix in affixes:
                if not affix.get('influence') and not any(t.get('influence') for t in affix.get('tiers', [])):
                    normal.append(affix)
                    continue
                for tier in affix.get('tiers', []):
                    influence = tier.get('influence') or affix.get('influence', '')
                    # 使用完整多行属性模板，避免把辅助技能相同但副属性不同的词缀合并。
                    value = tier.get('value', '')
                    template = re.sub(r'[（(]\s*[+-]?\d+(?:\.\d+)?\s*[-—–~～至]\s*[+-]?\d+(?:\.\d+)?\s*[）)]', '#', value)
                    template = re.sub(r'[+-]?\d+(?:\.\d+)?', '#', template)
                    template = re.sub(r'\s+', ' ', template).strip()
                    key = (influence, template, tuple(sorted(tier.get('types', []))))
                    group = grouped.setdefault(key, {'name': template, 'influence': influence, 'tiers': [], 'inferred_tiers': True})
                    if tier not in group['tiers']:
                        group['tiers'].append(dict(tier))
            # 源数据的势力档位均标为 T1，按需求等级从高到低重建档位顺序。
            for group in grouped.values():
                group['tiers'].sort(key=lambda t: t.get('req_lvl', 0), reverse=True)
                levels = sorted({t.get('req_lvl', 0) for t in group['tiers']}, reverse=True)
                for tier in group['tiers']:
                    tier['tier'] = f"T{levels.index(tier.get('req_lvl', 0)) + 1}"
                group['max_level'] = max(levels, default=0)
                group['total_weight'] = sum(t.get('weight', 0) for t in group['tiers'])
            # 极少数同描述、不同属性标签的组也必须能分别选取。
            names = {}
            for group in grouped.values():
                name_key = (group['influence'], group['name'])
                names[name_key] = names.get(name_key, 0) + 1
                if names[name_key] > 1:
                    group['name'] += f" [{names[name_key]}]"
            index[(equip_type, position)] = normal + list(grouped.values())
    return index

_FULL_AFFIX_DATA, _FULL_EQUIPMENT_TYPES = _load_affix_data()
_AFFIX_INDEX = _build_affix_index(_FULL_AFFIX_DATA)

EQUIPMENT_CATEGORIES = {
    "武器": ["爪", "匕首", "符文匕首", "单手剑", "细剑", "单手斧", "单手锤", "弓",
             "双手剑", "双手斧", "双手锤", "长杖", "战杖", "短杖", "法杖", "鱼竿"],
    "防具": ["手套(str)", "手套(dex)", "手套(int)", "手套(str_dex)", "手套(str_int)", "手套(dex_int)",
             "鞋子(str)", "鞋子(dex)", "鞋子(int)", "鞋子(str_dex)", "鞋子(str_int)", "鞋子(dex_int)",
             "胸甲(str)", "胸甲(dex)", "胸甲(int)", "胸甲(str_dex)", "胸甲(str_int)", "胸甲(dex_int)", "胸甲(str_dex_int)",
             "头部(str)", "头部(dex)", "头部(int)", "头部(str_dex)", "头部(str_int)", "头部(dex_int)",
             "盾牌(str)", "盾牌(dex)", "盾牌(int)", "盾牌(str_dex)", "盾牌(str_int)", "盾牌(dex_int)"],
    "首饰": ["项链", "戒指", "腰带", "箭袋"],
    "珠宝": ["三相珠宝", "永恒珠宝", "星团珠宝"],
    "药剂": ["功能药剂", "生命药剂", "魔力药剂"],
}

CURRENCY_LIST = [
    ("transmutation", "蜕变石"),
    ("alteration", "改造石"),
    ("augment", "增幅石"),
    ("scouring", "重铸石"),
    ("chaos", "混沌石"),
    ("alchemy", "点金石"),
]


# ──────────────────────────────────────────────
# Bot 基类
# ──────────────────────────────────────────────
CRAFT_MODES = {
    "1. 蜕变 → 改造 → 改造…": (("transmutation",), ("alteration",)),
    "2. 蜕变 → 改造 → 增幅 → 循环": (("transmutation",), ("alteration", "augment")),
    "3. 重铸 → 点金 → 循环": ((), ("scouring", "alchemy")),
    "4. 点金 → 混沌 → 混沌…": (("alchemy",), ("chaos",)),
}


class PoeOrbBotBase:
    def __init__(self):
        self.running = False
        self.currency_counts = {}
        self.total_currency_used = 0
        self.start_time = 0
        self.config = {
            "equipment_type": "单手剑",
            "orb_positions": {},
            "alter_positions": [],
            "augment_positions": [],
            "item_positions": [],
            "interval": 0.02,
            "use_augment": True,
            "craft_mode": next(iter(CRAFT_MODES)),
            "per_item_currency_limit": 2000,
            "total_currency_limit": 0,
            "craft_steps": [
                {"action": "currency", "currency": "transmutation",
                 "condition_group": {"conditions": [], "min_required": 1},
                 "success_handling": "terminateSuccess", "failure_handling": "jump", "jump_target": 0}
            ],
            "target_conditions": [
                {"equipment_type": "单手剑", "position": "前缀", "conditions": [], "logic": "or"}
            ],
        }
        if getattr(sys, "frozen", False):
            # 单文件包中的资源只读；客户配置保存在稳定、可写的用户目录。
            config_dir = os.path.join(
                os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                "PoeOrbBot",
            )
            os.makedirs(config_dir, exist_ok=True)
            self.config_file = os.path.join(config_dir, "poe_改造助手_config.json")
        else:
            self.config_file = "poe_改造助手_config.json"
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
        if base is None:
            base = self.config.get("interval", 0.02)
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
            text = pyperclip.paste()
            if text:
                return text
        return ""

    def _match_affix_text(self, item_text, affix_pattern):
        """普通文本按子串匹配；括号中的数值范围按实际数值匹配（含边界）。"""
        if not affix_pattern:
            return False
        number = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
        range_pattern = re.compile(
            rf"[（(]\s*({number})\s*[-—–~～至]\s*({number})\s*[）)]"
        )
        ranges = list(range_pattern.finditer(affix_pattern))
        if not ranges:
            return affix_pattern in item_text

        parts = []
        bounds = []
        end = 0
        for match in ranges:
            parts.append(re.escape(affix_pattern[end:match.start()]))
            parts.append(rf"(?<![\d.+-])({number})(?![\d.])")
            bounds.append(sorted((float(match.group(1)), float(match.group(2)))))
            end = match.end()
        parts.append(re.escape(affix_pattern[end:]))

        # 同一条词缀可能含多个范围，必须在一次完整匹配中全部满足。
        for match in re.finditer("".join(parts), item_text):
            if all(low <= float(value) <= high
                   for value, (low, high) in zip(match.groups(), bounds)):
                return True
        return False

    def check_logic_groups(self, item_pos, target_conditions):
        pyautogui.moveTo(item_pos, duration=0.05)
        self.rand_sleep()
        text = self.get_item_info()
        if not text:
            return False
        for group in target_conditions:
            conditions = group.get("conditions", [])
            if not conditions:
                continue
            logic = group.get("logic", "or")
            matched = sum(1 for cond in conditions if self._match_affix_text(text, cond.get("text", "")))
            if logic == "and":
                if matched != len(conditions):
                    return False
            elif logic == "not":
                if matched > 0:
                    return False
            else:
                if matched < 1:
                    return False
        return True

    def check_item(self, item_pos, need_count=None):
        return self.check_logic_groups(item_pos, self.config.get("target_conditions", []))

    def get_currency_positions(self, orb_name):
        """返回可修改的坐标列表，并兼容旧配置中的单个坐标。"""
        if orb_name in ("alteration", "alter", "augment"):
            key = "alter_positions" if orb_name in ("alteration", "alter") else "augment_positions"
            return self.config.setdefault(key, [])
        orb_positions = self.config.setdefault("orb_positions", {})
        positions = orb_positions.get(orb_name, [])
        if positions and len(positions) == 2 and all(isinstance(v, (int, float)) for v in positions):
            positions = [list(positions)]
        else:
            positions = list(positions or [])
        orb_positions[orb_name] = positions
        return positions

    def use_orb(self, orb_name, item_pos=None):
        poses = self.get_currency_positions(orb_name)
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
        self.currency_counts[orb_name] = self.currency_counts.get(orb_name, 0) + 1
        self.total_currency_used += 1

    def process_one_item(self, item_pos) -> bool:
        if not self.running:
            return False
        per_item_limit = self.config.get("per_item_currency_limit", 2000)
        total_limit = self.config.get("total_currency_limit", 0)
        initial, cycle = CRAFT_MODES[self.config["craft_mode"]]
        used = 0
        while self.running:
            if (per_item_limit and used >= per_item_limit) or (
                    total_limit and self.total_currency_used >= total_limit):
                return False
            orb = initial[used] if used < len(initial) else cycle[(used - len(initial)) % len(cycle)]
            self.use_orb(orb, item_pos)
            used += 1
            self.rand_sleep(0.1)
            if self.check_logic_groups(item_pos, self.config.get("target_conditions", [])):
                return True
        return False


# ══════════════════════════════════════════════
#  CustomTkinter GUI
# ══════════════════════════════════════════════

# CTk 原生双主题配色，顺序为 (浅色, 深色)。动态创建/悬停也使用这些值。
BG_BASE       = ("#ffffff", "#0d1117")
CARD_BG       = ("#f6f8fa", "#161b22")
SURFACE       = ("#f3f4f6", "#1c2128")
BORDER        = ("#d0d7de", "#30363d")
TEXT_PRIMARY  = ("#1f2328", "#c9d1d9")
TEXT_MUTED    = ("#656d76", "#8b949e")
TEXT_FAINT    = ("#6e7781", "#6e7681")
ACCENT        = ("#0969da", "#1f6feb")
ACCENT_HOVER  = ("#0550ae", "#388bfd")
SUCCESS       = ("#1a7f37", "#3fb950")
WARNING       = ("#9a6700", "#d29922")
DANGER        = ("#cf222e", "#f85149")
ALT_BG        = ("#eaeef2", "#21262d")
ALT_HOVER     = ("#d0d7de", "#30363d")
BUTTON_HOVER  = ("#afb8c1", "#484f58")
SUCCESS_HOVER = ("#116329", "#2ea043")


def section(parent, title, desc=None, icon=None, collapsed=False):
    """创建可折叠卡片"""
    card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                        border_width=1, border_color=BORDER)
    
    # 标题行
    header_frame = ctk.CTkFrame(card, fg_color=SURFACE, corner_radius=0, height=40)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)
    
    arrow_var = ctk.StringVar(value="▼" if not collapsed else "▶")
    
    def toggle():
        if outer.winfo_viewable():
            # 折叠：隐藏内容
            outer.pack_forget()
            arrow_var.set("▶")
        else:
            # 展开：显示内容（不使用 expand，让内容决定高度）
            outer.pack(fill="x")
            content_frame.pack(fill="x")
            arrow_var.set("▼")
        # 强制更新卡片和父容器布局
        card.update_idletasks()
        parent.update_idletasks()
    
    arrow_label = ctk.CTkLabel(header_frame, textvariable=arrow_var,
                               font=("", 11), text_color=TEXT_FAINT, width=24)
    arrow_label.pack(side="left", padx=(12, 0))
    arrow_label.bind("<Button-1>", lambda e: toggle())
    
    if icon:
        ctk.CTkLabel(header_frame, text=icon, font=("", 14), 
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 4))
    
    title_label = ctk.CTkLabel(header_frame, text=title,
                                font=("", 12, "bold"), text_color=TEXT_MUTED)
    title_label.pack(side="left", padx=0)
    title_label.bind("<Button-1>", lambda e: toggle())
    
    if desc:
        ctk.CTkLabel(header_frame, text=desc, font=("", 10),
                     text_color=TEXT_FAINT).pack(side="right", padx=12)
    
    header_frame.bind("<Button-1>", lambda e: toggle())
    
    # 内容区
    outer = ctk.CTkFrame(card, fg_color=BORDER, corner_radius=0)
    content_frame = ctk.CTkFrame(outer, fg_color=CARD_BG, corner_radius=0)
    
    if collapsed:
        # 先不pack内容
        pass
    else:
        outer.pack(fill="x")
        content_frame.pack(fill="x")
    
    return card, content_frame


def make_button(parent, text, cmd, style="default", width=None, height=28):
    """创建统一风格按钮"""
    if style == "accent":
        fg, hover, tc = ACCENT, ACCENT_HOVER, "white"
    elif style == "danger":
        fg, hover, tc = ALT_BG, ALT_HOVER, DANGER
    elif style == "success":
        fg, hover, tc = SUCCESS, SUCCESS_HOVER, "white"
    else:
        fg, hover, tc = ALT_BG, ALT_HOVER, TEXT_PRIMARY
    
    btn = ctk.CTkButton(parent, text=text, command=cmd,
                        width=width, height=height, corner_radius=8,
                        fg_color=fg, hover_color=hover, text_color=tc,
                        font=("", 11))
    return btn


class MainApp:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.app = ctk.CTk()
        self.app.title("POE 改造助手")
        self.app.geometry("720x960")
        self.app.minsize(540, 640)
        self.app.configure(fg_color=BG_BASE)
        
        self.bot = PoeOrbBotBase()
        self.logic_groups = self.bot.config.get("target_conditions", [])
        if not self.logic_groups:
            self.logic_groups = [{"equipment_type": "单手剑", "position": "前缀",
                                  "conditions": [], "logic": "or"}]
        self.selected_group_index = 0
        self.coord_type = "transmutation"
        self._cards = []
        self._content_frames = []
        
        self._create_ui()
        
        # 恢复装备类型
        saved = self.bot.config.get("equipment_type", "")
        for cat, types in EQUIPMENT_CATEGORIES.items():
            if saved in types:
                self.category_var.set(cat)
                self._on_category_changed()
                self.equip_var.set(saved)
                break
        
        # 全局热键
        import keyboard
        keyboard.add_hotkey('f3', lambda: self.app.after(0, self._toggle_run))
        keyboard.add_hotkey('=', lambda: self.app.after(0, self._capture_coord))
        
        self.app.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _create_ui(self):
        # ── 顶部栏 ──
        header = ctk.CTkFrame(self.app, fg_color=CARD_BG, corner_radius=0, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="◈", font=("", 18),
                     text_color=TEXT_MUTED).pack(side="left", padx=(14, 4))
        ctk.CTkLabel(header, text="POE 改造助手", font=("", 15, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        
        # 主题切换按钮
        self.theme_btn = ctk.CTkButton(header, text="🌙", width=32, height=30,
                                        corner_radius=8, fg_color=ALT_BG,
                                        hover_color=ALT_HOVER, text_color=TEXT_MUTED,
                                        font=("", 13), command=self._toggle_theme)
        self.theme_btn.pack(side="left", padx=(12, 0))
        
        self.current_item_label = ctk.CTkLabel(header, text="物品 0/0",
                                               font=("Consolas", 11), text_color=TEXT_MUTED)
        self.current_item_label.pack(side="right", padx=14)
        
        self.time_label = ctk.CTkLabel(header, text="00:00:00",
                                       font=("Consolas", 11), text_color=TEXT_FAINT)
        self.time_label.pack(side="right", padx=4)
        
        self.header = header
        
        # ── 状态栏 ──
        status_bar = ctk.CTkFrame(self.app, fg_color=CARD_BG, corner_radius=0, height=34)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(status_bar,
                                         text="$ 就绪  ·  F3 开始/停止  ·  = 捕获坐标",
                                         font=("Consolas", 11), text_color=SUCCESS)
        self.status_label.pack(side="left", padx=14)
        
        # ── 主滚动区 ──
        self.scroll = ctk.CTkScrollableFrame(self.app, fg_color=BG_BASE,
                                             corner_radius=0, scrollbar_button_color=TEXT_FAINT)
        self.scroll.pack(fill="both", expand=True)
        
        self._create_coord_panel()
        self._create_affix_panel()
        self._create_craft_panel()
        self._create_stats_panel()
        
        # ── 底部控制栏 ──
        control_bar = ctk.CTkFrame(self.app, fg_color=CARD_BG, corner_radius=0, height=52)
        control_bar.pack(fill="x", side="bottom")
        control_bar.pack_propagate(False)
        self.control_bar = control_bar
        
        make_button(control_bar, "▶ 开始 (F3)", self._toggle_run,
                    "success", width=110).pack(side="left", padx=(14, 8), pady=10)
        
        ctk.CTkLabel(control_bar, text="间隔", font=("", 11),
                     text_color=TEXT_FAINT).pack(side="left", padx=(0, 4))
        
        self.interval_entry = ctk.CTkEntry(control_bar, width=64, height=30,
                                           corner_radius=8, fg_color=BG_BASE,
                                           border_color=BORDER, text_color=TEXT_PRIMARY,
                                           font=("Consolas", 11))
        self.interval_entry.pack(side="left", padx=4, pady=10)
        self.interval_entry.insert(0, str(self.bot.config.get("interval", 0.02)))
        
        for text, cmd in [("保存配置", self._save), ("加载配置", self._load), ("重置统计", self._reset_stats)]:
            make_button(control_bar, text, cmd, width=76).pack(side="left", padx=4, pady=10)
    
    # ── 坐标面板 ──
    def _create_coord_panel(self):
        card, content = section(self.scroll, "配置",
                                desc="鼠标定位后按 = 捕获", icon="◉", collapsed=False)
        self._cards.append(card)
        self._content_frames.append(content)
        card.pack(fill="x", padx=14, pady=(12, 6))
        
        self.capture_hint = ctk.CTkLabel(
            content, text="正在设置：蜕变石 · 鼠标定位后按 =",
            font=("", 10), text_color=ACCENT, anchor="w")
        self.capture_hint.pack(fill="x", padx=14, pady=(10, 6))
        currency_area = ctk.CTkFrame(content, fg_color=BG_BASE, corner_radius=8,
                                    border_width=1, border_color=BORDER)
        currency_area.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(currency_area, text="通货坐标", font=("", 11, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=10, pady=(8, 2))
        self.coord_chips = {}
        # 每种通货的选择按钮与坐标在同一行。
        self.currency_coord_frames = {}
        for k, name in CURRENCY_LIST:
            row = ctk.CTkFrame(currency_area, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=(3, 7))
            chip = make_button(row, name, lambda key=k: self._select_coord_type(key),
                               "accent" if k == self.coord_type else "default", width=76)
            chip.pack(side="left")
            self.coord_chips[k] = chip
            coords = FlowLayout(row, fg_color="transparent", height=28)
            coords.pack(side="left", padx=(8, 0), fill="x", expand=True)
            self.currency_coord_frames[k] = coords
            self._refresh_currency_coords(k)
        
        # 独立物品坐标区域，按实际处理顺序显示。
        item_area = ctk.CTkFrame(content, fg_color=BG_BASE, corner_radius=8,
                               border_width=1, border_color=BORDER)
        item_area.pack(fill="x", padx=12, pady=(10, 4))
        row = ctk.CTkFrame(item_area, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(row, text="物品坐标", font=("", 11, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        self.item_coord_lbl = ctk.CTkLabel(row, text="",
                                           font=("Consolas", 10), text_color=TEXT_MUTED, anchor="w")
        self.item_coord_lbl.pack(side="left", padx=(12, 0), fill="x", expand=True)
        make_button(row, "清空全部", self._clear_item_coords,
                    "danger", width=72, height=24).pack(side="right")
        self.item_chip = make_button(row, "添加坐标", lambda: self._select_coord_type("item"),
                                     width=76, height=24)
        self.item_chip.pack(side="right", padx=6)
        self.item_coords_frame = ctk.CTkScrollableFrame(
            item_area, fg_color="transparent", height=100,
            scrollbar_button_color=TEXT_FAINT)
        self.item_coords_frame.pack(fill="x", padx=6, pady=(4, 8))
        self._refresh_item_coords()
        
        # 分隔线
        sep = ctk.CTkFrame(content, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=8)
        
        ctk.CTkLabel(content, text="打造模式", font=("", 11, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=12)
        self.mode_combo = ctk.CTkComboBox(content, values=list(CRAFT_MODES),
                                        state="readonly", height=32)
        self.mode_combo.pack(fill="x", padx=12, pady=(4, 10))
        self.mode_combo.set(self.bot.config["craft_mode"])
        
        # 两个等宽字段，缩短说明，避免窄窗口横向拥挤。
        limits = ctk.CTkFrame(content, fg_color="transparent")
        limits.pack(fill="x", padx=12, pady=(0, 12))
        limits.grid_columnconfigure((0, 1), weight=1, uniform="limits")
        for column, (key, title, attr) in enumerate([
            ("per_item_currency_limit", "单物品通货最大消耗", "per_item_limit_entry"),
            ("total_currency_limit", "总物品通货最大消耗", "total_limit_entry"),
        ]):
            field = ctk.CTkFrame(limits, fg_color="transparent")
            field.grid(row=0, column=column, sticky="ew",
                       padx=(0, 6) if column == 0 else (6, 0))
            ctk.CTkLabel(field, text=title, font=("", 10),
                         text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 2))
            input_row = ctk.CTkFrame(field, fg_color="transparent")
            input_row.pack(fill="x")
            ctk.CTkLabel(input_row, text="0 为无限制", font=("", 9),
                         text_color=TEXT_FAINT).pack(side="right", padx=(4, 0))
            entry = ctk.CTkEntry(input_row, width=60, height=30, corner_radius=8,
                                placeholder_text="0 为无限制",
                                fg_color=BG_BASE, border_color=BORDER,
                                text_color=TEXT_PRIMARY, font=("Consolas", 11))
            entry.pack(side="left", fill="x", expand=True)
            entry.insert(0, str(self.bot.config[key]))
            setattr(self, attr, entry)
    
    def _select_coord_type(self, key):
        self.coord_type = key
        name = "物品坐标" if key == "item" else dict(CURRENCY_LIST).get(key, key)
        self.capture_hint.configure(text=f"正在设置：{name} · 鼠标定位后按 =")
        for k, chip in self.coord_chips.items():
            if k == key:
                chip.configure(fg_color=ACCENT, text_color="white")
            else:
                chip.configure(fg_color=ALT_BG, text_color=TEXT_MUTED)
        if key == "item":
            self.item_chip.configure(fg_color=SUCCESS, text_color="white")
        else:
            self.item_chip.configure(fg_color=ALT_BG, text_color=TEXT_MUTED)
    
    # ── 词缀面板 ──
    def _create_affix_panel(self):
        card, content = section(self.scroll, "词缀选取器", icon="◈", collapsed=False)
        self._cards.append(card)
        self._content_frames.append(content)
        card.pack(fill="x", padx=14, pady=6)
        
        # 下拉选择行
        ctrl_row = ctk.CTkFrame(content, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=6, pady=(8, 4))
        ctrl_row.grid_columnconfigure((1, 3, 5, 7), weight=1, uniform="affix_selectors")
        
        self.category_var = ctk.StringVar(value="武器")
        self.equip_var = ctk.StringVar(value="")
        
        ctk.CTkLabel(ctrl_row, text="分类", font=("", 10),
                     text_color=TEXT_FAINT).grid(row=0, column=0, padx=(2, 4))
        self.cat_combo = ctk.CTkComboBox(ctrl_row,
                                         values=list(EQUIPMENT_CATEGORIES.keys()),
                                         width=64, height=28, corner_radius=8,
                                         fg_color=ALT_BG, border_color=BORDER,
                                         button_color=BORDER, button_hover_color=BUTTON_HOVER,
                                         dropdown_fg_color=CARD_BG, dropdown_hover_color=SURFACE,
                                         text_color=TEXT_PRIMARY, font=("", 11),
                                         command=self._on_category_changed)
        self.cat_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        
        ctk.CTkLabel(ctrl_row, text="类型", font=("", 10),
                     text_color=TEXT_FAINT).grid(row=0, column=2, padx=(2, 4))
        initial_types = self._get_types_for_category("武器")
        self.equip_combo = ctk.CTkComboBox(ctrl_row,
                                           values=initial_types if initial_types else [""],
                                           width=78, height=28, corner_radius=8,
                                           fg_color=ALT_BG, border_color=BORDER,
                                           button_color=BORDER, button_hover_color=BUTTON_HOVER,
                                           dropdown_fg_color=CARD_BG, dropdown_hover_color=SURFACE,
                                           text_color=TEXT_PRIMARY, font=("", 11),
                                           variable=self.equip_var,
                                           command=lambda e: self._schedule_affix_refresh())
        self.equip_combo.configure(width=64)
        self.equip_combo.grid(row=0, column=3, sticky="ew", padx=(0, 4))
        
        ctk.CTkLabel(ctrl_row, text="位置", font=("", 10),
                     text_color=TEXT_FAINT).grid(row=0, column=4, padx=(2, 4))
        self.pos_combo = ctk.CTkComboBox(ctrl_row,
                                         values=["前缀", "后缀"],
                                         width=68, height=28, corner_radius=8,
                                         fg_color=ALT_BG, border_color=BORDER,
                                         button_color=BORDER, button_hover_color=BUTTON_HOVER,
                                         dropdown_fg_color=CARD_BG, dropdown_hover_color=SURFACE,
                                         text_color=TEXT_PRIMARY, font=("", 11),
                                         command=lambda e: self._schedule_affix_refresh())
        self.pos_combo.configure(width=64)
        self.pos_combo.grid(row=0, column=5, sticky="ew", padx=(0, 4))
        
        ctk.CTkLabel(ctrl_row, text="势力影响", font=("", 10),
                     text_color=TEXT_FAINT).grid(row=0, column=6, padx=(2, 4))
        self.influence_filter = ctk.CTkComboBox(
            ctrl_row, values=list(AFFIX_SOURCES), state="readonly", width=64, height=28,
            font=("", 11), fg_color=ALT_BG, border_color=BORDER,
            button_color=BORDER, button_hover_color=BUTTON_HOVER,
            dropdown_fg_color=CARD_BG, dropdown_hover_color=SURFACE,
            text_color=TEXT_PRIMARY,
            command=lambda value: self._schedule_affix_refresh())
        self.influence_filter.set("普通")
        self.influence_filter.grid(row=0, column=7, sticky="ew", padx=(0, 4))

        # 第二行：搜索框 + 词缀种类选择
        type_row = ctk.CTkFrame(content, fg_color="transparent")
        type_row.pack(fill="x", padx=12, pady=(4, 4))
        
        self.search_entry = ctk.CTkEntry(type_row, height=32, corner_radius=8,
                                         fg_color=BG_BASE, border_color=BORDER,
                                         text_color=TEXT_PRIMARY, font=("", 11),
                                         placeholder_text="搜索词缀种类...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._affix_refresh_after_id = None
        self._affix_render_after_id = None
        self.search_entry.bind("<KeyRelease>", lambda e: self._schedule_affix_refresh())
        
        make_button(type_row, "＋ 自定义", self._add_custom_affix,
                    width=80, height=32).pack(side="right")
        
        # 词缀种类下拉框
        affix_type_row = ctk.CTkFrame(content, fg_color="transparent")
        affix_type_row.pack(fill="x", padx=12, pady=(0, 4))
        
        ctk.CTkLabel(affix_type_row, text="种类", font=("", 10),
                     text_color=TEXT_FAINT).pack(side="left")
        self.affix_type_combo = ctk.CTkComboBox(affix_type_row,
                                                values=[""],
                                                width=300, height=32, corner_radius=8,
                                                fg_color=ALT_BG, border_color=BORDER,
                                                button_color=BORDER, button_hover_color=BUTTON_HOVER,
                                                dropdown_fg_color=CARD_BG, dropdown_hover_color=SURFACE,
                                                text_color=TEXT_PRIMARY, font=("", 11),
                                                command=lambda e: self._on_affix_type_changed())
        self.affix_type_combo.pack(side="left", padx=(6, 0), fill="x", expand=True)
        self.affix_type_combo.set("请选择词缀种类")
        
        # Tier 列表区
        list_frame = ctk.CTkFrame(content, fg_color=BG_BASE, corner_radius=8,
                                  border_width=1, border_color=BORDER)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        
        # 表头
        hdr = ctk.CTkFrame(list_frame, fg_color=SURFACE, corner_radius=0, height=26)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for txt, w in [("T级", 1), ("词缀名称", 2), ("数值范围", 3), ("权重", 1), ("等级", 1)]:
            ctk.CTkLabel(hdr, text=txt, font=("", 9, "bold"),
                         text_color=TEXT_FAINT).pack(side="left", padx=8,
                                                      expand=(w > 1), fill="x" if w > 1 else "none")
        
        # 滚动列表
        self.affix_scroll = ctk.CTkScrollableFrame(list_frame, fg_color=BG_BASE,
                                                    corner_radius=0, scrollbar_button_color=TEXT_FAINT)
        self.affix_scroll.pack(fill="both", expand=True)
        
        # 按钮行
        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(2, 8))
        ctk.CTkLabel(btn_row, text="选择来源 → 词缀 → 档位；T* 为按需求等级推定的档位",
                     font=("", 10), text_color=TEXT_FAINT).pack(side="left")
    
    def _get_types_for_category(self, category):
        cat_types = EQUIPMENT_CATEGORIES.get(category, [])
        return [t for t in cat_types if t in _FULL_AFFIX_DATA]
    
    def _on_category_changed(self, cat=None):
        cat = cat or self.category_var.get()
        types = self._get_types_for_category(cat)
        self.equip_combo.configure(values=types if types else [""])
        if types:
            self.equip_combo.set(types[0])
            self.equip_var.set(types[0])
        else:
            self.equip_combo.set("")
            self.equip_var.set("")
        self._schedule_affix_refresh()
    
    def _schedule_affix_refresh(self):
        """延迟刷新词缀列表，多次调用合并为一次"""
        if self._affix_refresh_after_id is not None:
            self.app.after_cancel(self._affix_refresh_after_id)
        if self._affix_render_after_id is not None:
            self.app.after_cancel(self._affix_render_after_id)
            self._affix_render_after_id = None
        self._affix_refresh_after_id = self.app.after(200, self._update_affix_list)

    def _update_affix_list(self, *args):
        """更新词缀种类下拉框（根据搜索过滤）"""
        self._affix_refresh_after_id = None
        
        equip_type = self.equip_var.get()
        position = self.pos_combo.get()
        search_value = self.search_entry.get().strip()
        search = search_value.lower() if search_value else ""

        if not equip_type:
            self.affix_type_combo.configure(values=[""])
            self.affix_type_combo.set("请选择词缀种类")
            self._clear_tier_list()
            return

        affixes = _AFFIX_INDEX.get((equip_type, position))
        if affixes is None:
            self.affix_type_combo.configure(values=[""])
            self.affix_type_combo.set("该装备类型暂无词缀数据")
            self._clear_tier_list()
            return

        # 按势力属性过滤，再应用搜索和字典序排序。
        influence = AFFIX_SOURCES[self.influence_filter.get()]
        affixes = [a for a in affixes if (a.get('influence') or '') == influence]
        self._visible_affixes = affixes
        if search:
            filtered = [a for a in affixes if search in a.get('name', '').lower()]
        else:
            filtered = affixes
        
        names = sorted(a.get('name', '') for a in filtered)
        if not names:
            names = [""]
        
        current = self.affix_type_combo.get()
        self.affix_type_combo.configure(values=names)
        # 如果当前选中的还在列表中，保持不变；否则重置
        if current not in names:
            self.affix_type_combo.set(names[0] if names and names[0] else "请选择词缀种类")
        self._on_affix_type_changed()

    def _on_affix_type_changed(self):
        """词缀种类改变时，更新 tier 列表"""
        self._clear_tier_list()
        
        equip_type = self.equip_var.get()
        position = self.pos_combo.get()
        affix_name = self.affix_type_combo.get()
        
        if not equip_type or not affix_name or affix_name in ("请选择词缀种类", "该装备类型暂无词缀数据", ""):
            return
        
        affixes = getattr(self, '_visible_affixes', [])
        affix = next((a for a in affixes if a.get('name') == affix_name), None)
        if not affix:
            return
        
        tiers = affix.get('tiers', [])
        if not tiers:
            # 没有tier数据，显示单行
            self._add_affix_row(
                tier="", name=affix_name, value=affix_name,
                weight=str(affix.get('total_weight', 0)),
                req_lvl=f"L{affix.get('max_level', '')}",
                affix_name=affix_name, match_text=affix_name)
            return
        
        # 按 tier 排序（T1 在前）
        def tier_sort_key(t):
            try:
                return int(str(t.get('tier', 'T999')).replace('T', ''))
            except ValueError:
                return 999
        
        sorted_tiers = sorted(tiers, key=tier_sort_key)
        
        for tier in sorted_tiers:
            # 势力词缀共用名称，需按描述和数值区分；普通词缀直接匹配档位名。
            tier_name = tier.get('name', '')
            influenced = bool(affix.get('influence') or tier.get('influence'))
            match_text = tier.get('value', '') if influenced else tier_name
            if not match_text:
                match_text = tier.get('value', '')
            detail = ' '.join((tier.get('value') or affix_name).split())
            label = f"{tier_name}·{detail}" if tier_name else detail
            self._add_affix_row(
                tier=(tier.get('tier', '') + '*') if affix.get('inferred_tiers') else tier.get('tier', ''),
                name=tier.get('name', ''),
                value=tier.get('value', '').replace('\n', ' '),
                weight=str(tier.get('weight', 0)),
                req_lvl=f"L{tier.get('req_lvl', '')}",
                affix_name=label,
                match_text=match_text)

    def _clear_tier_list(self):
        for w in self.affix_scroll.winfo_children():
            w.destroy()

    def _render_affix_batch(self, rows):
        pass  # 不再使用批量渲染
    
    def _add_affix_row(self, tier, name, value, weight, req_lvl, affix_name, match_text):
        def on_enter(e):
            row.configure(fg_color=SURFACE)
        def on_leave(e):
            row.configure(fg_color="transparent")
        def on_click(e):
            self._add_affix_to_group(affix_name, match_text)
        
        row = ctk.CTkFrame(self.affix_scroll, fg_color="transparent", corner_radius=6, height=28)
        row.pack(fill="x", pady=1)
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)
        row.bind("<Button-1>", on_click)
        
        ctk.CTkLabel(row, text=tier, font=("Consolas", 10, "bold"), text_color=ACCENT,
                     width=40, anchor="center").pack(side="left", padx=(8, 4))
        ctk.CTkLabel(row, text=name, font=("", 10), text_color=TEXT_PRIMARY,
                     anchor="w", width=100).pack(side="left", padx=4)
        ctk.CTkLabel(row, text=value, font=("Consolas", 9), text_color=TEXT_MUTED,
                     anchor="w").pack(side="left", padx=4, expand=True, fill="x")
        ctk.CTkLabel(row, text=weight, font=("Consolas", 9), text_color=TEXT_MUTED,
                     width=50, anchor="center").pack(side="left", padx=4)
        ctk.CTkLabel(row, text=req_lvl, font=("Consolas", 9), text_color=TEXT_MUTED,
                     width=40, anchor="center").pack(side="left", padx=(0, 8))
        
        # 让所有子控件也触发点击
        for widget in row.winfo_children():
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
    
    def _add_affix_to_group(self, affix_name, match_text):
        if not affix_name or self.selected_group_index >= len(self.logic_groups):
            return
        group = self.logic_groups[self.selected_group_index]
        conditions = group.get("conditions", [])
        if any(c.get("text") == match_text for c in conditions):
            return
        conditions.append({"text": match_text, "name": affix_name})
        group["conditions"] = conditions
        self._refresh_group_list()
    
    def _add_selected_affix_to_group(self):
        pass  # 已改为点击行直接添加
    
    def _add_custom_affix(self):
        dialog = ctk.CTkInputDialog(text="输入词缀文本:", title="添加自定义词缀")
        text = dialog.get_input()
        if text and text.strip():
            self._add_affix_to_group(text.strip(), text.strip())
    
        # ── 打造设置面板 ──
    def _create_craft_panel(self):
        card, content = section(self.scroll, "打造设置", icon="⚙", collapsed=False)
        self._cards.append(card)
        self._content_frames.append(content)
        card.pack(fill="x", padx=14, pady=6)
        
        # 配置选项行
        opts_row = ctk.CTkFrame(content, fg_color="transparent")
        opts_row.pack(fill="x", padx=12, pady=(8, 4))
        
        # 增幅开关已移至坐标设置面板
        ctk.CTkLabel(opts_row, text="每次使用通货后判断目标，达标后切换下一个物品",
                        font=("", 10), text_color=TEXT_FAINT).pack(side="left")
        
        # 逻辑组标题
        ctk.CTkLabel(content, text="逻辑组（组间 AND，组内按类型）",
                     font=("", 10), text_color=TEXT_FAINT).pack(anchor="w", padx=12, pady=(8, 2))

        # 逻辑组列表
        self.group_frame = ctk.CTkScrollableFrame(content, fg_color=BG_BASE,
                                                   corner_radius=8, border_width=1,
                                                   border_color=BORDER,
                                                   scrollbar_button_color=TEXT_FAINT,
                                                   height=120)
        self.group_frame.pack(fill="x", padx=12, pady=(0, 4))
        
        # 组操作按钮
        grp_btn_row = ctk.CTkFrame(content, fg_color="transparent")
        grp_btn_row.pack(fill="x", padx=12, pady=(2, 8))
        make_button(grp_btn_row, "+ 或组", lambda: self._add_group("or"),
                    "accent", width=64, height=26).pack(side="left", padx=(0, 4))
        make_button(grp_btn_row, "+ 且组", lambda: self._add_group("and"),
                    "accent", width=64, height=26).pack(side="left", padx=0)
        make_button(grp_btn_row, "+ 非组", lambda: self._add_group("not"),
                    "accent", width=64, height=26).pack(side="left", padx=4)
        make_button(grp_btn_row, "删除组", self._del_group,
                    "danger", width=64, height=26).pack(side="left", padx=0)
        
        self._refresh_group_list()
    
    def _refresh_group_list(self):
        for w in self.group_frame.winfo_children():
            w.destroy()
        
        for i, group in enumerate(self.logic_groups):
            logic = group.get("logic", "or")
            logic_label = {"or": "或 OR", "and": "且 AND", "not": "非 NOT"}.get(logic, logic)
            affixes = group.get("conditions", [])
            is_sel = (i == self.selected_group_index)
            
            bg = ALT_BG if is_sel else "transparent"
            border_w = 1 if is_sel else 0
            
            # 外层容器
            outer = ctk.CTkFrame(self.group_frame, fg_color="transparent")
            outer.pack(fill="x", padx=4, pady=2)
            
            # 逻辑类型 badge
            badge_frame = ctk.CTkFrame(outer, fg_color=bg, corner_radius=8,
                                       border_width=border_w, border_color=ACCENT)
            badge_frame.pack(anchor="w")
            
            badge = ctk.CTkLabel(badge_frame, text=logic_label, font=("", 9, "bold"),
                                 text_color=BG_BASE, fg_color=TEXT_MUTED,
                                 corner_radius=4, width=52, height=22)
            badge.pack(side="left", padx=(6, 4), pady=4)
            badge.bind("<Button-1>", lambda e, idx=i: self._select_group(idx))
            
            # 词缀芯片区域 - 使用 FlowLayout 自动换行
            if affixes:
                chip_wrap = FlowLayout(badge_frame, fg_color="transparent")
                chip_wrap.pack(side="left", padx=(0, 6), pady=4, fill="x", expand=True)
                
                for j, cond in enumerate(affixes):
                    name = cond.get("name", cond.get("text", ""))
                    self._make_affix_chip(chip_wrap, name, i, j)
            else:
                empty_lbl = ctk.CTkLabel(badge_frame, text="(空)", font=("", 10),
                                          text_color=TEXT_FAINT, anchor="w")
                empty_lbl.pack(side="left", padx=(0, 8), fill="x", expand=True)
                empty_lbl.bind("<Button-1>", lambda e, idx=i: self._select_group(idx))

    def _make_affix_chip(self, parent, name, group_idx, affix_idx):
        """创建可点击删除的词缀芯片"""
        chip = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=6,
                            border_width=1, border_color=BORDER)

        lbl = ctk.CTkLabel(chip, text=name, font=("", 10),
                            text_color=TEXT_PRIMARY, anchor="w")
        lbl.pack(side="left", padx=(8, 2), pady=4)

        # × 删除按钮
        x_btn = ctk.CTkLabel(chip, text="×", font=("", 11, "bold"),
                              text_color=TEXT_FAINT, width=18, height=18)
        x_btn.pack(side="right", padx=(0, 4), pady=4)

        # 点击芯片或 × 删除该词缀
        def remove(gi=group_idx, ai=affix_idx):
            if gi < len(self.logic_groups):
                conds = self.logic_groups[gi].get("conditions", [])
                if ai < len(conds):
                    conds.pop(ai)
                    self.logic_groups[gi]["conditions"] = conds
                    self._refresh_group_list()

        chip.bind("<Button-1>", lambda e: remove())
        lbl.bind("<Button-1>", lambda e: remove())
        x_btn.bind("<Button-1>", lambda e: remove())

        # hover 效果
        def on_enter(e):
            chip.configure(fg_color=ALT_HOVER, border_color=DANGER)
            x_btn.configure(text_color=DANGER)
        def on_leave(e):
            chip.configure(fg_color=SURFACE, border_color=BORDER)
            x_btn.configure(text_color=TEXT_FAINT)
        chip.bind("<Enter>", on_enter)
        chip.bind("<Leave>", on_leave)
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        x_btn.bind("<Enter>", on_enter)
        x_btn.bind("<Leave>", on_leave)

        # 添加到 FlowLayout
        if isinstance(parent, FlowLayout):
            parent.add_widget(chip)
        else:
            chip.pack(side="left", padx=2, pady=2)
    
    def _select_group(self, idx):
        self.selected_group_index = idx
        self._refresh_group_list()
    
    def _add_group(self, logic_type):
        self.logic_groups.append({
            "equipment_type": self.equip_var.get(),
            "position": self.pos_combo.get(),
            "conditions": [],
            "logic": logic_type,
        })
        self.selected_group_index = len(self.logic_groups) - 1
        self._refresh_group_list()
    
    def _del_group(self):
        if len(self.logic_groups) <= 1:
            messagebox.showinfo("提示", "至少保留一个逻辑组")
            return
        del self.logic_groups[self.selected_group_index]
        if self.selected_group_index >= len(self.logic_groups):
            self.selected_group_index = len(self.logic_groups) - 1
        self._refresh_group_list()
    
    def _del_affix(self):
        if self.selected_group_index >= len(self.logic_groups):
            return
        group = self.logic_groups[self.selected_group_index]
        conditions = group.get("conditions", [])
        if conditions:
            conditions.pop()
            group["conditions"] = conditions
            self._refresh_group_list()
    
    # ── 统计面板 ──
    def _create_stats_panel(self):
        card, content = section(self.scroll, "统计信息", icon="◔", collapsed=True)
        self._cards.append(card)
        self._content_frames.append(content)
        card.pack(fill="x", padx=14, pady=6)
        
        stats_row = ctk.CTkFrame(content, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=12)
        
        # 运行时间
        time_cell = ctk.CTkFrame(stats_row, fg_color=SURFACE, corner_radius=10,
                                 border_width=1, border_color=BORDER)
        time_cell.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(time_cell, text="运行时间", font=("", 10),
                     text_color=TEXT_MUTED).pack(pady=(8, 0))
        self.stats_time_label = ctk.CTkLabel(time_cell, text="00:00:00",
                                             font=("Consolas", 18, "bold"),
                                             text_color=TEXT_MUTED)
        self.stats_time_label.pack(pady=(0, 8))
        
        # 成功物品
        success_cell = ctk.CTkFrame(stats_row, fg_color=SURFACE, corner_radius=10,
                                    border_width=1, border_color=BORDER)
        success_cell.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(success_cell, text="成功物品", font=("", 10),
                     text_color=TEXT_MUTED).pack(pady=(8, 0))
        self.stats_success_label = ctk.CTkLabel(success_cell, text="0/0",
                                                font=("Consolas", 18, "bold"),
                                                text_color=TEXT_MUTED)
        self.stats_success_label.pack(pady=(0, 8))
        
        currency_stats = ctk.CTkFrame(content, fg_color="transparent")
        currency_stats.pack(fill="x", padx=12, pady=(0, 12))
        currency_stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="currency_stats")
        self.stat_labels = {}
        for index, (k, name) in enumerate(CURRENCY_LIST):
            cell = ctk.CTkFrame(currency_stats, fg_color=SURFACE, corner_radius=10,
                                border_width=1, border_color=BORDER)
            cell.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)
            
            ctk.CTkLabel(cell, text=name, font=("", 10),
                         text_color=TEXT_MUTED).pack(pady=(8, 0))
            
            lbl = ctk.CTkLabel(cell, text="0", font=("Consolas", 18, "bold"),
                               text_color=TEXT_MUTED)
            lbl.pack(pady=(0, 8))
            self.stat_labels[k] = lbl
    
    # ── 坐标操作 ──
    def _capture_coord(self):
        x, y = pyautogui.position()
        ct = self.coord_type
        
        if ct == "item":
            self.bot.config["item_positions"].append((x, y))
            self._refresh_item_coords()
            self._set_status(f"已添加物品坐标  ({x}, {y})")
        elif ct in self.currency_coord_frames:
            self.bot.get_currency_positions(ct).append((x, y))
            self._refresh_currency_coords(ct)
            name = dict(CURRENCY_LIST).get(ct, ct)
            self._set_status(f"已添加 {name} 坐标  ({x}, {y})")
    
    def _refresh_currency_coords(self, key):
        frame = self.currency_coord_frames[key]
        frame._widgets.clear()
        for widget in frame.winfo_children():
            widget.destroy()
        positions = self.bot.get_currency_positions(key)
        if not positions:
            frame.add_widget(ctk.CTkLabel(frame, text="未设置", font=("", 10),
                                          text_color=TEXT_FAINT))
            return
        for index, (x, y) in enumerate(positions):
            chip = self._make_coord_chip(
                frame, f"({x}, {y})",
                lambda k=key, i=index: self._remove_currency_coord(k, i))
            frame.add_widget(chip)

    def _remove_currency_coord(self, key, index):
        positions = self.bot.get_currency_positions(key)
        if index < len(positions):
            positions.pop(index)
        self._refresh_currency_coords(key)
    
    def _refresh_item_coords(self):
        positions = self.bot.config.get("item_positions", [])
        self.item_coord_lbl.configure(text=f"{len(positions)} 个物品坐标")
        for widget in self.item_coords_frame.winfo_children():
            widget.destroy()
        self.item_coords_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="coords")
        if not positions:
            ctk.CTkLabel(self.item_coords_frame, text="尚未添加物品坐标",
                         font=("", 10), text_color=TEXT_FAINT).grid(
                             row=0, column=0, columnspan=3, sticky="w", padx=4)
            return
        for index, (x, y) in enumerate(positions):
            self._make_item_coord_chip(index, x, y)

    def _make_item_coord_chip(self, index, x, y):
        def remove():
            positions = self.bot.config.get("item_positions", [])
            if index < len(positions):
                positions.pop(index)
                self._refresh_item_coords()
        chip = self._make_coord_chip(self.item_coords_frame, f"{index + 1}. ({x}, {y})", remove)
        chip.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=3)

    def _make_coord_chip(self, parent, text, on_remove):
        chip = ctk.CTkFrame(parent, fg_color=SURFACE,
                            corner_radius=6, border_width=1, border_color=BORDER,
                            cursor="hand2")
        close = ctk.CTkLabel(chip, text="×", width=18, font=("", 11),
                             text_color=TEXT_FAINT)
        close.pack(side="right", padx=(0, 4), pady=4)
        label = ctk.CTkLabel(chip, text=text,
                             font=("Consolas", 10), text_color=TEXT_PRIMARY, anchor="w")
        label.pack(side="left", padx=(8, 2), pady=4, fill="x", expand=True)

        def remove(event=None):
            on_remove()

        def on_enter(event=None):
            chip.configure(fg_color=ALT_HOVER, border_color=DANGER)
            close.configure(text_color=DANGER)

        def on_leave(event=None):
            chip.configure(fg_color=SURFACE, border_color=BORDER)
            close.configure(text_color=TEXT_FAINT)

        for widget in (chip, label, close):
            widget.bind("<Button-1>", remove)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        return chip

    def _clear_item_coords(self):
        self.bot.config["item_positions"].clear()
        self._refresh_item_coords()
    
    def _set_status(self, text, color=SUCCESS):
        self.status_label.configure(text=f"$ {text}", text_color=color)
    
    # ── 运行控制 ──
    def _toggle_run(self):
        if self.bot.running:
            self.bot.running = False
            self._set_status("已停止", TEXT_MUTED)
        else:
            self._start()
    
    def _sync_craft_options(self):
        try:
            per_item = int(self.per_item_limit_entry.get())
            total = int(self.total_limit_entry.get())
            if per_item < 0 or total < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("警告", "通货消耗上限必须是非负整数，0 为无限制。")
            return False
        self.bot.config.update(craft_mode=self.mode_combo.get(),
                               per_item_currency_limit=per_item, total_currency_limit=total)
        return True

    def _start(self):
        try:
            interval = float(self.interval_entry.get())
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("警告", "操作间隔必须是大于等于 0 的数字！")
            return
        if not self.bot.config.get("item_positions"):
            messagebox.showwarning("警告", "请至少添加一个物品坐标！")
            return
        
        self.bot.config["target_conditions"] = [g.copy() for g in self.logic_groups]
        self.bot.config["equipment_type"] = self.equip_var.get()
        self.bot.config["interval"] = interval
        if not self._sync_craft_options():
            return
        
        initial, cycle = CRAFT_MODES[self.bot.config["craft_mode"]]
        missing = [dict(CURRENCY_LIST)[k] for k in dict.fromkeys(initial + cycle)
                   if not self.bot.get_currency_positions(k)]
        if missing:
            messagebox.showwarning("警告", "请设置通货坐标：" + "、".join(missing))
            return
        self.bot.total_currency_used = 0
        self.bot.running = True
        self.bot.start_time = time.time()
        self.bot.currency_counts.clear()
        
        # 重置统计显示
        total = len(self.bot.config["item_positions"])
        self.stats_success_label.configure(text=f"0/{total}")
        self.stats_time_label.configure(text="00:00:00")
        
        self._set_status("运行中  ·  F3 停止", SUCCESS)
        
        threading.Thread(target=self._run_loop, daemon=True).start()
        threading.Thread(target=self._update_stats_loop, daemon=True).start()
    
    def _run_loop(self):
        total = len(self.bot.config["item_positions"])
        total_limit = self.bot.config.get("total_currency_limit", 0)
        success_count = 0
        
        for i, pos in enumerate(self.bot.config["item_positions"], 1):
            if not self.bot.running:
                break
            if total_limit and self.bot.total_currency_used >= total_limit:
                self._set_status(f"已达到总通货消耗上限 {total_limit}", WARNING)
                break
            self.app.after(0, lambda i=i, t=total: self.current_item_label.configure(text=f"物品 {i}/{t}"))
            self._set_status(f"正在处理  {i}/{total}", SUCCESS)
            try:
                success = self.bot.process_one_item(pos)
                if success:
                    success_count += 1
                    self.app.after(0, lambda s=success_count, t=total: 
                                   self.stats_success_label.configure(text=f"{s}/{t}"))
                    self.bot.beep()
                    self._set_status(f"✓ 物品 {i} 达标 — 切换下一个", SUCCESS)
            except Exception as ex:
                self._set_status(f"✗ 异常: {ex}", DANGER)
                self.bot.rand_sleep(0.5)
        stopped = not self.bot.running
        self.bot.running = False
        if total_limit and self.bot.total_currency_used >= total_limit:
            self._set_status(f"已达到总通货消耗上限 {total_limit}", WARNING)
        else:
            self._set_status("已停止" if stopped else "处理结束", TEXT_MUTED)
        self.bot.beep(1500, 800)
    
    def _update_stats_loop(self):
        while self.bot.running:
            counts = dict(self.bot.currency_counts)
            elapsed = int(time.time() - self.bot.start_time)
            self.app.after(0, self._apply_stats, counts, elapsed)
            time.sleep(0.5)

    def _apply_stats(self, counts, elapsed):
        for k, lbl in self.stat_labels.items():
            lbl.configure(text=str(counts.get(k, 0)))
        time_str = f"{elapsed//3600:02d}:{elapsed%3600//60:02d}:{elapsed%60:02d}"
        self.time_label.configure(text=time_str)
        self.stats_time_label.configure(text=time_str)

    def _reset_stats(self):
        self.bot.currency_counts.clear()
        for k, lbl in self.stat_labels.items():
            lbl.configure(text="0")
        self.stats_time_label.configure(text="00:00:00")
        total = len(self.bot.config.get("item_positions", []))
        self.stats_success_label.configure(text=f"0/{total}")
    
    def _save(self):
        self.bot.config["target_conditions"] = [g.copy() for g in self.logic_groups]
        try:
            self.bot.config["interval"] = float(self.interval_entry.get())
        except ValueError:
            pass
        if not self._sync_craft_options():
            return
        self.bot.save_config()
        self._set_status("配置已保存", SUCCESS)
        messagebox.showinfo("成功", "配置保存成功！")
    
    def _load(self):
        p = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON文件", "*.json")])
        if not p:
            return
        tmp = PoeOrbBotBase()
        tmp.config_file = p
        tmp.load_config()
        self.bot.config.update(tmp.config)
        
        self.logic_groups = self.bot.config.get("target_conditions", [])
        if not self.logic_groups:
            self.logic_groups = [{"equipment_type": "单手剑", "position": "前缀",
                                  "conditions": [], "logic": "or"}]
        self.selected_group_index = 0
        self._refresh_group_list()
        
        self.mode_combo.set(self.bot.config["craft_mode"])
        if "interval" in self.bot.config:
            self.interval_entry.delete(0, "end")
            self.interval_entry.insert(0, str(self.bot.config["interval"]))
        if "per_item_currency_limit" in self.bot.config:
            self.per_item_limit_entry.delete(0, "end")
            self.per_item_limit_entry.insert(0, str(self.bot.config["per_item_currency_limit"]))
        if "total_currency_limit" in self.bot.config:
            self.total_limit_entry.delete(0, "end")
            self.total_limit_entry.insert(0, str(self.bot.config["total_currency_limit"]))
        for k in self.currency_coord_frames:
            self._refresh_currency_coords(k)
        
        self._refresh_item_coords()
        self._set_status("配置已加载", SUCCESS)
        messagebox.showinfo("成功", "配置加载成功！")
    
    def _toggle_theme(self):
        """控件持有 (浅色, 深色) 配色，由 CTk 一次性切换外观。"""
        new_mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.theme_btn.configure(text="☀" if new_mode == "light" else "🌙")
    
    def _on_closing(self):
        self.bot.running = False
        for callback_id in (self._affix_refresh_after_id, self._affix_render_after_id):
            if callback_id is not None:
                self.app.after_cancel(callback_id)
        try:
            self.bot.config["target_conditions"] = [g.copy() for g in self.logic_groups]
            self.bot.save_config()
        except:
            pass
        self.app.destroy()
    
    def run(self):
        self.app.mainloop()


if __name__ == "__main__":
    MainApp().run()
