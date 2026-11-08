import sqlite3, os
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
 id INTEGER PRIMARY KEY AUTOINCREMENT, game TEXT NOT NULL, card_name TEXT NOT NULL,
 set_name TEXT DEFAULT '', card_number TEXT DEFAULT '', rarity TEXT DEFAULT '',
 language TEXT NOT NULL, condition_target TEXT DEFAULT 'Near Mint',
 active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(game,card_name,set_name,card_number,language));
CREATE TABLE IF NOT EXISTS price_references (
 id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER NOT NULL, source TEXT NOT NULL,
 market_price REAL NOT NULL, currency TEXT DEFAULT 'USD', condition TEXT DEFAULT 'Near Mint',
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(card_id) REFERENCES cards(id));
CREATE TABLE IF NOT EXISTS ebay_listings (
 id INTEGER PRIMARY KEY AUTOINCREMENT, ebay_item_id TEXT NOT NULL UNIQUE, card_id INTEGER,
 title TEXT NOT NULL, item_price REAL NOT NULL, shipping REAL DEFAULT 0, currency TEXT DEFAULT 'USD',
 item_url TEXT NOT NULL, condition_name TEXT DEFAULT '', seller_username TEXT DEFAULT '',
 seller_feedback_pct REAL, listing_date TEXT DEFAULT '', match_confidence REAL DEFAULT 0,
 landed_cost REAL, discount_pct REAL, first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(card_id) REFERENCES cards(id));
CREATE TABLE IF NOT EXISTS alerts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, ebay_item_id TEXT NOT NULL UNIQUE,
 sent_at TEXT DEFAULT CURRENT_TIMESTAMP, discount_pct REAL NOT NULL);
"""

@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn=sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally: conn.close()

def init_db():
    with connect() as c: c.executescript(SCHEMA)

def get_cards(active_only=False):
    with connect() as c:
        q="SELECT * FROM cards" + (" WHERE active=1" if active_only else "") + " ORDER BY game,card_name"
        return [dict(x) for x in c.execute(q).fetchall()]

def add_card(d):
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO cards(game,card_name,set_name,card_number,rarity,language,condition_target) VALUES(?,?,?,?,?,?,?)",
        (d["game"],d["card_name"],d.get("set_name",""),d.get("card_number",""),d.get("rarity",""),d["language"],d.get("condition_target","Near Mint")))

def latest_prices():
    with connect() as c:
        rows=c.execute("""SELECT p.* FROM price_references p JOIN
        (SELECT card_id,MAX(updated_at) latest FROM price_references GROUP BY card_id) x
        ON p.card_id=x.card_id AND p.updated_at=x.latest""").fetchall()
        return {r["card_id"]:dict(r) for r in rows}

def save_price(card_id,price,source="CSV",condition="Near Mint"):
    with connect() as c:
        c.execute("INSERT INTO price_references(card_id,source,market_price,condition) VALUES(?,?,?,?)",
                  (card_id,source,float(price),condition))

def save_listing(i,card_id,confidence,landed,discount):
    with connect() as c:
        c.execute("""INSERT OR IGNORE INTO ebay_listings
        (ebay_item_id,card_id,title,item_price,shipping,currency,item_url,condition_name,
         seller_username,seller_feedback_pct,listing_date,match_confidence,landed_cost,discount_pct)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (i["item_id"],card_id,i["title"],i["price"],i["shipping"],i["currency"],i["url"],
         i["condition"],i["seller"],i["seller_feedback"],i["listing_date"],confidence,landed,discount))

def was_alerted(item_id):
    with connect() as c: return c.execute("SELECT 1 FROM alerts WHERE ebay_item_id=?",(item_id,)).fetchone() is not None

def record_alert(item_id,discount):
    with connect() as c: c.execute("INSERT OR IGNORE INTO alerts(ebay_item_id,discount_pct) VALUES(?,?)",(item_id,discount))

def get_listings(limit=300):
    with connect() as c:
        rows=c.execute("""SELECT l.*,c.game,c.card_name,c.set_name,c.card_number,c.language
        FROM ebay_listings l LEFT JOIN cards c ON c.id=l.card_id ORDER BY l.first_seen_at DESC LIMIT ?""",(limit,)).fetchall()
        return [dict(r) for r in rows]

def get_alert_count():
    with connect() as c: return c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
