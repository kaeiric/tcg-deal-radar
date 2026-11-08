"""
Portfolio management module for TCG Deal Radar.
Handles portfolio CRUD operations and portfolio-level analytics.
"""
import json
from contextlib import contextmanager
import sqlite3
from config import DB_PATH


@contextmanager
def connect():
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ============================================================
# Portfolio CRUD
# ============================================================

def create_portfolio(name: str, description: str = "") -> int:
    """Create a new portfolio. Returns portfolio ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO portfolios (name, description) VALUES (?, ?)",
            (name.strip(), description.strip())
        )
        return cursor.lastrowid


def get_portfolios() -> list[dict]:
    """Get all portfolios with card counts and total values."""
    with connect() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT p.*,
                   COUNT(c.id) as card_count,
                   SUM(c.quantity) as total_quantity,
                   COALESCE(SUM(c.quantity * c.purchase_price), 0) as total_cost,
                   COALESCE(SUM(
                       CASE
                           WHEN c.is_graded = 1 THEN c.quantity * c.purchase_price * 1.5  -- Placeholder for graded premium
                           WHEN c.is_sealed = 1 THEN c.quantity * c.purchase_price * 1.2  -- Placeholder for sealed premium
                           ELSE c.quantity * c.purchase_price
                       END
                   ), 0) as estimated_value
            FROM portfolios p
            LEFT JOIN collections c ON c.portfolio_id = p.id
            GROUP BY p.id
            ORDER BY p.created_at
        """).fetchall()
        return [dict(r) for r in rows]


def get_portfolio(portfolio_id: int) -> dict | None:
    """Get a single portfolio by ID."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        return dict(row) if row else None


def update_portfolio(portfolio_id: int, name: str = None, description: str = None) -> bool:
    """Update portfolio name and/or description."""
    with connect() as conn:
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(portfolio_id)
        cursor = conn.execute(f"UPDATE portfolios SET {', '.join(updates)} WHERE id = ?", params)
        return cursor.rowcount > 0


def delete_portfolio(portfolio_id: int, force: bool = False) -> tuple[bool, str]:
    """
    Delete a portfolio.
    If force=False and portfolio has cards, returns (False, error_message).
    If force=True, deletes portfolio and all its cards (CASCADE).
    """
    with connect() as conn:
        cursor = conn.cursor()
        # Check for cards
        card_count = cursor.execute("SELECT COUNT(*) FROM collections WHERE portfolio_id = ?", (portfolio_id,)).fetchone()[0]
        if card_count > 0 and not force:
            return False, f"Portfolio has {card_count} card(s). Use force=True to delete anyway."

        cursor.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
        return cursor.rowcount > 0, "Deleted successfully"


def get_portfolio_summary(portfolio_id: int) -> dict:
    """Get detailed portfolio summary with analytics."""
    with connect() as conn:
        cursor = conn.cursor()

        # Basic portfolio info
        portfolio = cursor.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if not portfolio:
            return {}
        portfolio = dict(portfolio)

        # Card stats
        stats = cursor.execute("""
            SELECT
                COUNT(*) as unique_cards,
                SUM(quantity) as total_quantity,
                SUM(quantity * purchase_price) as total_cost,
                COUNT(CASE WHEN is_graded = 1 THEN 1 END) as graded_count,
                COUNT(CASE WHEN is_sealed = 1 THEN 1 END) as sealed_count,
                COUNT(CASE WHEN game = 'Pokemon' THEN 1 END) as pokemon_count,
                COUNT(CASE WHEN game = 'One Piece' THEN 1 END) as onepiece_count
            FROM collections WHERE portfolio_id = ?
        """, (portfolio_id,)).fetchone()

        # Value by game
        by_game = cursor.execute("""
            SELECT game, COUNT(*) as count, SUM(quantity) as qty, SUM(quantity * purchase_price) as cost
            FROM collections WHERE portfolio_id = ? GROUP BY game
        """, (portfolio_id,)).fetchall()

        # Value by type (graded/raw/sealed)
        by_type = cursor.execute("""
            SELECT
                CASE
                    WHEN is_graded = 1 THEN 'Graded'
                    WHEN is_sealed = 1 THEN 'Sealed'
                    ELSE 'Raw'
                END as type,
                COUNT(*) as count, SUM(quantity) as qty, SUM(quantity * purchase_price) as cost
            FROM collections WHERE portfolio_id = ? GROUP BY type
        """, (portfolio_id,)).fetchall()

        # Top cards by purchase value
        top_cards = cursor.execute("""
            SELECT card_name, set_name, card_number, language, variant, condition,
                   grading_company, grade, quantity, purchase_price,
                   (quantity * purchase_price) as total_cost
            FROM collections WHERE portfolio_id = ?
            ORDER BY total_cost DESC LIMIT 10
        """, (portfolio_id,)).fetchall()

        return {
            "portfolio": portfolio,
            "stats": dict(stats) if stats else {},
            "by_game": [dict(r) for r in by_game],
            "by_type": [dict(r) for r in by_type],
            "top_cards": [dict(r) for r in top_cards]
        }


# ============================================================
# Card movement between portfolios
# ============================================================

def move_card(collection_id: int, target_portfolio_id: int) -> bool:
    """Move a card to another portfolio."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE collections SET portfolio_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_portfolio_id, collection_id)
        )
        return cursor.rowcount > 0


def copy_card(collection_id: int, target_portfolio_id: int) -> int | None:
    """Copy a card to another portfolio (creates new entry). Returns new collection ID."""
    with connect() as conn:
        cursor = conn.cursor()
        card = cursor.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
        if not card:
            return None
        card = dict(card)
        # Remove ID and update portfolio
        card.pop('id')
        card['portfolio_id'] = target_portfolio_id
        card['notes'] = card.get('notes', '') + ' [Copied]'
        cols = ', '.join(card.keys())
        placeholders = ', '.join(['?'] * len(card))
        cursor.execute(f"INSERT INTO collections ({cols}) VALUES ({placeholders})", list(card.values()))
        return cursor.lastrowid


def bulk_move_cards(collection_ids: list[int], target_portfolio_id: int) -> int:
    """Move multiple cards to another portfolio. Returns count moved."""
    if not collection_ids:
        return 0
    with connect() as conn:
        placeholders = ', '.join(['?'] * len(collection_ids))
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE collections SET portfolio_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
            [target_portfolio_id] + collection_ids
        )
        return cursor.rowcount


def bulk_copy_cards(collection_ids: list[int], target_portfolio_id: int) -> int:
    """Copy multiple cards to another portfolio. Returns count copied."""
    if not collection_ids:
        return 0
    with connect() as conn:
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(collection_ids))
        cards = cursor.execute(
            f"SELECT * FROM collections WHERE id IN ({placeholders})", collection_ids
        ).fetchall()
        count = 0
        for card in cards:
            card = dict(card)
            card.pop('id')
            card['portfolio_id'] = target_portfolio_id
            card['notes'] = card.get('notes', '') + ' [Copied]'
            cols = ', '.join(card.keys())
            placeholders2 = ', '.join(['?'] * len(card))
            cursor.execute(f"INSERT INTO collections ({cols}) VALUES ({placeholders2})", list(card.values()))
            count += 1
        return count


def bulk_delete_cards(collection_ids: list[int]) -> int:
    """Delete multiple cards. Returns count deleted."""
    if not collection_ids:
        return 0
    with connect() as conn:
        placeholders = ', '.join(['?'] * len(collection_ids))
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM collections WHERE id IN ({placeholders})", collection_ids)
        return cursor.rowcount


# ============================================================
# Default portfolio helpers
# ============================================================

def ensure_default_portfolio() -> int:
    """Ensure default portfolio exists, return its ID."""
    with connect() as conn:
        row = conn.execute("SELECT id FROM portfolios WHERE id = 1").fetchone()
        if row:
            return row[0]
        cursor = conn.cursor()
        cursor.execute("INSERT INTO portfolios (id, name, description) VALUES (1, 'Main Collection', 'Default portfolio for all cards')")
        return 1