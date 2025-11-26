import requests
import json
import pickle

class PoeNinjaEssenceAPI:
    def __init__(self, league="Settlers"):
        self.base_url = "https://poe.ninja/api/data/itemoverview"
        self.league = league
    
    def get_all_essence_prices(self):
        """获取所有精华的价格"""
        params = {
            "league": self.league,
            "type": "Essence"  # 关键参数：Essence
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            essences = []
            
            for item in data.get("lines", []):
                essence_info = {
                    "id": item["id"],
                    "name": item["name"],
                    "icon": item["icon"],
                    "chaos_value": item["chaosValue"],
                    "divine_value": item.get("divineValue", 0),
                    "item_count": item.get("count", 0),
                    "level": item.get("level", 0),
                    "is_corrupted": item.get("corrupted", False)
                }
                essences.append(essence_info)
            
            return essences
            
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return []

# 使用示例
api = PoeNinjaEssenceAPI()
essences = api.get_all_essence_prices()

with open('essence.json', "w", encoding="utf-8") as f:
    json.dump(essences, f, ensure_ascii=False, indent=4)
# 按价格排序并显示
sorted_essences = sorted(essences, key=lambda x: x['chaos_value'], reverse=True)
# for essence in sorted_essences[:10]:
#     print(f"{essence['name']}: {essence['chaos_value']} chaos")
for essence in sorted_essences:
    if 'Deafening' not in essence['name']:
        continue
    print(f"{essence['name']}: {essence['chaos_value']} chaos")