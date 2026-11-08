# TCG Deal Radar MVP

A local Streamlit dashboard for monitoring eBay single-card listings for Pokémon TCG and One Piece TCG, English and Japanese.

## Included
- Local dashboard and SQLite database
- eBay Browse API app-token authentication and search
- CSV import for market-price references
- Estimated landed-cost comparison (item + shipping + configurable tax)
- 20% default alert threshold
- ntfy push notifications to Android
- Duplicate alert suppression

## Important scope notes
- No TCGplayer API key is assumed. Import permitted market-price data via CSV. This MVP does not scrape TCGplayer.
- This build has a manual **Run scan now** button. The 15-minute interval is a target setting, not an active background scheduler yet. We will add a dedicated worker after API access and matching are validated.
- Card matching is heuristic, not guaranteed. Always inspect the listing before purchase.
- Tax and shipping are estimates. Confirm the actual checkout total.
- API availability, quotas, and permissions depend on eBay developer account approval and current terms.

## Setup: Windows
1. Install Python 3.12+ from https://www.python.org/downloads/ (enable Add Python to PATH).
2. Create an app at https://developer.ebay.com/ and obtain Production App ID (Client ID) and Cert ID (Client Secret). Confirm Browse API access.
3. Extract this ZIP and open PowerShell in the `tcg-deal-radar` folder.
4. Run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

5. Edit `.env` and enter eBay credentials plus an unguessable ntfy topic.
6. Run:

```powershell
streamlit run app.py
```

Open http://localhost:8501.

## Setup: macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, then:
streamlit run app.py
```

## Android notifications
Install ntfy from Google Play, subscribe to the same topic set in `.env`, and keep the topic secret. A public ntfy.sh topic is not private if someone knows its name. For stronger privacy, use an authenticated or self-hosted ntfy server.

## Workflow
1. Add each card variant in Watchlist. Add separate entries for English and Japanese.
2. Download the CSV template in Import prices.
3. Enter the matching language/condition market price and import it.
4. Configure eBay credentials and ntfy topic in `.env`.
5. Click Run scan now.

Example CSV:
```csv
game,card_name,set_name,card_number,language,market_price,condition,source
Pokemon,Lugia V,Silver Tempest,186/195,English,165.00,Near Mint,Manual reference
One Piece,Monkey.D.Luffy,OP05,119,Japanese,75.00,Near Mint,Manual reference
```

## Calculation
Landed cost = (item price + shipping) × (1 + estimated tax rate)

Discount = (market price - landed cost) / market price × 100

Default tax is 8.875% as an editable estimate, not a promise of checkout tax.

## Safety before purchase
Confirm card name, set, number, language, condition, authenticity, seller feedback, shipping, returns, and actual checkout total. An alert is a lead, not a purchase recommendation.
