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
