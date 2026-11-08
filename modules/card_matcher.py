import re
from difflib import SequenceMatcher

def norm(s): return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()

def match_score(card,title):
    t=norm(title); n=norm(card["card_name"])
    if not n or (n not in t and SequenceMatcher(None,n,t).ratio()<0.78): return 0.0
    score=0.55
    if card.get("set_name") and norm(card["set_name"]) in t: score+=0.20
    if card.get("card_number") and norm(card["card_number"]) in t: score+=0.20
    lang=card["language"].lower()
    if lang=="japanese" and any(x in t for x in ["japanese"," jp "," jpn"]): score+=0.05
    elif lang=="english" and any(x in t for x in ["english"," eng "]): score+=0.05
    return min(score,1.0)

def likely_excluded(title):
    t=(title or "").lower()
    return any(x in t for x in ["proxy","custom","orica","digital","code card","empty box","playmat","sleeve","booster pack","lot of"])

def language_compatible(card,title):
    t=" "+(title or "").lower()+" "
    if card["language"].lower()=="japanese":
        return any(x in t for x in ["japanese"," jp "," jpn "])
    return not any(x in t for x in [" japanese "," jpn "," jp "])
