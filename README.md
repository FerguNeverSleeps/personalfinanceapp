# Personal Finance Dashboard

A full-stack personal finance application for importing, organizing, categorizing, and analyzing bank transactions.

The application supports duplicate-safe CSV and Excel imports, rule-based transaction categorization, monthly budgeting, financial reports, and a provider-independent bank connection architecture.

> V1 uses Flask, Jinja, SQLAlchemy, and SQLite.  
> V2 will introduce a React frontend and a Flask REST API.

## Screenshots

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Transactions

![Transactions](docs/screenshots/transactions.png)

### Budgets

![Budgets](docs/screenshots/budgets.png)

### Reports

![Reports](docs/screenshots/reports.png)

## Features

- Import transactions from CSV, TXT, XLS, and XLSX files
- Normalize different bank export formats
- Prevent duplicate transactions using SHA-256 fingerprints
- Associate transactions with financial accounts
- Automatically categorize transactions
- Create custom merchant and description rules
- Prioritize rules when multiple rules match
- Manually update transaction categories
- Search and filter transactions
- Create monthly category budgets
- Track spending, remaining budget, and budget usage
- View monthly income, expenses, net cash flow, and savings rate
- View spending by category
- Compare income, expenses, and net cash flow over time
- Review import history
- Undo successful imports
- Manage accounts and connection-state records

## Technology Stack

### Backend

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Pandas
- python-dateutil

### Frontend

- Jinja
- HTML
- CSS
- JavaScript
- Chart.js

### Database

- SQLite for local development
- PostgreSQL-ready through `DATABASE_URL`

## Architecture

V1 is a server-rendered Flask application.

```text
Browser
   |
   v
Flask routes
   |
   v
Business services
   |
   v
SQLAlchemy models
   |
   v
SQLite / PostgreSQL

## Transaction processing pipeline

CSV / Excel upload
        |
        v
Read and normalize columns
        |
        v
Clean descriptions and merchants
        |
        v
Generate transaction fingerprint
        |
        v
Check for duplicates
        |
        v
Apply custom rules
        |
        v
Apply fallback categorization
        |
        v
Save transaction
        |
        v
Dashboard, budgets, and reports

## Main Database Models

Account — groups transactions by financial account
Transaction — stores individual financial movements
Category — classifies transactions
Rule — automatically assigns categories
Budget — stores category limits by month
ImportBatch — records each import and supports undo
BankConnection — stores provider-independent connection state

## Installation

### 1. Clone the repository

git clone https://github.com/FerguNeverSleeps/personalfinanceapp.git
cd personalfinanceapp

### 2. Create a virtual environment

#### Windows:

py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1

#### macOS/Linux:

python3 -m venv venv
source venv/bin/activate

### 3. Install dependencies

python -m pip install -r requirements.txt

### 4. Configure environment variables

Copy .env.example to .env and update the values.

SECRET_KEY=replace-with-a-random-secret
DATABASE_URL=sqlite:///finance.db
FLASK_DEBUG=true
ENABLE_DEV_TOOLS=false

### 5. Run the application

python app.py

Open:

http://127.0.0.1:5000

## Development Tools

Some potentially destructive or simulated features are controlled by:

ENABLE_DEV_TOOLS=true

These include development-only actions such as resetting transactions and simulating bank connection states.

Development tools should remain disabled in public deployments.

## Testing

Run the automated tests with:

pytest

The project tests cover areas such as:

transaction duplicate detection;
invalid import rows;
rule priority;
monthly date filtering;
budget calculations;
import undo behavior.

A manual V1 checklist is available in:

docs/V1_TEST_CHECKLIST.md

## Privacy and Data Safety

Real bank statements, database files, account identifiers, API credentials, and private keys are excluded from Git.

The repository should only use anonymized demonstration data and screenshots.

## Current Limitations

The application is designed primarily as a single-user system
User authentication has not yet been implemented
Bank connections are currently represented through a provider-independent architecture and development workflow
Live PSD2 authorization and transaction synchronization are not yet implemented
SQLite is used locally
Automated test coverage is still being expanded
