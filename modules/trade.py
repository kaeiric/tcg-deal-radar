"""
Trade analyzer module for TCG Deal Radar.
Handles trade evaluation and trade history.
"""
import json
from contextlib import contextmanager
import sqlite3
from config import DB_PATH
from modules.price_history import get_latest_price


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
# Trade Evaluation
# ============================================================

def evaluate_trade(
    items_given: list[dict],
    items_received: list[dict],
    cash_given: float = 0,
    cash_received: float = 0
) -> dict:
    """
    Evaluate a trade proposal.

    items_given: list of {collection_id, quantity, condition_override}
    items_received: list of {collection_id, quantity, condition_override}

    Returns evaluation dict with values, difference, and recommendation.
    """
    # Calculate value of items given
    value_given = 0
    given_details = []

    for item in items_given:
        collection_id = item['collection_id']
        quantity = item.get('quantity', 1)

        # Get latest market price
        latest_price_data = get_latest_price(collection_id)
        if latest_price_data:
            price = latest_price_data['price']
        else:
            # Fallback to purchase price
            with connect() as conn:
                card = conn.execute("SELECT purchase_price FROM collections WHERE id = ?", (collection_id,)).fetchone()
                price = card['purchase_price'] if card else 0

        item_value = price * quantity
        value_given += item_value

        with connect() as conn:
            card = conn.execute("SELECT card_name, set_name, card_number, language, variant FROM collections WHERE id = ?", (collection_id,)).fetchone()

        given_details.append({
            'collection_id': collection_id,
            'name': card['card_name'] if card else 'Unknown',
            'set': card['set_name'] if card else '',
            'number': card['card_number'] if card else '',
            'language': card['language'] if card else '',
            'variant': card['variant'] if card else '',
            'quantity': quantity,
            'unit_price': price,
            'total_value': item_value
        })

    # Calculate value of items received
    value_received = 0
    received_details = []

    for item in items_received:
        collection_id = item['collection_id']
        quantity = item.get('quantity', 1)

        latest_price_data = get_latest_price(collection_id)
        if latest_price_data:
            price = latest_price_data['price']
        else:
            with connect() as conn:
                card = conn.execute("SELECT purchase_price FROM collections WHERE id = ?", (collection_id,)).fetchone()
                price = card['purchase_price'] if card else 0

        item_value = price * quantity
        value_received += item_value

        with connect() as conn:
            card = conn.execute("SELECT card_name, set_name, card_number, language, variant FROM collections WHERE id = ?", (collection_id,)).fetchone()

        received_details.append({
            'collection_id': collection_id,
            'name': card['card_name'] if card else 'Unknown',
            'set': card['set_name'] if card else '',
            'number': card['card_number'] if card else '',
            'language': card['language'] if card else '',
            'variant': card['variant'] if card else '',
            'quantity': quantity,
            'unit_price': price,
            'total_value': item_value
        })

    # Net value difference (including cash)
    net_value_given = value_given + cash_given
    net_value_received = value_received + cash_received
    value_difference = net_value_received - net_value_given

    # Percentage difference relative to value given
    pct_difference = (value_difference / net_value_given * 100) if net_value_given > 0 else 0

    # Determine evaluation
    if pct_difference >= 5:
        evaluation = "Favorable to Me"
    elif pct_difference <= -5:
        evaluation = "Unfavorable to Me"
    else:
        evaluation = "Fair Trade"

    return {
        'value_given': round(value_given, 2),
        'value_received': round(value_received, 2),
        'cash_given': cash_given,
        'cash_received': cash_received,
        'net_value_given': round(net_value_given, 2),
        'net_value_received': round(net_value_received, 2),
        'value_difference': round(value_difference, 2),
        'pct_difference': round(pct_difference, 2),
        'evaluation': evaluation,
        'items_given': given_details,
        'items_received': received_details,
        'disclaimer': (
            "This evaluation is based on estimated market prices only. "
            "Actual trade fairness depends on card condition, liquidity, buyer demand, "
            "grading accuracy, and personal collecting goals. Always verify card condition "
            "and authenticity before completing any trade."
        )
    }


# ============================================================
# Trade History CRUD
# ============================================================

def record_trade(data: dict) -> int | None:
    """
    Record a completed trade.
    Required: trade_date, items_given, items_received, value_given, value_received,
              value_difference, pct_difference, evaluation
    Optional: cash_given, cash_received, cash_currency, notes
    """
    required = ['trade_date', 'items_given', 'items_received',
                'value_given', 'value_received', 'value_difference',
                'pct_difference', 'evaluation']
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Convert items to JSON
    items_given_json = json.dumps(data['items_given'])
    items_received_json = json.dumps(data['items_received'])

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (
                trade_date, items_given, items_received,
                cash_given, cash_received, cash_currency,
                value_given, value_received, value_difference, pct_difference,
                evaluation, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['trade_date'],
            items_given_json,
            items_received_json,
            data.get('cash_given', 0),
            data.get('cash_received', 0),
            data.get('cash_currency', 'USD'),
            data['value_given'],
            data['value_received'],
            data['value_difference'],
            data['pct_difference'],
            data['evaluation'],
            data.get('notes', '')
        ))
        return cursor.lastrowid


def get_trades(limit: int = 100) -> list[dict]:
    """Get trade history."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM trades ORDER BY trade_date DESC, created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_trade(trade_id: int) -> dict | None:
    """Get a single trade by ID."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if row:
            trade = dict(row)
            trade['items_given'] = json.loads(trade['items_given']) if trade['items_given'] else []
            trade['items_received'] = json.loads(trade['items_received']) if trade['items_received'] else []
            return trade
        return None


def delete_trade(trade_id: int) -> bool:
    """Delete a trade record."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        return cursor.rowcount > 0


def get_trade_stats() -> dict:
    """Get trade statistics."""
    with connect() as conn:
        stats = conn.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN evaluation = 'Favorable to Me' THEN 1 ELSE 0 END) as favorable,
                SUM(CASE WHEN evaluation = 'Fair Trade' THEN 1 ELSE 0 END) as fair,
                SUM(CASE WHEN evaluation = 'Unfavorable to Me' THEN 1 ELSE 0 END) as unfavorable,
                SUM(value_difference) as net_value_difference,
                AVG(pct_difference) as avg_pct_difference
            FROM trades
        """).fetchone()
        return dict(stats) if stats else {}


# ============================================================
# Quick Trade Evaluation (for UI)
# ============================================================

def quick_evaluate(given_ids: list[int], received_ids: list[int],
                   given_quantities: list[int] = None,
                   received_quantities: list[int] = None,
                   cash_given: float = 0, cash_received: float = 0) -> dict:
    """
    Quick trade evaluation from collection IDs.
    """
    items_given = []
    for i, cid in enumerate(given_ids):
        items_given.append({
            'collection_id': cid,
            'quantity': given_quantities[i] if given_quantities and i < len(given_quantities) else 1
        })

    items_received = []
    for i, cid in enumerate(received_ids):
        items_received.append({
            'collection_id': cid,
            'quantity': received_quantities[i] if received_quantities and i < len(received_quantities) else 1
        })

    return evaluate_trade(items_given, items_received, cash_given, cash_received)