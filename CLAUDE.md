# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PathofAutoV2 是一套用于《流放之路》（Path of Exile）游戏经济自动化的 Python 脚本集合。各模块独立运行，无构建系统或测试框架。所有机器人均为 **Windows 专用**。

## 运行脚本

```bash
# 从 poe.ninja 抓取实时价格
python essence/ninja.py

# 运行精华利润蒙特卡洛模拟
python essence/main.py

# 运行精华转换期望值计算器
python essence/emulator.py

# 运行宝珠制作机器人（完整版，7种宝珠）
python poborbbot/POBorbBot.py

# 运行宝珠制作机器人（简化版，3种宝珠）
python poborbbot/POBorbBotV2.py

# 运行法斯特交易所价格读取器
python faust/faust_v2.py
```

## 依赖库（需手动安装）

```
pyautogui pyperclip keyboard paddleocr opencv-python numpy matplotlib requests
```

`winsound` 和 `tkinter` 为 Python 内置模块。

## 架构要点

**四个独立子模块：**

- `essence/` — 精华货币分析：`ninja.py` 抓取 poe.ninja 价格写入 `price.json`；`main.py` 做蒙特卡洛模拟；`emulator.py` 做期望值计算，读取 `essence_tencent.json`
- `faust/` — 交易所价格读取机器人，使用 PaddleOCR（中文模型）识别游戏内 UI 文字，hardcode 了 1920x1080 屏幕坐标
- `poborbbot/` — 宝珠制作自动化，含 Tkinter GUI；`POBorbBot.py`（7种宝珠）和 `POBorbBotV2.py`（3种宝珠）共用 `poe_orb_config.json` 配置
- `scarabBot/` — 圣甲虫转换机器人（未完成），依赖不存在的 `executor` 模块，**无法运行**

**关键模式：**

- 屏幕坐标为绝对像素值，用户通过 GUI 中按 `=` 键捕获坐标
- 宝珠机器人用 `Ctrl+Alt+C` 将物品数据复制到剪贴板后解析词缀，无需 OCR
- 制作循环为显式状态机 + 随机延迟（模拟人类操作）
- 热键 `F3` 启动/停止宝珠机器人
- 配置持久化到 `poe_orb_config.json`

**`faust/faust_v2.py` 的 `FaustMaster` 类**使用中文 PaddleOCR 模型，调试图像保存至 `debug/` 文件夹。`read_price()` 识别形如 `1:5` 的价格比例。

## 注意事项

- `scarabBot/PoeScarabBot.py` 因 `from executor import Executor` 缺失依赖，运行时会抛 `ImportError`
- `price.json` 当前为空，需先运行 `essence/ninja.py` 填充
- `faust_v2.py` 中的屏幕坐标针对中文版游戏客户端布局（腾讯服）
