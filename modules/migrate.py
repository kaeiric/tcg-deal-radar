"""
Database migration script for Phase 1: Collection Management & Portfolios
Adds new tables while preserving all existing data and tables.
"""
import sqlite3
import os
from contextlib import contextmanager
from config import DB_PATH

# Migration version - increment for each migration
MIGRATION_VERSION = 1

MIGRATION_SQL = """
-- ============================================================
-- MIGRATION v1: Collection Management & Portfolios
-- ============================================================

-- Portfolios table
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Collections table (main collection tracking with full details)
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    -- Card identification
    game TEXT NOT NULL,                    -- 'Pokemon' or 'One Piece'
    card_name TEXT NOT NULL,
    set_name TEXT DEFAULT '',
    card_number TEXT DEFAULT '',
    rarity TEXT DEFAULT '',
    language TEXT NOT NULL,                -- 'English', 'Japanese', 'Chinese', etc.
    variant TEXT DEFAULT '',               -- 'Normal', 'Holo', 'Reverse Holo', 'Alternate Art', 'Parallel', 'Manga', etc.
    -- Condition & Grading
    condition TEXT NOT NULL DEFAULT 'Near Mint',  -- 'Near Mint', 'Lightly Played', 'Moderately Played', 'Heavily Played', 'Damaged'
    grading_company TEXT DEFAULT '',       -- 'PSA', 'BGS', 'CGC', 'SGC', etc.
    grade TEXT DEFAULT '',                 -- e.g., '10', '9.5', '9', etc.
    is_graded INTEGER DEFAULT 0,           -- 0 = raw, 1 = graded
    is_sealed INTEGER DEFAULT 0,           -- 0 = single card, 1 = sealed product
    sealed_type TEXT DEFAULT '',           -- 'Booster Box', 'Elite Trainer Box', 'Booster Pack', 'Collection Box', 'Other'
    -- Quantity & Cost Basis
    quantity INTEGER NOT NULL DEFAULT 1,
    purchase_price REAL DEFAULT 0,         -- Price per unit at purchase
    purchase_date TEXT DEFAULT '',         -- ISO date string
    purchase_currency TEXT DEFAULT 'USD',
    -- Images & Notes
    image_url TEXT DEFAULT '',             -- Reference URL to card image
    notes TEXT DEFAULT '',
    -- Tracking
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_collections_portfolio ON collections(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_collections_game_name ON collections(game, card_name);
CREATE INDEX IF NOT EXISTS idx_collections_set_number ON collections(set_name, card_number);
CREATE INDEX IF NOT EXISTS idx_collections_graded ON collections(is_graded, grading_company, grade);
CREATE INDEX IF NOT EXISTS idx_collections_sealed ON collections(is_sealed, sealed_type);

-- Price History table (historical snapshots)
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    source TEXT NOT NULL,                  -- 'eBay', 'TCGplayer', 'Manual', 'PokéTCG', etc.
    condition TEXT DEFAULT 'Near Mint',
    language TEXT DEFAULT '',
    variant TEXT DEFAULT '',
    grading_company TEXT DEFAULT '',
    grade TEXT DEFAULT '',
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_collection ON price_history(collection_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded ON price_history(recorded_at);

-- Watchlist table (target price alerts, separate from collection)
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER,                  -- Optional: associate with portfolio
    -- Card identification (same fields as collections for matching)
    game TEXT NOT NULL,
    card_name TEXT NOT NULL,
    set_name TEXT DEFAULT '',
    card_number TEXT DEFAULT '',
    rarity TEXT DEFAULT '',
    language TEXT NOT NULL,
    variant TEXT DEFAULT '',
    condition TEXT DEFAULT 'Near Mint',
    grading_company TEXT DEFAULT '',
    grade TEXT DEFAULT '',
    is_sealed INTEGER DEFAULT 0,
    sealed_type TEXT DEFAULT '',
    -- Alert settings
    target_price REAL NOT NULL,
    alert_on_drop INTEGER DEFAULT 1,       -- Alert when price drops to/below target
    alert_on_rise INTEGER DEFAULT 0,       -- Alert when price rises significantly
    significant_change_pct REAL DEFAULT 20.0,  -- Percentage for significant change alerts
    -- Status
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(portfolio_id) REFERENCES portfolios(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(active);
CREATE INDEX IF NOT EXISTS idx_watchlist_game_name ON watchlist(game, card_name);

-- Trades table (trade history)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,              -- ISO date string
    -- Items given
    items_given TEXT NOT NULL,             -- JSON array of {collection_id, quantity, value_at_trade}
    -- Items received
    items_received TEXT NOT NULL,          -- JSON array of {collection_id, quantity, value_at_trade}
    -- Cash adjustment
    cash_given REAL DEFAULT 0,             -- Cash paid out
    cash_received REAL DEFAULT 0,          -- Cash received
    cash_currency TEXT DEFAULT 'USD',
    -- Evaluation
    value_given REAL NOT NULL,             -- Total market value given
    value_received REAL NOT NULL,          -- Total market value received
    value_difference REAL NOT NULL,        -- value_received - value_given + cash_received - cash_given
    pct_difference REAL NOT NULL,          -- Percentage difference
    evaluation TEXT NOT NULL,              -- 'Favorable to Me', 'Fair Trade', 'Unfavorable to Me'
    -- Notes
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sets catalog table (for set completion tracking)
CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL,                    -- 'Pokemon' or 'One Piece'
    set_code TEXT NOT NULL,                -- e.g., 'sv1', 'sv2', 'OP01', 'OP02'
    set_name TEXT NOT NULL,                -- e.g., 'Scarlet & Violet', 'Romance Dawn'
    release_date TEXT DEFAULT '',          -- ISO date string
    total_cards INTEGER DEFAULT 0,         -- Total cards in set (including secret rares)
    total_secret INTEGER DEFAULT 0,        -- Number of secret rares
    series TEXT DEFAULT '',                -- e.g., 'Scarlet & Violet', 'Sword & Shield', 'OP Series'
    UNIQUE(game, set_code)
);

-- Set cards table (cards belonging to each set)
CREATE TABLE IF NOT EXISTS set_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id INTEGER NOT NULL,
    card_number TEXT NOT NULL,             -- e.g., '001/198', '119', 'SV01'
    card_name TEXT NOT NULL,
    rarity TEXT DEFAULT '',                -- 'Common', 'Uncommon', 'Rare', 'Double Rare', 'Illustration Rare', 'Special Illustration Rare', 'Hyper Rare', 'Ultra Rare', 'Secret Rare', etc.
    variant TEXT DEFAULT '',               -- 'Normal', 'Holo', 'Reverse Holo', 'Alternate Art', etc.
    language TEXT DEFAULT 'English',       -- Default language for this catalog entry
    -- Market data (optional, for cost-to-complete estimates)
    market_price REAL DEFAULT 0,
    market_price_currency TEXT DEFAULT 'USD',
    market_price_updated TEXT DEFAULT '',
    FOREIGN KEY(set_id) REFERENCES sets(id) ON DELETE CASCADE,
    UNIQUE(set_id, card_number, variant, language)
);

CREATE INDEX IF NOT EXISTS idx_set_cards_set ON set_cards(set_id);
CREATE INDEX IF NOT EXISTS idx_set_cards_name ON set_cards(card_name);

-- Insert default portfolio if none exists
INSERT OR IGNORE INTO portfolios (id, name, description) VALUES (1, 'Main Collection', 'Default portfolio for all cards');
"""

@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def run_migration():
    """Run the Phase 1 migration."""
    print(f"Running migration v{MIGRATION_VERSION}...")

    with connect() as conn:
        # Check if migration already applied
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolios'")
        if cursor.fetchone():
            print("Migration v1 already applied (portfolios table exists). Skipping.")
            return True

        # Execute migration
        try:
            conn.executescript(MIGRATION_SQL)
            print("Migration v1 applied successfully!")

            # Verify new tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Tables in database: {', '.join(tables)}")

            return True
        except Exception as e:
            print(f"Migration failed: {e}")
            return False

def verify_migration():
    """Verify migration was applied correctly."""
    with connect() as conn:
        cursor = conn.cursor()
        expected_tables = ['portfolios', 'collections', 'price_history', 'watchlist', 'trades', 'sets', 'set_cards']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}

        missing = [t for t in expected_tables if t not in existing]
        if missing:
            print(f"Missing tables: {missing}")
            return False

        print("All Phase 1 tables present.")
        return True

if __name__ == "__main__":
    run_migration()
    verify_migration()