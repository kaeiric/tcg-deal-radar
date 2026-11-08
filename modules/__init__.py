"""
TCG Deal Radar - Modules Package
"""
from modules.database import (
    init_db, get_cards, add_card, save_price, get_listings, get_alert_count,
    latest_prices, save_listing, was_alerted, record_alert
)
from modules.scanner import run_scan
from modules.ebay_scanner import search_ebay, build_query, normalize_item
from modules.card_matcher import match_score, likely_excluded, language_compatible
from modules.price_engine import calculate_landed_cost, discount_percent
from modules.notification import send_ntfy

# Phase 1: Collection Management & Portfolios
from modules.collection import (
    add_card as add_collection_card,
    get_card, get_cards, update_card, delete_card,
    get_collection_stats, get_cards_by_set, search_cards,
    get_valid_conditions, get_valid_languages, get_valid_variants,
    get_valid_grading_companies, get_valid_sealed_types,
    VALID_CONDITIONS, VALID_LANGUAGES, VALID_VARIANTS,
    VALID_GRADING_COMPANIES, VALID_SEALED_TYPES
)
from modules.portfolio import (
    create_portfolio, get_portfolios, get_portfolio,
    update_portfolio, delete_portfolio, get_portfolio_summary,
    move_card, copy_card, bulk_move_cards, bulk_copy_cards, bulk_delete_cards,
    ensure_default_portfolio
)
from modules.price_history import (
    record_price_snapshot, get_price_history, get_latest_price,
    get_price_at_date, delete_price_history, get_chart_data,
    get_portfolio_chart_data, update_market_price_from_scan,
    get_price_trend, cleanup_old_snapshots, TIMEFRAMES
)
from modules.watchlist import (
    add_watchlist_item, get_watchlist, get_watchlist_item,
    update_watchlist_item, delete_watchlist_item,
    check_watchlist_alerts, send_watchlist_notification,
    check_significant_movements
)
from modules.set_tracker import (
    create_set, get_sets, get_set, update_set, delete_set,
    add_set_card, get_set_cards, update_set_card, delete_set_card,
    bulk_add_set_cards, get_set_completion, get_all_set_completions,
    import_pokemon_sets_from_api, import_pokemon_set_cards_from_api,
    import_onepiece_sets_from_csv, import_onepiece_set_cards_from_csv
)
from modules.trade import (
    evaluate_trade, record_trade, get_trades, get_trade,
    delete_trade, get_trade_stats, quick_evaluate
)
from modules.migrate import run_migration, verify_migration

__all__ = [
    # Original modules
    'init_db', 'get_cards', 'add_card', 'save_price', 'get_listings', 'get_alert_count',
    'latest_prices', 'save_listing', 'was_alerted', 'record_alert',
    'run_scan', 'search_ebay', 'build_query', 'normalize_item',
    'match_score', 'likely_excluded', 'language_compatible',
    'calculate_landed_cost', 'discount_percent', 'send_ntfy',
    # Collection management
    'add_collection_card', 'get_card', 'get_cards', 'update_card', 'delete_card',
    'get_collection_stats', 'get_cards_by_set', 'search_cards',
    'get_valid_conditions', 'get_valid_languages', 'get_valid_variants',
    'get_valid_grading_companies', 'get_valid_sealed_types',
    'VALID_CONDITIONS', 'VALID_LANGUAGES', 'VALID_VARIANTS',
    'VALID_GRADING_COMPANIES', 'VALID_SEALED_TYPES',
    # Portfolios
    'create_portfolio', 'get_portfolios', 'get_portfolio',
    'update_portfolio', 'delete_portfolio', 'get_portfolio_summary',
    'move_card', 'copy_card', 'bulk_move_cards', 'bulk_copy_cards', 'bulk_delete_cards',
    'ensure_default_portfolio',
    # Price history
    'record_price_snapshot', 'get_price_history', 'get_latest_price',
    'get_price_at_date', 'delete_price_history', 'get_chart_data',
    'get_portfolio_chart_data', 'update_market_price_from_scan',
    'get_price_trend', 'cleanup_old_snapshots', 'TIMEFRAMES',
    # Watchlist
    'add_watchlist_item', 'get_watchlist', 'get_watchlist_item',
    'update_watchlist_item', 'delete_watchlist_item',
    'check_watchlist_alerts', 'send_watchlist_notification',
    'check_significant_movements',
    # Set tracker
    'create_set', 'get_sets', 'get_set', 'update_set', 'delete_set',
    'add_set_card', 'get_set_cards', 'update_set_card', 'delete_set_card',
    'bulk_add_set_cards', 'get_set_completion', 'get_all_set_completions',
    'import_pokemon_sets_from_api', 'import_pokemon_set_cards_from_api',
    'import_onepiece_sets_from_csv', 'import_onepiece_set_cards_from_csv',
    # Trade analyzer
    'evaluate_trade', 'record_trade', 'get_trades', 'get_trade',
    'delete_trade', 'get_trade_stats', 'quick_evaluate',
    # Migration
    'run_migration', 'verify_migration',
]