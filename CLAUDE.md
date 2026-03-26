# CLAUDE.md

## Project overview
This project is an Amazon/Rakuten arbitrage research tool.

Backend: FastAPI
Frontend: React + TypeScript
Database: PostgreSQL

Main goals:
- Fetch candidate ASINs from Keepa
- Get Amazon prices and fees
- Search Rakuten items
- Calculate profit and ROI
- Save snapshots
- Show candidates in UI

## Working rules
- One session, one theme
- First, inspect current state only
- Always specify target files
- Show diff plan before editing
- After implementation, run pytest
- Start a new thread after one theme is closed
- Use only necessary logs/snippets
- Extra usage is the last resort

## Safety rules
- Never commit secrets
- Never edit .env directly without explicit instruction
- Ask before changing profit / fee / pass_filter logic
- Ask before changing credential handling
- Prefer minimal diffs
- Do not touch unused files unless explicitly asked

## Important files
- amazon_fee.py
- price_calculation.py
- batch_runner.py
- main.py
- keepa_client.py
- get_keepa_prices.py
- rakuten_client.py
- spapi_client.py
- app/schemas.py
- app/db.py
- app/repository.py
- app/main_fastapi.py

## Notes
- fee=None must never be treated as 0
- pass_filter must stay on the safe side
- rakuten_client_jan.py should not be changed unless confirmed in use
- All requests.get calls must include timeout=(10, 30); never add a call without it
- RAKUTEN_SLEEP_TIME is a float (e.g. 0.2); always read with float(), never int()
- search_rakuten_product_api and search_ichiba_from_product have no retry logic; 429 is absorbed by except Exception