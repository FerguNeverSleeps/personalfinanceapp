# Finance UI Template (Flask)

This is a **starter template** for a personal finance web app UI (light mode).
It focuses on layout/components: dashboard, transactions, budgets, reports, and bank connections.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open: http://127.0.0.1:5000

## Next steps (when you wire real data)
- Replace the sample data in `app.py` with DB models (SQLite/Postgres).
- Add import endpoints (CSV/CAMT.053/MT940).
- Add an aggregator connector later (Plaid/Enable Banking/etc.).
- Add category rules + budget alerts + notifications.
