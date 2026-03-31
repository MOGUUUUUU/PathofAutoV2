import numpy as np
import os
import json
import matplotlib.pyplot as plt
from dataclasses import dataclass

CONVERT_CHAOS_COST = 1/38*30
CONVERT_GOLD_COST = 1/8*30
CHAOS_GOLD = 15
ESSENCE_GOLDS = 75

@dataclass
class ConvertItem:
    name: str
    value: float
    gold: float
    
class ConvertTool:
    def __init__(self, items: list[ConvertItem]) -> None:
        self.items = sorted(items, key=lambda d:d.value)
        for item in self.items:
            print(item)
        
        self.cheapest_item = None
        for item in self.items:
            if not self.cheapest_item or item.value < self.cheapest_item.value:
                self.cheapest_item = item
    
    def calculate_success_set(
        self,
        item: ConvertItem,
        threshold: float
    ):
        optional_items = [p for p in self.items if p.name != item.name]
        success_prices = [p for p in optional_items if p.value >= threshold]
        return success_prices, len(success_prices)

    def calculate_expected_k_exact(
        self,
        initial_item: ConvertItem,
        threshold: float
    ) -> float:
        n = len(self.items)
        # 首次转换的成功/失败信息
        success_prices1, f1 = self.calculate_success_set(initial_item, threshold)
        q1 = f1 / (n-1)  # 首次成功概率
        if q1 == 1:
            return 1.0  # 必然成功，转换1次
        if q1 == 0:
            return float('inf')  # 无法成功
        
        # 失败集合：可选集合中 < 阈值的石头
        optional_items = [p for p in self.items if p.name != initial_item.name]
        fail_items = [p for p in optional_items if p.value < threshold]
        m = len(fail_items)  # 失败集合大小
        if m == 0:
            return 1.0
        
        q_fail = []
        for s_fail in fail_items:
            _, f_fail = self.calculate_success_set(s_fail, threshold)
            q_fail.append(f_fail / (n-1))
        
        # 失败后平均成功概率
        avg_q_fail = np.mean(q_fail)
        # 总期望转换次数：解方程 E[k] = 1 + (1-q1)*E[k|fail]，其中 E[k|fail] = 1 + (1-avg_q_fail)*E[k|fail]
        E_k_fail = 1 / avg_q_fail if avg_q_fail != 0 else float('inf')
        E_k = 1 + (1 - q1) * E_k_fail
        return E_k

    def calculate_expected_profit(
        self,
        threshold: float,
        mode: str = "exact"  # "exact" 精确模式，"approx" 近似模式
    ):
        
        n = len(self.items)
        if n <= 1:
            return -float('inf')
        
        cheapest = self.cheapest_item
        # 计算首次转换的成功集合和数量
        success_prices1, f1 = self.calculate_success_set(cheapest, threshold)
        if f1 == 0:
            return -float('inf')  # 无成功可能
        
        # 期望卖出价
        E_X = sum([p.value for p in success_prices1]) / f1
        
        # 期望转换次数
        if mode == "approx":
            E_k = (n-1) / f1  # 近似模式
        else:
            E_k = self.calculate_expected_k_exact(cheapest, threshold)  # 精确模式
        
        E_pi_net = E_X - cheapest.value - CONVERT_CHAOS_COST * E_k
        gold_cost = E_k * CONVERT_GOLD_COST + E_pi_net * CHAOS_GOLD + cheapest.gold
        return E_pi_net, E_k, gold_cost



# ------------------- 示例运行 -------------------
if __name__ == "__main__":
    essences = None
    with open('essence_tencent.json', "r", encoding="utf-8") as f:
        essences = json.load(f)
    
    items = []
    for essence in essences:
        # if 'Deafening' not in essence['name']:
        #     continue
        items.append(ConvertItem(essence['name'], essence['chaos_value'], ESSENCE_GOLDS))
    probably_threshold = [e.value for e in items]
    probably_threshold.sort()
    tool = ConvertTool(items)
    mode = "exact"  # 可选 "exact" 或 "approx"
    for threshold in probably_threshold:
        net_profit, tries, gold_cost = tool.calculate_expected_profit(threshold)
        print(threshold, f'{net_profit:.2f}, {tries:.2f},{gold_cost:.2f}, {10000/gold_cost:.2f}')