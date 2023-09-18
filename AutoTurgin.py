import executor


positions = executor.get_position_args()
grid_positions = executor.get_grid_positions(positions['turgin_start'], positions['turgin_end'], 12, 2)
needs = []
with open('db/turgin_need.txt', 'r') as fp:
    for line in fp:
        ll = line.strip()
        needs.append(ll)
            
    
def main(times=1):
    def bargin():
        executor.safe_click()
        last_ptice = 0
        while True:
            executor.safe_move_to(positions['turgin_price'])
            executor.safe_double_click(button='left')
            info = executor.safe_get_info()
            if len(info) == 0:
                break
            now_price = int(info.strip())
            if abs(now_price-last_ptice) > 10:
                price = (last_ptice+now_price) / 2.1
                last_ptice = price
            else:
                price = now_price - 2
            executor.safe_type(price)
            executor.safe_move_to(positions['turgin_confirm'])
            executor.safe_click(button='left')
    def deal_one_page():
        for pos in positions:
            executor.safe_move_to(pos)
            info = executor.safe_get_info()
            if len(info) == 0:
                return
            if executor.safe_check_target(info, needs):
                bargin()
                
    subs = [30]*(times//30) + [times%30]
    for sub in subs:
        for ii in range(sub):
            deal_one_page()
            executor.safe_move_to(positions['turgin_flush'])
            executor.safe_click(button='left')
                
    


if '__name__' == '__main__':
    executor.open_poe()
