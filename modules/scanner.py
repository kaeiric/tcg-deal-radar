from config import DEFAULT_TAX_RATE
from modules.database import get_cards,latest_prices,save_listing,was_alerted,record_alert
from modules.ebay_scanner import search_ebay
from modules.card_matcher import match_score,likely_excluded,language_compatible
from modules.price_engine import calculate_landed_cost,discount_percent
from modules.notification import send_ntfy

def run_scan(threshold_pct=20.0,tax_rate=DEFAULT_TAX_RATE,notify=True):
    stats={"cards_scanned":0,"items_seen":0,"new_listings":0,"alerts_sent":0,"errors":[]}
    prices=latest_prices()
    for card in get_cards(active_only=True):
        stats["cards_scanned"]+=1
        try:
            for item in search_ebay(card):
                stats["items_seen"]+=1
                if not item["item_id"] or not item["url"] or likely_excluded(item["title"]): continue
                if not language_compatible(card,item["title"]): continue
                confidence=match_score(card,item["title"])
                if confidence<0.75: continue
                ref=prices.get(card["id"])
                if not ref: continue
                landed=calculate_landed_cost(item["price"],item["shipping"],tax_rate)
                discount=discount_percent(ref["market_price"],landed)
                save_listing(item,card["id"],confidence,landed,discount)
                stats["new_listings"]+=1
                if discount>=threshold_pct and not was_alerted(item["item_id"]):
                    msg=(f'{card["card_name"]} ({card["game"]}, {card["language"]})\n'
                         f'eBay: ${item["price"]:.2f} + ${item["shipping"]:.2f} shipping\n'
                         f'Estimated total: ${landed:.2f}\n'
                         f'{ref["source"]} reference: ${ref["market_price"]:.2f}\n'
                         f'Discount: {discount:.1f}%\n{item["title"]}')
                    if notify: send_ntfy("TCG Deal Radar: potential deal",msg,item["url"])
                    record_alert(item["item_id"],discount); stats["alerts_sent"]+=1
        except Exception as e: stats["errors"].append(f'{card["card_name"]} [{card["language"]}]: {e}')
    return stats
