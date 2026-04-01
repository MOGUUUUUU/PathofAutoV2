# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PathofAutoV2 是一套用于《流放之路》（Path of Exile）游戏经济自动化的 Python 脚本集合。各模块独立运行，无构建系统或测试框架。所有机器人均为 **Windows 专用**。

## 运行脚本

```bash
# Gwennen 远征商人自动购买机器人
python expedition/gwennen.py

# 宝珠制作机器人（合并版，双 Tab 选择简化/完整模式）
python poborbbot/POBorbBotMerged.py

# 从 poe.ninja 抓取实时价格
python essence/ninja.py

# 运行精华利润蒙特卡洛模拟
python essence/main.py

# 运行精华转换期望值计算器
python essence/emulator.py

# 运行法斯特交易所价格读取器
python faust/faust_v2.py
```

## 依赖库（需手动安装）

```
pyautogui pyperclip keyboard paddleocr opencv-python numpy matplotlib requests
```

`winsound` 和 `tkinter` 为 Python 内置模块。

## 架构要点

### 各子模块

- **`expedition/`** — Gwennen 远征商人自动购买。见下方详细说明。
- **`poborbbot/`** — 宝珠制作自动化。`POBorbBotMerged.py` 为合并版（推荐使用），`POBorbBot.py`（7种宝珠）和 `POBorbBotV2.py`（3种宝珠）为旧版，共用 `poe_orb_config.json` 配置。
- **`faust/`** — 交易所价格读取机器人，使用 PaddleOCR（中文模型）识别游戏内 UI 文字，hardcode 了 1920x1080 屏幕坐标，腾讯服专用。
- **`essence/`** — 精华货币分析：`ninja.py` 抓取 poe.ninja 价格写入 `price.json`；`main.py` 做蒙特卡洛模拟；`emulator.py` 做期望值计算，读取 `essence_tencent.json`。
- **`scarabBot/`** — 圣甲虫转换机器人（未完成），依赖不存在的 `executor` 模块，**无法运行**。

### 通用模式

- 屏幕坐标均为绝对像素值，用户通过 GUI 中按 `=` 键捕获
- 物品信息读取统一用 `Ctrl+Alt+C` 复制到剪贴板后解析
- 宝珠/购买机器人均用 `F3` 热键启停
- 随机延迟（`random.random()` jitter）模拟人类操作
- 配置持久化为 JSON 文件，随脚本同目录存放

---

## expedition/gwennen.py

### 类结构

- `GwennenBot` — 纯逻辑层，不依赖 tkinter
- `GwennenGUI` — Tkinter 界面，持有 `GwennenBot` 实例

### 主循环逻辑

```
遍历商店所有格子（m×n，左上/右下两点等分计算；m/n 由 GUI 可配置，默认 12×12）
  └─ Ctrl+Alt+C 读取物品信息
      └─ 匹配购买关键词？
          ├─ 是 → Ctrl+左键购买 → buy_count++
          │       └─ 再次读取同格：物品还在 → 货币不足，停止
          │       └─ buy_count >= check_interval（GUI 可配置）→ 清理背包
          └─ 否 → 跳过
一页遍历完 → 点刷新按钮 → 等待 REFRESH_DELAY(1秒) → 继续
```

### 清背包逻辑

遍历背包 12×5 每一格，读取物品信息，不匹配**保留关键词**的物品执行 `/destroy` 命令删除。购买关键词与保留关键词是两套独立的列表。

### 坐标设置

需捕获 5 个坐标：商店左上角、商店右下角、背包左上角、背包右下角、刷新按钮。`gwennen.py` 启动时会自动尝试从 `expedition/gwennen.json` 加载配置，也可在 GUI 里手动保存/加载。

### Gwennen GUI 细节

- 支持两套关键词列表（购买关键词 / 背包保留关键词），均支持添加、删除、清空
- 关键词列表带滚动条，适合较长列表
- 商店行列（shop_rows/shop_cols）可在 GUI 中设置并保存到配置
- `F3` 启停，`=` 捕获当前选中的坐标类型

### 类结构

```
PoeOrbBotBase          # 公共基类（配置读写、use_orb、check_item）
├── PoeOrbBotSimple    # 简化版状态机（3种宝珠）
└── PoeOrbBotFull      # 完整版状态机（7种宝珠）

BotTabPanel            # 通用 Tab 面板，接受任意 bot 实例和 orb_names 字典
MainApp                # Notebook 双 Tab 主窗口
```

### 状态机

**简化版**：`蜕变 → 增幅 ⟷ 改造`（目标：匹配1个词缀）

**完整版**：`蜕变 → 改造循环（1词缀）→ 增幅（2词缀）→ 富豪（3词缀）→ 崇高（4词缀）→ 成功 / 剥离（退到3词缀重试）/ 重铸（归零重来）`

### Tab 切换行为

切换 Tab 时自动停止另一个 Tab 正在运行的 bot，`F3` 和 `=` 始终作用于当前激活 Tab。

## 注意事项

- `scarabBot/PoeScarabBot.py` 因 `from executor import Executor` 缺失依赖，运行时会抛 `ImportError`
- `price.json` 当前为空，需先运行 `essence/ninja.py` 填充
- `faust_v2.py` 中的屏幕坐标针对中文版游戏客户端布局（腾讯服）
- `POBorbBot.py` 和 `POBorbBotV2.py` 为旧版，新开发请基于 `POBorbBotMerged.py`
