import base64,time,requests
from config import EBAY_CLIENT_ID,EBAY_CLIENT_SECRET,EBAY_MARKETPLACE_ID,MAX_RESULTS_PER_QUERY
TOKEN_URL="https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL="https://api.ebay.com/buy/browse/v1/item_summary/search"
_cache={"token":None,"expires":0}

def get_app_token():
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise RuntimeError("Add eBay Client ID and Client Secret to your .env file.")
    if _cache["token"] and time.time() < _cache["expires"]-60: return _cache["token"]
    auth=base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    r=requests.post(TOKEN_URL,headers={"Authorization":f"Basic {auth}","Content-Type":"application/x-www-form-urlencoded"},
        data={"grant_type":"client_credentials","scope":"https://api.ebay.com/oauth/api_scope"},timeout=30)
    r.raise_for_status(); data=r.json()
    _cache["token"]=data["access_token"]; _cache["expires"]=time.time()+int(data.get("expires_in",7200))
    return _cache["token"]

def build_query(card):
    parts=[card["card_name"]]
    if card.get("set_name"): parts.append(card["set_name"])
    if card.get("card_number"): parts.append(card["card_number"])
    parts.append("Japanese" if card["language"].lower()=="japanese" else "English")
    return " ".join(parts)

def normalize_item(raw):
    price=raw.get("price") or {}; ships=raw.get("shippingOptions") or []
    shipping=0.0
    if ships:
        val=(ships[0].get("shippingCost") or {}).get("value")
        if val is not None: shipping=float(val)
    seller=raw.get("seller") or {}
    try: feedback=float(seller["feedbackPercentage"]) if seller.get("feedbackPercentage") is not None else None
    except (TypeError,ValueError): feedback=None
    return {"item_id":raw.get("itemId",""),"title":raw.get("title",""),
        "price":float(price.get("value",0)),"currency":price.get("currency","USD"),
        "shipping":shipping,"url":raw.get("itemWebUrl",""),"condition":raw.get("condition",""),
        "seller":seller.get("username",""),"seller_feedback":feedback,
        "listing_date":raw.get("itemCreationDate","")}

def search_ebay(card):
    headers={"Authorization":f"Bearer {get_app_token()}","X-EBAY-C-MARKETPLACE-ID":EBAY_MARKETPLACE_ID}
    params={"q":build_query(card),"limit":MAX_RESULTS_PER_QUERY,"sort":"newlyListed"}
    r=requests.get(SEARCH_URL,params=params,headers=headers,timeout=35)
    r.raise_for_status()
    return [normalize_item(x) for x in r.json().get("itemSummaries",[])]
