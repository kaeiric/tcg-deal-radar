"""
Collection management module for TCG Deal Radar.
Handles card collection CRUD operations with full detail tracking.
"""
import json
from contextlib import contextmanager
import sqlite3
from config import DB_PATH
from modules.portfolio import ensure_default_portfolio


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
# Collection CRUD
# ============================================================

VALID_CONDITIONS = ['Near Mint', 'Lightly Played', 'Moderately Played', 'Heavily Played', 'Damaged']
VALID_LANGUAGES = ['English', 'Japanese', 'Chinese', 'Korean', 'French', 'German', 'Italian', 'Spanish', 'Portuguese']
VALID_VARIANTS = ['Normal', 'Holo', 'Reverse Holo', 'Alternate Art', 'Parallel', 'Manga', 'Full Art', 'Rainbow Rare', 'Gold', 'Etched', 'Promo', 'First Edition', 'Unlimited', 'Shadowless']
VALID_GRADING_COMPANIES = ['PSA', 'BGS', 'CGC', 'SGC', 'ACE', 'Other']
VALID_SEALED_TYPES = ['Booster Box', 'Elite Trainer Box', 'Booster Pack', 'Collection Box', 'Bundle', 'Blister Pack', 'Theme Deck', 'Starter Deck', 'V Battle Deck', 'VSTAR Special Set', 'Premium Collection', 'Other']


def validate_collection_data(data: dict) -> tuple[bool, str]:
    """Validate collection entry data. Returns (is_valid, error_message)."""
    required = ['game', 'card_name', 'language']
    for field in required:
        if not data.get(field):
            return False, f"Missing required field: {field}"

    if data['game'] not in ['Pokemon', 'One Piece']:
        return False, "Game must be 'Pokemon' or 'One Piece'"

    if data.get('condition') and data['condition'] not in VALID_CONDITIONS:
        return False, f"Invalid condition. Must be one of: {', '.join(VALID_CONDITIONS)}"

    if data.get('language') and data['language'] not in VALID_LANGUAGES:
        return False, f"Invalid language. Must be one of: {', '.join(VALID_LANGUAGES)}"

    if data.get('variant') and data['variant'] not in VALID_VARIANTS:
        return False, f"Invalid variant. Must be one of: {', '.join(VALID_VARIANTS)}"

    if data.get('grading_company') and data['grading_company'] not in VALID_GRADING_COMPANIES:
        return False, f"Invalid grading company. Must be one of: {', '.join(VALID_GRADING_COMPANIES)}"

    if data.get('sealed_type') and data['sealed_type'] not in VALID_SEALED_TYPES:
        return False, f"Invalid sealed type. Must be one of: {', '.join(VALID_SEALED_TYPES)}"

    if data.get('quantity', 1) < 1:
        return False, "Quantity must be at least 1"

    if data.get('purchase_price', 0) < 0:
        return False, "Purchase price cannot be negative"

    return True, ""


def add_card(data: dict) -> int | None:
    """
    Add a card to collection.
    Required: game, card_name, language
    Optional: portfolio_id, set_name, card_number, rarity, variant, condition,
              grading_company, grade, is_graded, is_sealed, sealed_type,
              quantity, purchase_price, purchase_date, purchase_currency,
              image_url, notes
    Returns collection ID or None on failure.
    """
    # Validate
    is_valid, error = validate_collection_data(data)
    if not is_valid:
        raise ValueError(error)

    # Ensure portfolio
    portfolio_id = data.get('portfolio_id') or ensure_default_portfolio()

    # Determine graded/sealed status
    is_graded = 1 if (data.get('grading_company') and data.get('grade')) else 0
    is_sealed = 1 if data.get('is_sealed') or data.get('sealed_type') else 0

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO collections (
                portfolio_id, game, card_name, set_name, card_number, rarity, language, variant,
                condition, grading_company, grade, is_graded, is_sealed, sealed_type,
                quantity, purchase_price, purchase_date, purchase_currency,
                image_url, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            portfolio_id,
            data['game'],
            data['card_name'].strip(),
            data.get('set_name', '').strip(),
            data.get('card_number', '').strip(),
            data.get('rarity', '').strip(),
            data['language'],
            data.get('variant', '').strip(),
            data.get('condition', 'Near Mint'),
            data.get('grading_company', '').strip(),
            data.get('grade', '').strip(),
            is_graded,
            is_sealed,
            data.get('sealed_type', '').strip(),
            data.get('quantity', 1),
            data.get('purchase_price', 0),
            data.get('purchase_date', ''),
            data.get('purchase_currency', 'USD'),
            data.get('image_url', '').strip(),
            data.get('notes', '').strip()
        ))
        return cursor.lastrowid


def get_card(collection_id: int) -> dict | None:
    """Get a single card by ID."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
        return dict(row) if row else None


def get_cards(portfolio_id: int = None, filters: dict = None) -> list[dict]:
    """
    Get cards with optional filtering.
    filters can include: game, card_name, set_name, card_number, language, variant,
                         condition, grading_company, grade, is_graded, is_sealed,
                         sealed_type, min_price, max_price, min_purchase_price, max_purchase_price
    """
    with connect() as conn:
        query = "SELECT c.*, p.name as portfolio_name FROM collections c LEFT JOIN portfolios p ON p.id = c.portfolio_id"
        conditions = []
        params = []

        if portfolio_id:
            conditions.append("c.portfolio_id = ?")
            params.append(portfolio_id)

        if filters:
            if filters.get('game'):
                conditions.append("c.game = ?")
                params.append(filters['game'])
            if filters.get('card_name'):
                conditions.append("c.card_name LIKE ?")
                params.append(f"%{filters['card_name']}%")
            if filters.get('set_name'):
                conditions.append("c.set_name LIKE ?")
                params.append(f"%{filters['set_name']}%")
            if filters.get('card_number'):
                conditions.append("c.card_number LIKE ?")
                params.append(f"%{filters['card_number']}%")
            if filters.get('language'):
                conditions.append("c.language = ?")
                params.append(filters['language'])
            if filters.get('variant'):
                conditions.append("c.variant = ?")
                params.append(filters['variant'])
            if filters.get('condition'):
                conditions.append("c.condition = ?")
                params.append(filters['condition'])
            if filters.get('grading_company'):
                conditions.append("c.grading_company = ?")
                params.append(filters['grading_company'])
            if filters.get('grade'):
                conditions.append("c.grade = ?")
                params.append(filters['grade'])
            if 'is_graded' in filters:
                conditions.append("c.is_graded = ?")
                params.append(1 if filters['is_graded'] else 0)
            if 'is_sealed' in filters:
                conditions.append("c.is_sealed = ?")
                params.append(1 if filters['is_sealed'] else 0)
            if filters.get('sealed_type'):
                conditions.append("c.sealed_type = ?")
                params.append(filters['sealed_type'])
            if filters.get('min_price') is not None:
                conditions.append("c.purchase_price >= ?")
                params.append(filters['min_price'])
            if filters.get('max_price') is not None:
                conditions.append("c.purchase_price <= ?")
                params.append(filters['max_price'])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.game, c.card_name, c.set_name, c.card_number"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_card(collection_id: int, data: dict) -> bool:
    """Update a card entry."""
    # Validate (only check fields that are provided)
    if data:
        is_valid, error = validate_collection_data({**{'game': 'Pokemon', 'card_name': 'x', 'language': 'English'}, **data})
        if not is_valid and not all(k in data for k in ['game', 'card_name', 'language']):
            # Only validate provided fields
            pass  # Skip full validation for partial updates

    with connect() as conn:
        cursor = conn.cursor()

        # Handle graded/sealed flags
        if 'grading_company' in data or 'grade' in data:
            grading_company = data.get('grading_company', '')
            grade = data.get('grade', '')
            data['is_graded'] = 1 if (grading_company and grade) else 0

        if 'sealed_type' in data or 'is_sealed' in data:
            data['is_sealed'] = 1 if (data.get('sealed_type') or data.get('is_sealed')) else 0

        # Build update query
        allowed_fields = [
            'portfolio_id', 'game', 'card_name', 'set_name', 'card_number', 'rarity',
            'language', 'variant', 'condition', 'grading_company', 'grade', 'is_graded',
            'is_sealed', 'sealed_type', 'quantity', 'purchase_price', 'purchase_date',
            'purchase_currency', 'image_url', 'notes'
        ]

        updates = []
        params = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(collection_id)

        cursor.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id = ?", params)
        return cursor.rowcount > 0


def delete_card(collection_id: int) -> bool:
    """Delete a card from collection."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        return cursor.rowcount > 0


# ============================================================
# Collection Analytics
# ============================================================

def get_collection_stats(portfolio_id: int = None) -> dict:
    """Get collection statistics."""
    with connect() as conn:
        cursor = conn.cursor()

        where_clause = "WHERE portfolio_id = ?" if portfolio_id else ""
        where_and = "WHERE portfolio_id = ? AND" if portfolio_id else "WHERE"
        params = [portfolio_id] if portfolio_id else []

        # Overall stats
        stats = cursor.execute(f"""
            SELECT
                COUNT(*) as unique_entries,
                SUM(quantity) as total_quantity,
                SUM(quantity * purchase_price) as total_cost,
                COUNT(CASE WHEN is_graded = 1 THEN 1 END) as graded_count,
                COUNT(CASE WHEN is_sealed = 1 THEN 1 END) as sealed_count,
                COUNT(CASE WHEN game = 'Pokemon' THEN 1 END) as pokemon_entries,
                COUNT(CASE WHEN game = 'One Piece' THEN 1 END) as onepiece_entries
            FROM collections {where_clause}
        """, params).fetchone()

        # By game
        by_game = cursor.execute(f"""
            SELECT game, COUNT(*) as entries, SUM(quantity) as qty, SUM(quantity * purchase_price) as cost
            FROM collections {where_clause} GROUP BY game
        """, params).fetchall()

        # By condition
        by_condition = cursor.execute(f"""
            SELECT condition, COUNT(*) as count, SUM(quantity) as qty
            FROM collections {where_clause} GROUP BY condition ORDER BY count DESC
        """, params).fetchall()

        # By variant
        by_variant = cursor.execute(f"""
            SELECT variant, COUNT(*) as count, SUM(quantity) as qty
            FROM collections {where_and} variant != '' GROUP BY variant ORDER BY count DESC
        """, params).fetchall()

        # Graded breakdown
        graded = cursor.execute(f"""
            SELECT grading_company, grade, COUNT(*) as count
            FROM collections {where_and} is_graded = 1 GROUP BY grading_company, grade
        """, params).fetchall()

        # Sealed breakdown
        sealed = cursor.execute(f"""
            SELECT sealed_type, COUNT(*) as count, SUM(quantity) as qty
            FROM collections {where_and} is_sealed = 1 GROUP BY sealed_type
        """, params).fetchall()

        # Language breakdown
        by_language = cursor.execute(f"""
            SELECT language, COUNT(*) as count, SUM(quantity) as qty
            FROM collections {where_clause} GROUP BY language ORDER BY count DESC
        """, params).fetchall()

        return {
            "overall": dict(stats) if stats else {},
            "by_game": [dict(r) for r in by_game],
            "by_condition": [dict(r) for r in by_condition],
            "by_variant": [dict(r) for r in by_variant],
            "graded": [dict(r) for r in graded],
            "sealed": [dict(r) for r in sealed],
            "by_language": [dict(r) for r in by_language]
        }


def get_cards_by_set(portfolio_id: int = None) -> list[dict]:
    """Get cards grouped by set for set completion tracking."""
    with connect() as conn:
        where_clause = "WHERE portfolio_id = ?" if portfolio_id else ""
        where_and = "WHERE portfolio_id = ? AND" if portfolio_id else "WHERE"
        params = [portfolio_id] if portfolio_id else []

        rows = conn.execute(f"""
            SELECT game, set_name, card_number, card_name, rarity, variant, language,
                   COUNT(*) as variant_count, SUM(quantity) as total_qty
            FROM collections {where_and} set_name != ''
            GROUP BY game, set_name, card_number, card_name, rarity, variant, language
            ORDER BY game, set_name, card_number
        """, params).fetchall()
        return [dict(r) for r in rows]


def search_cards(query: str, portfolio_id: int = None, limit: int = 50) -> list[dict]:
    """Search cards by name, set, or number."""
    with connect() as conn:
        where_parts = ["(c.card_name LIKE ? OR c.set_name LIKE ? OR c.card_number LIKE ?)"]
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if portfolio_id:
            where_parts.append("c.portfolio_id = ?")
            params.append(portfolio_id)

        where = "WHERE " + " AND ".join(where_parts)

        rows = conn.execute(f"""
            SELECT c.*, p.name as portfolio_name
            FROM collections c
            LEFT JOIN portfolios p ON p.id = c.portfolio_id
            {where}
            ORDER BY c.card_name
            LIMIT ?
        """, params + [limit]).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# Validation helpers (export for UI)
# ============================================================

def get_valid_conditions() -> list[str]:
    return VALID_CONDITIONS.copy()

def get_valid_languages() -> list[str]:
    return VALID_LANGUAGES.copy()

def get_valid_variants() -> list[str]:
    return VALID_VARIANTS.copy()

def get_valid_grading_companies() -> list[str]:
    return VALID_GRADING_COMPANIES.copy()

def get_valid_sealed_types() -> list[str]:
    return VALID_SEALED_TYPES.copy()