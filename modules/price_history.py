"""
Price history tracking module for TCG Deal Radar.
Handles historical price snapshots and chart data generation.
"""
import json
from contextlib import contextmanager
import sqlite3
from datetime import datetime, timedelta
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
# Price History CRUD
# ============================================================

def record_price_snapshot(
    collection_id: int,
    price: float,
    source: str,
    currency: str = 'USD',
    condition: str = 'Near Mint',
    language: str = '',
    variant: str = '',
    grading_company: str = '',
    grade: str = ''
) -> int:
    """Record a price snapshot for a collection item. Returns snapshot ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO price_history (
                collection_id, price, currency, source, condition, language,
                variant, grading_company, grade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (collection_id, price, currency, source, condition, language, variant, grading_company, grade))
        return cursor.lastrowid


def get_price_history(collection_id: int, days: int = None) -> list[dict]:
    """Get price history for a collection item, optionally limited to last N days."""
    with connect() as conn:
        query = "SELECT * FROM price_history WHERE collection_id = ?"
        params = [collection_id]

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            query += " AND recorded_at >= ?"
            params.append(cutoff)

        query += " ORDER BY recorded_at ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_latest_price(collection_id: int) -> dict | None:
    """Get the most recent price snapshot for a collection item."""
    with connect() as conn:
        row = conn.execute("""
            SELECT * FROM price_history
            WHERE collection_id = ?
            ORDER BY recorded_at DESC LIMIT 1
        """, (collection_id,)).fetchone()
        return dict(row) if row else None


def get_price_at_date(collection_id: int, target_date: str) -> dict | None:
    """Get price snapshot closest to a specific date (ISO format)."""
    with connect() as conn:
        row = conn.execute("""
            SELECT * FROM price_history
            WHERE collection_id = ? AND recorded_at <= ?
            ORDER BY recorded_at DESC LIMIT 1
        """, (collection_id, target_date)).fetchone()
        return dict(row) if row else None


def delete_price_history(collection_id: int, snapshot_id: int = None) -> int:
    """Delete price history for a collection item. If snapshot_id provided, delete only that snapshot."""
    with connect() as conn:
        cursor = conn.cursor()
        if snapshot_id:
            cursor.execute("DELETE FROM price_history WHERE id = ? AND collection_id = ?", (snapshot_id, collection_id))
        else:
            cursor.execute("DELETE FROM price_history WHERE collection_id = ?", (collection_id,))
        return cursor.rowcount


# ============================================================
# Chart Data Generation
# ============================================================

TIMEFRAMES = {
    '1D': 1,
    '7D': 7,
    '1M': 30,
    '3M': 90,
    '6M': 180,
    '1Y': 365,
    'ALL': None
}

def get_chart_data(collection_id: int, timeframe: str = '1M') -> dict:
    """
    Get price chart data for a collection item.
    Returns dict with: timeframe, data_points, current_price, previous_price,
    price_change, pct_change, high, low, average.
    """
    days = TIMEFRAMES.get(timeframe.upper(), 30)
    history = get_price_history(collection_id, days)

    if not history:
        return {
            "timeframe": timeframe,
            "data_points": [],
            "current_price": None,
            "previous_price": None,
            "price_change": 0,
            "pct_change": 0,
            "high": None,
            "low": None,
            "average": None,
            "has_data": False
        }

    # Extract prices and timestamps
    data_points = [
        {"timestamp": h["recorded_at"], "price": h["price"], "source": h["source"]}
        for h in history
    ]

    prices = [h["price"] for h in history]
    current_price = prices[-1]
    previous_price = prices[0] if len(prices) > 1 else current_price
    price_change = current_price - previous_price
    pct_change = (price_change / previous_price * 100) if previous_price > 0 else 0

    return {
        "timeframe": timeframe,
        "data_points": data_points,
        "current_price": current_price,
        "previous_price": previous_price,
        "price_change": round(price_change, 2),
        "pct_change": round(pct_change, 2),
        "high": max(prices),
        "low": min(prices),
        "average": round(sum(prices) / len(prices), 2),
        "has_data": True
    }


def get_portfolio_chart_data(portfolio_id: int, timeframe: str = '1M') -> dict:
    """
    Get aggregated portfolio value chart data over time.
    This requires historical snapshots for all cards in portfolio.
    """
    days = TIMEFRAMES.get(timeframe.upper(), 30)

    with connect() as conn:
        # Get all collections in portfolio with their price history
        collections = conn.execute("""
            SELECT id, card_name, quantity, purchase_price
            FROM collections WHERE portfolio_id = ?
        """, (portfolio_id,)).fetchall()

        if not collections:
            return {"timeframe": timeframe, "data_points": [], "has_data": False}

        # For each day in timeframe, calculate total portfolio value
        # This is a simplified approach - in production you'd want more efficient aggregation
        cutoff = (datetime.now() - timedelta(days=days)).isoformat() if days else None

        # Get all price history for these collections
        collection_ids = [c["id"] for c in collections]
        placeholders = ', '.join(['?'] * len(collection_ids))

        query = f"""
            SELECT ph.collection_id, ph.price, ph.recorded_at, c.quantity, c.card_name
            FROM price_history ph
            JOIN collections c ON c.id = ph.collection_id
            WHERE ph.collection_id IN ({placeholders})
        """
        params = collection_ids

        if cutoff:
            query += " AND ph.recorded_at >= ?"
            params.append(cutoff)

        query += " ORDER BY ph.recorded_at ASC"

        rows = conn.execute(query, params).fetchall()

        if not rows:
            return {"timeframe": timeframe, "data_points": [], "has_data": False}

        # Group by date and calculate portfolio value
        from collections import defaultdict
        daily_values = defaultdict(float)

        for row in rows:
            date_key = row["recorded_at"][:10]  # YYYY-MM-DD
            daily_values[date_key] += row["price"] * row["quantity"]

        # Sort by date
        sorted_dates = sorted(daily_values.keys())
        data_points = [
            {"date": d, "value": round(daily_values[d], 2)}
            for d in sorted_dates
        ]

        values = [dp["value"] for dp in data_points]
        current_value = values[-1] if values else 0
        previous_value = values[0] if len(values) > 1 else current_value

        return {
            "timeframe": timeframe,
            "data_points": data_points,
            "current_value": current_value,
            "previous_value": previous_value,
            "value_change": round(current_value - previous_value, 2),
            "pct_change": round((current_value - previous_value) / previous_value * 100, 2) if previous_value > 0 else 0,
            "high": max(values) if values else 0,
            "low": min(values) if values else 0,
            "has_data": len(data_points) > 0
        }


# ============================================================
# Market Price Tracking (for watchlist and collection)
# ============================================================

def update_market_price_from_scan(collection_id: int, market_price: float, source: str = 'eBay') -> int:
    """
    Record a market price snapshot from scanning.
    Also updates the collection's current market reference if needed.
    """
    # Get collection details for context
    with connect() as conn:
        collection = conn.execute("""
            SELECT condition, language, variant, grading_company, grade
            FROM collections WHERE id = ?
        """, (collection_id,)).fetchone()

    if not collection:
        return 0

    return record_price_snapshot(
        collection_id=collection_id,
        price=market_price,
        source=source,
        condition=collection["condition"] or 'Near Mint',
        language=collection["language"] or '',
        variant=collection["variant"] or '',
        grading_company=collection["grading_company"] or '',
        grade=collection["grade"] or ''
    )


def get_price_trend(collection_id: int, days: int = 30) -> dict:
    """
    Analyze price trend over specified days.
    Returns: trend ('up', 'down', 'stable'), slope, confidence
    """
    history = get_price_history(collection_id, days)

    if len(history) < 2:
        return {"trend": "insufficient_data", "slope": 0, "confidence": 0}

    # Simple linear regression
    n = len(history)
    x = list(range(n))
    y = [h["price"] for h in history]

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return {"trend": "stable", "slope": 0, "confidence": 0}

    slope = numerator / denominator

    # Calculate R-squared for confidence
    y_pred = [y_mean + slope * (x[i] - x_mean) for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    if slope > 0.01:
        trend = "up"
    elif slope < -0.01:
        trend = "down"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "slope": round(slope, 4),
        "confidence": round(r_squared, 3),
        "data_points": n
    }


def cleanup_old_snapshots(collection_id: int, keep_days: int = 365, max_per_day: int = 1) -> int:
    """
    Clean up old price snapshots to prevent database bloat.
    Keeps at most max_per_day snapshots per day for data older than keep_days.
    """
    with connect() as conn:
        cursor = conn.cursor()

        # For data older than keep_days, keep only first snapshot per day
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()

        # Get snapshots older than cutoff grouped by day
        rows = cursor.execute("""
            SELECT id, date(recorded_at) as day
            FROM price_history
            WHERE collection_id = ? AND recorded_at < ?
            ORDER BY recorded_at ASC
        """, (collection_id, cutoff)).fetchall()

        if not rows:
            return 0

        # Group by day and keep only first max_per_day
        from collections import defaultdict
        by_day = defaultdict(list)
        for row in rows:
            by_day[row["day"]].append(row["id"])

        to_delete = []
        for day, ids in by_day.items():
            if len(ids) > max_per_day:
                to_delete.extend(ids[max_per_day:])

        if to_delete:
            placeholders = ', '.join(['?'] * len(to_delete))
            cursor.execute(f"DELETE FROM price_history WHERE id IN ({placeholders})", to_delete)
            return len(to_delete)

        return 0