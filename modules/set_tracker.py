"""
Set completion tracker module for TCG Deal Radar.
Handles set catalog management and completion tracking.
"""
import json
import requests
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
# Sets Catalog CRUD
# ============================================================

def create_set(data: dict) -> int | None:
    """Create a new set entry."""
    required = ['game', 'set_code', 'set_name']
    for field in required:
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")

    if data['game'] not in ['Pokemon', 'One Piece']:
        raise ValueError("Game must be 'Pokemon' or 'One Piece'")

    with connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO sets (game, set_code, set_name, release_date, total_cards, total_secret, series)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['game'],
                data['set_code'].strip().upper(),
                data['set_name'].strip(),
                data.get('release_date', ''),
                data.get('total_cards', 0),
                data.get('total_secret', 0),
                data.get('series', '').strip()
            ))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Set {data['set_code']} already exists for {data['game']}")


def get_sets(game: str = None) -> list[dict]:
    """Get all sets, optionally filtered by game."""
    with connect() as conn:
        query = "SELECT * FROM sets"
        params = []
        if game:
            query += " WHERE game = ?"
            params.append(game)
        query += " ORDER BY game, release_date DESC, set_code"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_set(set_id: int) -> dict | None:
    """Get a single set by ID."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM sets WHERE id = ?", (set_id,)).fetchone()
        return dict(row) if row else None


def update_set(set_id: int, data: dict) -> bool:
    """Update a set."""
    with connect() as conn:
        cursor = conn.cursor()

        allowed_fields = ['game', 'set_code', 'set_name', 'release_date', 'total_cards', 'total_secret', 'series']
        updates = []
        params = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])

        if not updates:
            return False

        params.append(set_id)
        cursor.execute(f"UPDATE sets SET {', '.join(updates)} WHERE id = ?", params)
        return cursor.rowcount > 0


def delete_set(set_id: int) -> bool:
    """Delete a set and its cards."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sets WHERE id = ?", (set_id,))
        return cursor.rowcount > 0


# ============================================================
# Set Cards CRUD
# ============================================================

def add_set_card(data: dict) -> int | None:
    """Add a card to a set catalog."""
    required = ['set_id', 'card_number', 'card_name']
    for field in required:
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")

    with connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO set_cards (set_id, card_number, card_name, rarity, variant, language, market_price, market_price_currency, market_price_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['set_id'],
                data['card_number'].strip(),
                data['card_name'].strip(),
                data.get('rarity', '').strip(),
                data.get('variant', '').strip(),
                data.get('language', 'English'),
                data.get('market_price', 0),
                data.get('market_price_currency', 'USD'),
                data.get('market_price_updated', '')
            ))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Card {data['card_number']} already exists in this set")


def get_set_cards(set_id: int, language: str = None) -> list[dict]:
    """Get all cards in a set."""
    with connect() as conn:
        query = "SELECT * FROM set_cards WHERE set_id = ?"
        params = [set_id]
        if language:
            query += " AND language = ?"
            params.append(language)
        query += " ORDER BY card_number"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_set_card(card_id: int, data: dict) -> bool:
    """Update a set card."""
    with connect() as conn:
        cursor = conn.cursor()

        allowed_fields = ['card_number', 'card_name', 'rarity', 'variant', 'language', 'market_price', 'market_price_currency', 'market_price_updated']
        updates = []
        params = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])

        if not updates:
            return False

        params.append(card_id)
        cursor.execute(f"UPDATE set_cards SET {', '.join(updates)} WHERE id = ?", params)
        return cursor.rowcount > 0


def delete_set_card(card_id: int) -> bool:
    """Delete a set card."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM set_cards WHERE id = ?", (card_id,))
        return cursor.rowcount > 0


def bulk_add_set_cards(set_id: int, cards: list[dict]) -> int:
    """Add multiple cards to a set at once."""
    if not cards:
        return 0

    with connect() as conn:
        cursor = conn.cursor()
        count = 0
        for card in cards:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO set_cards (set_id, card_number, card_name, rarity, variant, language, market_price, market_price_currency, market_price_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    set_id,
                    card['card_number'].strip(),
                    card['card_name'].strip(),
                    card.get('rarity', '').strip(),
                    card.get('variant', '').strip(),
                    card.get('language', 'English'),
                    card.get('market_price', 0),
                    card.get('market_price_currency', 'USD'),
                    card.get('market_price_updated', '')
                ))
                if cursor.rowcount > 0:
                    count += 1
            except Exception:
                pass
        return count


# ============================================================
# Set Completion Tracking
# ============================================================

def get_set_completion(set_id: int, portfolio_id: int = None, language: str = 'English') -> dict:
    """
    Get set completion status for a portfolio.
    Returns: total_cards, owned_cards, missing_cards, completion_pct, estimated_cost_to_complete
    """
    with connect() as conn:
        # Get set info
        set_info = conn.execute("SELECT * FROM sets WHERE id = ?", (set_id,)).fetchone()
        if not set_info:
            return {}
        set_info = dict(set_info)

        # Get all cards in set (for specified language)
        set_cards = conn.execute("""
            SELECT * FROM set_cards WHERE set_id = ? AND language = ?
            ORDER BY card_number
        """, (set_id, language)).fetchall()

        if not set_cards:
            return {
                "set": set_info,
                "total_cards": 0,
                "owned_cards": 0,
                "missing_cards": 0,
                "completion_pct": 0,
                "owned": [],
                "missing": [],
                "estimated_cost_to_complete": 0
            }

        # Get owned cards from collection - FIX: explicitly use c.language to avoid ambiguity
        if portfolio_id:
            owned = conn.execute("""
                SELECT c.*, sc.rarity as set_rarity, sc.variant as set_variant, sc.market_price
                FROM collections c
                LEFT JOIN set_cards sc ON sc.set_id = ? AND sc.card_number = c.card_number AND sc.language = c.language
                WHERE c.portfolio_id = ? AND c.game = ? AND c.set_name = ? AND c.language = ?
            """, (set_id, portfolio_id, set_info['game'], set_info['set_name'], language)).fetchall()
        else:
            owned = conn.execute("""
                SELECT c.*, sc.rarity as set_rarity, sc.variant as set_variant, sc.market_price
                FROM collections c
                LEFT JOIN set_cards sc ON sc.set_id = ? AND sc.card_number = c.card_number AND sc.language = c.language
                WHERE c.game = ? AND c.set_name = ? AND c.language = ?
            """, (set_id, set_info['game'], set_info['set_name'], language)).fetchall()

        owned_dict = {}
        for o in owned:
            key = f"{o['card_number']}|{o.get('variant', '')}|{o['language']}"
            if key not in owned_dict:
                owned_dict[key] = []
            owned_dict[key].append(dict(o))

        # Match set cards to owned
        owned_list = []
        missing_list = []
        cost_to_complete = 0

        for sc in set_cards:
            sc = dict(sc)
            key = f"{sc['card_number']}|{sc.get('variant', '')}|{sc['language']}"

            if key in owned_dict and owned_dict[key]:
                # Card is owned (at least one copy)
                owned_entry = owned_dict[key][0]
                owned_list.append({
                    "set_card": sc,
                    "collection": owned_entry,
                    "quantity_owned": sum(o['quantity'] for o in owned_dict[key])
                })
            else:
                # Missing
                missing_list.append(sc)
                if sc.get('market_price', 0) > 0:
                    cost_to_complete += sc['market_price']

        total = len(set_cards)
        owned_count = len(owned_list)
        missing_count = len(missing_list)

        return {
            "set": set_info,
            "total_cards": total,
            "owned_cards": owned_count,
            "missing_cards": missing_count,
            "completion_pct": round((owned_count / total * 100) if total > 0 else 0, 1),
            "owned": owned_list,
            "missing": missing_list,
            "estimated_cost_to_complete": round(cost_to_complete, 2)
        }


def get_all_set_completions(portfolio_id: int = None, game: str = None, language: str = 'English') -> list[dict]:
    """Get completion status for all sets."""
    sets = get_sets(game)
    results = []

    for s in sets:
        completion = get_set_completion(s['id'], portfolio_id, language)
        if completion.get('total_cards', 0) > 0:
            results.append({
                "set_id": s['id'],
                "set_code": s['set_code'],
                "set_name": s['set_name'],
                "game": s['game'],
                "total_cards": completion['total_cards'],
                "owned_cards": completion['owned_cards'],
                "missing_cards": completion['missing_cards'],
                "completion_pct": completion['completion_pct'],
                "estimated_cost_to_complete": completion['estimated_cost_to_complete']
            })

    # Sort by completion percentage (ascending - least complete first)
    results.sort(key=lambda x: x['completion_pct'])
    return results


# ============================================================
# External Data Import (PokéTCG.io for Pokemon)
# ============================================================

POKEMON_TCG_API = "https://api.pokemontcg.io/v2"

def import_pokemon_sets_from_api(api_key: str = None) -> dict:
    """
    Import Pokemon sets from PokéTCG.io API.
    Returns summary of imported sets.
    """
    headers = {}
    if api_key:
        headers['X-Api-Key'] = api_key

    try:
        response = requests.get(f"{POKEMON_TCG_API}/sets", headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        imported = 0
        updated = 0
        errors = []

        with connect() as conn:
            cursor = conn.cursor()

            for set_data in data.get('data', []):
                try:
                    set_code = set_data.get('id', '').upper()
                    set_name = set_data.get('name', '')
                    release_date = set_data.get('releaseDate', '')
                    series = set_data.get('series', '')
                    total_cards = set_data.get('printedTotal', 0) + set_data.get('total', 0)  # approximate

                    # Count secret rares
                    # We'll need to fetch cards for this

                    cursor.execute("""
                        INSERT INTO sets (game, set_code, set_name, release_date, total_cards, total_secret, series)
                        VALUES ('Pokemon', ?, ?, ?, ?, 0, ?)
                        ON CONFLICT(game, set_code) DO UPDATE SET
                            set_name = excluded.set_name,
                            release_date = excluded.release_date,
                            total_cards = excluded.total_cards,
                            series = excluded.series
                    """, (set_code, set_name, release_date, total_cards, series))

                    if cursor.rowcount > 0:
                        imported += 1
                    else:
                        updated += 1

                except Exception as e:
                    errors.append(f"{set_data.get('id', 'unknown')}: {e}")

        return {"imported": imported, "updated": updated, "errors": errors}

    except Exception as e:
        return {"imported": 0, "updated": 0, "errors": [str(e)]}


def import_pokemon_set_cards_from_api(set_id: int, api_key: str = None) -> dict:
    """
    Import cards for a specific Pokemon set from PokéTCG.io API.
    """
    # Get set code from database
    with connect() as conn:
        set_info = conn.execute("SELECT set_code FROM sets WHERE id = ?", (set_id,)).fetchone()

    if not set_info:
        return {"imported": 0, "errors": ["Set not found"]}

    set_code = set_info['set_code']
    headers = {}
    if api_key:
        headers['X-Api-Key'] = api_key

    try:
        # Fetch cards for this set
        response = requests.get(
            f"{POKEMON_TCG_API}/cards",
            params={"q": f"set.id:{set_code}", "pageSize": 250},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        cards = []
        for card_data in data.get('data', []):
            # Extract card number
            number = card_data.get('number', '')

            # Determine variant
            rarity = card_data.get('rarity', '')
            subtypes = card_data.get('subtypes', [])
            variant = 'Normal'
            if 'Full Art' in subtypes:
                variant = 'Full Art'
            elif 'Alternate Art' in subtypes or 'Special Illustration' in rarity:
                variant = 'Alternate Art'
            elif 'Rainbow Rare' in rarity or 'Hyper Rare' in rarity:
                variant = 'Rainbow Rare'
            elif 'Illustration Rare' in rarity:
                variant = 'Illustration Rare'
            elif 'Ultra Rare' in rarity:
                variant = 'Ultra Rare'
            elif 'Reverse Holo' in subtypes:
                variant = 'Reverse Holo'
            elif 'Holo' in subtypes:
                variant = 'Holo'

            cards.append({
                'card_number': number,
                'card_name': card_data.get('name', ''),
                'rarity': rarity,
                'variant': variant,
                'language': 'English'
            })

        count = bulk_add_set_cards(set_id, cards)
        return {"imported": count, "errors": []}

    except Exception as e:
        return {"imported": 0, "errors": [str(e)]}


# ============================================================
# One Piece Card Game - Manual CSV Import (no public API)
# ============================================================

def import_onepiece_sets_from_csv(csv_path: str) -> dict:
    """Import One Piece sets from CSV file."""
    import pandas as pd

    try:
        df = pd.read_csv(csv_path)
        required_cols = ['set_code', 'set_name']
        for col in required_cols:
            if col not in df.columns:
                return {"imported": 0, "errors": [f"Missing column: {col}"]}

        imported = 0
        with connect() as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO sets (game, set_code, set_name, release_date, total_cards, total_secret, series)
                        VALUES ('One Piece', ?, ?, ?, ?, ?, 'OP Series')
                        ON CONFLICT(game, set_code) DO UPDATE SET
                            set_name = excluded.set_name,
                            release_date = excluded.release_date,
                            total_cards = excluded.total_cards
                    """, (
                        str(row['set_code']).strip().upper(),
                        str(row['set_name']).strip(),
                        str(row.get('release_date', '')),
                        int(row.get('total_cards', 0)),
                        int(row.get('total_secret', 0))
                    ))
                    if cursor.rowcount > 0:
                        imported += 1
                except Exception:
                    pass

        return {"imported": imported, "errors": []}

    except Exception as e:
        return {"imported": 0, "errors": [str(e)]}


def import_onepiece_set_cards_from_csv(set_id: int, csv_path: str) -> dict:
    """Import One Piece set cards from CSV file."""
    import pandas as pd

    try:
        df = pd.read_csv(csv_path)
        required_cols = ['card_number', 'card_name']
        for col in required_cols:
            if col not in df.columns:
                return {"imported": 0, "errors": [f"Missing column: {col}"]}

        cards = []
        for _, row in df.iterrows():
            cards.append({
                'card_number': str(row['card_number']).strip(),
                'card_name': str(row['card_name']).strip(),
                'rarity': str(row.get('rarity', '')).strip(),
                'variant': str(row.get('variant', '')).strip(),
                'language': str(row.get('language', 'English')).strip()
            })

        count = bulk_add_set_cards(set_id, cards)
        return {"imported": count, "errors": []}

    except Exception as e:
        return {"imported": 0, "errors": [str(e)]}