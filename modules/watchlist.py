"""
Watchlist module for TCG Deal Radar.
Handles target price alerts and price movement notifications.
"""
import json
from contextlib import contextmanager
import sqlite3
from datetime import datetime
from config import DB_PATH
from modules.notification import send_ntfy
from modules.price_history import get_latest_price, get_price_trend


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
# Watchlist CRUD
# ============================================================

def add_watchlist_item(data: dict) -> int | None:
    """
    Add a card to watchlist.
    Required: game, card_name, language, target_price
    Optional: portfolio_id, set_name, card_number, rarity, variant,
              condition, grading_company, grade, is_sealed, sealed_type,
              alert_on_drop, alert_on_rise, significant_change_pct
    """
    required = ['game', 'card_name', 'language', 'target_price']
    for field in required:
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")

    if data['game'] not in ['Pokemon', 'One Piece']:
        raise ValueError("Game must be 'Pokemon' or 'One Piece'")

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO watchlist (
                portfolio_id, game, card_name, set_name, card_number, rarity, language, variant,
                condition, grading_company, grade, is_sealed, sealed_type,
                target_price, alert_on_drop, alert_on_rise, significant_change_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('portfolio_id'),
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
            1 if data.get('is_sealed') or data.get('sealed_type') else 0,
            data.get('sealed_type', '').strip(),
            float(data['target_price']),
            1 if data.get('alert_on_drop', True) else 0,
            1 if data.get('alert_on_rise', False) else 0,
            float(data.get('significant_change_pct', 20.0))
        ))
        return cursor.lastrowid


def get_watchlist(portfolio_id: int = None, active_only: bool = True) -> list[dict]:
    """Get watchlist items."""
    with connect() as conn:
        query = "SELECT * FROM watchlist"
        conditions = []
        params = []

        if portfolio_id:
            conditions.append("portfolio_id = ?")
            params.append(portfolio_id)

        if active_only:
            conditions.append("active = 1")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY game, card_name"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_watchlist_item(item_id: int) -> dict | None:
    """Get a single watchlist item."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM watchlist WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


def update_watchlist_item(item_id: int, data: dict) -> bool:
    """Update a watchlist item."""
    with connect() as conn:
        cursor = conn.cursor()

        allowed_fields = [
            'portfolio_id', 'game', 'card_name', 'set_name', 'card_number', 'rarity',
            'language', 'variant', 'condition', 'grading_company', 'grade',
            'is_sealed', 'sealed_type', 'target_price', 'alert_on_drop',
            'alert_on_rise', 'significant_change_pct', 'active'
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
        params.append(item_id)

        cursor.execute(f"UPDATE watchlist SET {', '.join(updates)} WHERE id = ?", params)
        return cursor.rowcount > 0


def delete_watchlist_item(item_id: int) -> bool:
    """Delete a watchlist item."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        return cursor.rowcount > 0


# ============================================================
# Alert Checking
# ============================================================

def check_watchlist_alerts(market_prices: dict) -> list[dict]:
    """
    Check watchlist items against current market prices.
    market_prices: dict of {collection_key: price} where collection_key identifies the card
    Returns list of triggered alerts.
    """
    watchlist = get_watchlist(active_only=True)
    triggered = []

    for item in watchlist:
        # Build key to match market price
        key = f"{item['game']}|{item['card_name']}|{item['set_name']}|{item['card_number']}|{item['language']}|{item['variant']}|{item['condition']}|{item['grading_company']}|{item['grade']}"

        # Try exact match first, then fallback to name+game+language
        current_price = market_prices.get(key)

        if current_price is None:
            # Fallback: match by game, name, language
            for k, v in market_prices.items():
                parts = k.split('|')
                if (parts[0] == item['game'] and
                    parts[1].lower() == item['card_name'].lower() and
                    parts[4].lower() == item['language'].lower()):
                    current_price = v
                    break

        if current_price is None:
            continue

        target = item['target_price']
        alerts = []

        # Check drop alert
        if item['alert_on_drop'] and current_price <= target:
            alerts.append({
                'type': 'target_reached',
                'message': f"Price dropped to ${current_price:.2f} (target: ${target:.2f})",
                'current_price': current_price,
                'target_price': target
            })

        # Check significant rise alert
        if item['alert_on_rise']:
            # Get price trend
            # We'd need a collection_id for this, so skip for now
            # In practice, you'd link watchlist to collections or track separately
            pass

        if alerts:
            triggered.append({
                'watchlist_id': item['id'],
                'item': item,
                'current_price': current_price,
                'alerts': alerts
            })

    return triggered


def send_watchlist_notification(alert: dict) -> bool:
    """Send ntfy notification for watchlist alert."""
    item = alert['item']
    current_price = alert['current_price']

    for a in alert['alerts']:
        title = f"TCG Watchlist: {a['type'].replace('_', ' ').title()}"
        message = (
            f"{item['card_name']} ({item['game']}, {item['language']})\n"
            f"Current: ${current_price:.2f}\n"
            f"Target: ${item['target_price']:.2f}\n"
            f"{a['message']}"
        )

        try:
            send_ntfy(title, message)
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return False

    return True


def check_significant_movements(collection_id: int, threshold_pct: float = 20.0) -> dict | None:
    """
    Check if a collection item has had a significant price movement.
    Returns alert info if threshold exceeded.
    """
    trend = get_price_trend(collection_id, days=7)

    if trend['trend'] == 'insufficient_data':
        return None

    # Get latest price
    latest = get_latest_price(collection_id)
    if not latest:
        return None

    # Calculate change from 7 days ago
    history = get_price_history(collection_id, days=7)
    if len(history) < 2:
        return None

    old_price = history[0]['price']
    new_price = history[-1]['price']
    pct_change = ((new_price - old_price) / old_price) * 100 if old_price > 0 else 0

    if abs(pct_change) >= threshold_pct:
        return {
            'collection_id': collection_id,
            'old_price': old_price,
            'new_price': new_price,
            'pct_change': round(pct_change, 2),
            'direction': 'up' if pct_change > 0 else 'down',
            'trend_confidence': trend['confidence']
        }

    return None