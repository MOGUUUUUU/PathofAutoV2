import random
from dataclasses import dataclass
from typing import List, Tuple


GOLD_PER_ROLL = 5000

@dataclass
class Essence:
    name: str
    price: float

class EssenceList:
    def __init__(self, essences: List[Essence] = None) -> None:
        self.essences = essences or []
    
    def simulate_rolls(self, tries: int = 5000) -> Tuple[float, float]:
        if not self.essences:
            raise 
        
        lowest_price = min(e.price for e in self.essences)
        available_essences = [e for e in self.essences if e.price > lowest_price]
        
        
        total_profit = 0.0
        total_gold_cost = 0.0
        
        selected_essences = random.choices(available_essences, k=tries)
        
        for essence in selected_essences:
            total_gold_cost += GOLD_PER_ROLL
            total_profit += essence.price - lowest_price
        
        profit_per_10k = 10000 * total_profit / total_gold_cost
        
        print(f'profit:{total_profit}, every 10k gold earn:{profit_per_10k:.2f}')
        
        return total_profit, total_gold_cost
    
    def simulate_until_above_avg(self, max_tries: int = 10000) -> None:

        if not self.essences:
            return
        
        avg_price = sum(e.price for e in self.essences) / len(self.essences)
        lowest_price = min(e.price for e in self.essences)
        

        tries = 0
        while tries < max_tries:
            tries += 1
            selected = random.choice([e for e in self.essences if e.price > lowest_price])
            if selected.price > avg_price:
                print(f"经过 {tries} 次抽取，获得高于平均价的精华: {selected.name}")
                return
        print(f'income:{total_profit}, every 10k gold earn:{profit_per_10k:.2f}')
        
        
if __name__ == '__main__':
    essence_list = EssenceList([
        Essence("a", 1000),
        Essence("b", 3000),
        Essence("c", 8000),
        Essence("d", 15000),
    ])
    
    essence_list.simulate_rolls(tries=5000)