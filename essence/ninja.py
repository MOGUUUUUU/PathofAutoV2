import requests
import json

class PoeNinjaAPI:
    def __init__(self, league="Settlers"):
        self.base_url = "https://poe.ninja/api/data/itemoverview"
        self.league = league
        # 只抓：精华、化石、迷雾宝珠
        self.item_categories = {
            "essence": "Essence",
            "fossil": "Fossil",
            "delirium_orb": "DeliriumOrb"
        }

    def fetch(self, item_type):
        params = {"league": self.league, "type": item_type}
        try:
            r = requests.get(self.base_url, params=params, timeout=10)
            r.raise_for_status()
            lines = r.json().get("lines", [])
            items = []
            for x in lines:
                items.append({
                    "name": x["name"],
                    "chaos_value": x["chaosValue"],
                    "category": item_type
                })
            return items
        except Exception as e:
            print(f"抓取失败 {item_type}: {e}")
            return []

    def run(self):
        all_items = []
        for key, typ in self.item_categories.items():
            data = self.fetch(typ)
            all_items.extend(data)
            print(f"✅ {typ}：{len(data)} 个")

        with open("price.json", "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)
        print(f"\n全部保存到 price.json，总计 {len(all_items)} 个物品")

if __name__ == "__main__":
    PoeNinjaAPI(league="Settlers").run()