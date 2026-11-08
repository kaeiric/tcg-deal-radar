def calculate_landed_cost(item_price,shipping,tax_rate=0.0):
    return round((float(item_price)+float(shipping))*(1+float(tax_rate)),2)
def discount_percent(market_price,landed_cost):
    if not market_price or market_price<=0: return 0.0
    return round((float(market_price)-float(landed_cost))/float(market_price)*100,2)
