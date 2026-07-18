from __future__ import annotations
import re
from flask import Flask, render_template
import os
from flask import request, redirect, url_for, render_template, flash, abort
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Account, Transaction, Category, Budget, Rule, ImportBatch, BankConnection  # adjust import path if needed
from datetime import date, datetime
from sqlalchemy import func, case, and_, or_
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv


#to help with organization and less lines of code in the app.py
# we have separated the helper functions
# into a separate folder of services and importing them here
from services.import_service import (
    load_rows_auto,
    normalize_transaction_row,
    clean_note,
    normalize_merchant_name,
    detect_bank_from_text,
    tx_fingerprint,
)

from services.rule_service import (
    apply_rules_to_row,
    guess_category,
)

from services.report_service import month_bounds

#load your .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

app.config["ENABLE_DEV_TOOLS"] = (
    os.environ.get("ENABLE_DEV_TOOLS", "false").lower() == "true"
)

app.config["DEBUG"] = (
    os.environ.get("FLASK_DEBUG", "false").lower() == "true"
)

# SQLite locally, but allow Postgres later via DATABASE_URL
db_url = os.environ.get("DATABASE_URL", "sqlite:///finance.db")
# Render/Fly often provide postgres URLs starting with postgres://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#db = SQLAlchemy(app)
db.init_app(app)
#app = Flask(__name__)
#app.secret_key = "dev"  # replace for production


# @dataclass
# class Tx:
#     date: str
#     merchant: str
#     meta: str
#     category: str
#     amount: float
#     account: str
#
#
# def sample_transactions() -> list[Tx]:
#     return [
#         Tx(str(date.today()), "Albert Heijn", "Grocery store · Card payment", "Groceries", -23.45, "ABN •••• 1204"),
#         Tx(str(date.today()), "NS", "Train · OV-chipkaart", "Transport", -9.20, "ING •••• 8841"),
#         Tx(str(date.today()), "Spotify", "Subscription", "Subscriptions", -10.99, "bunq •••• 4412"),
#         Tx(str(date.today()), "Salary", "Employer payout", "Income", 3250.00, "ABN •••• 1204"),
#         Tx(str(date.today()), "Zara", "Clothing", "Shopping", -79.90, "ING •••• 8841"),
#     ]


@app.context_processor
def inject_now():
    return {"current_year": date.today().year}

@app.get("/")
def dashboard():
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))

    # start_date = date(year, month, 1)
    # last_day = calendar.monthrange(year, month)[1]
    # end_date = date(year, month, last_day)
    start_date, next_month = month_bounds(year, month)

    # ---- totals (optional, if you want the metrics cards) ----
    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0))\
        .filter(Transaction.posted_date >= start_date,
                #Transaction.posted_date <= end_date,
                Transaction.posted_date < next_month,
                Transaction.amount > 0).scalar()

    expenses = db.session.query(func.coalesce(func.sum(-Transaction.amount), 0))\
        .filter(Transaction.posted_date >= start_date,
                #Transaction.posted_date <= end_date,
                Transaction.posted_date < next_month,
                Transaction.amount < 0).scalar()

    net = income - expenses
    savings_rate = (float(net) / float(income) * 100) if income and float(income) != 0 else 0.0

    # ---- budgets for this month (this is the key part) ----
    budgets = (
        db.session.query(Budget, Category)
        .join(Category, Category.id == Budget.category_id)
        .filter(Budget.year == year, Budget.month == month)
        .all()
    )

    # spent per category for the month (expenses only)
    spent_rows = (
        db.session.query(
            Transaction.category_id,
            func.coalesce(func.sum(
                case((Transaction.amount < 0, -Transaction.amount), else_=0)
            ), 0).label("spent")
        )
        .filter(Transaction.posted_date >= start_date,
                #Transaction.posted_date <= end_date,
                Transaction.posted_date < next_month,
                Transaction.category_id.isnot(None))
        .group_by(Transaction.category_id)
        .all()
    )
    spent_map = {cid: float(spent) for cid, spent in spent_rows}

    budget_cards = []
    for b, c in budgets:
        limit_amt = float(b.limit_amount or 0)
        spent = spent_map.get(c.id, 0.0)
        pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0

        status = None
        if limit_amt > 0 and spent >= limit_amt:
            status = "overspent"
        elif limit_amt > 0 and pct >= 80:
            status = "near"

        budget_cards.append({
            "category": c.name,
            "spent": spent,
            "limit": limit_amt,
            "pct": pct,
            "status": status,
        })

    # Optional: sort so overspent/near-limit appear first
    def sort_key(x):
        if x["status"] == "overspent": return (0, -x["pct"])
        if x["status"] == "near": return (1, -x["pct"])
        return (2, -x["pct"])
    budget_cards.sort(key=sort_key)

    # recent tx (example)
    recent_txs = Transaction.query.order_by(Transaction.posted_date.desc()).limit(8).all()

    return render_template(
        "dashboard.html",
        year=year, month=month,
        income=income, expenses=expenses, net=net, savings_rate=savings_rate,
        budget_cards=budget_cards,
        recent=recent_txs
    )

@app.get("/transactions")
def transactions():
    # --- read filters from URL ---
    view = request.args.get("view", "all")                # all | uncat
    search_q = (request.args.get("q") or "").strip()      # free-text
    account_id = request.args.get("account_id", type=int) # optional
    category_raw = (request.args.get("category_id") or "").strip()  # "", "none", or id string
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # --- base query ---
    query = Transaction.query

    # view filter (keeps your existing behavior)
    if view == "uncat":
        query = query.filter(Transaction.category_id.is_(None))

    # account filter
    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    # category filter (optional; independent of view)
    # category_id=none => uncategorized only
    if category_raw:
        if category_raw == "none":
            query = query.filter(Transaction.category_id.is_(None))
        else:
            try:
                category_id = int(category_raw)
                query = query.filter(Transaction.category_id == category_id)
            except ValueError:
                pass

    # search filter
    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            or_(
                Transaction.merchant.ilike(like),
                Transaction.description.ilike(like),
            )
        )

    # ordering
    query = query.order_by(Transaction.posted_date.desc(), Transaction.id.desc())

    # pagination (Flask-SQLAlchemy)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = pagination.items

    categories = Category.query.order_by(Category.name.asc()).all()
    accounts = Account.query.order_by(Account.name.asc()).all()

    return render_template(
        "transactions.html",
        transactions=transactions,
        pagination=pagination,
        view=view,
        search_q=search_q,
        account_id=account_id,
        category_id=category_raw,
        categories=categories,
        accounts=accounts,
        clean_note=clean_note,
    )

@app.post("/transactions/<int:tx_id>/category")
def set_tx_category(tx_id: int):
    tx = Transaction.query.get_or_404(tx_id)

    category_id = (request.form.get("category_id") or "").strip()

    if category_id in ("", "none"):
        tx.category_id = None
    else:
        try:
            tx.category_id = int(category_id)
        except ValueError:
            abort(400, "Invalid category_id")

    db.session.commit()
    flash("Category updated.", "success")
    return redirect(url_for("transactions"))





@app.get("/connections")
def connections():
    account_rows = (
        db.session.query(
            Account,
            func.count(Transaction.id).label("tx_count")
        )
        .outerjoin(Transaction, Transaction.account_id == Account.id)
        .group_by(Account.id)
        .order_by(Account.name.asc())
        .all()
    )

    connections = (
        BankConnection.query
        .order_by(BankConnection.created_at.desc())
        .all()
    )

    return render_template(
        "connections.html",
        rows=account_rows,
        connections=connections
    )

@app.post("/connections/dev-connect")
def dev_connect_bank():
    if not app.config["ENABLE_DEV_TOOLS"]:
        abort(404)
    provider = (request.form.get("provider") or "enable_banking").strip()
    institution_name = (request.form.get("institution_name") or "").strip()
    account_id_raw = (request.form.get("account_id") or "").strip()

    account = None
    if account_id_raw:
        account = Account.query.get(int(account_id_raw))

    if not institution_name:
        flash("Institution name is required.", "error")
        return redirect(url_for("connections"))

    conn = BankConnection(
        provider=provider,
        institution_name=institution_name,
        provider_user_id="dev-user",
        provider_account_id=f"dev-{institution_name.lower().replace(' ', '-')}",
        account_id=account.id if account else None,
        status="connected",
        last_sync_at=datetime.utcnow(),
    )

    db.session.add(conn)
    db.session.commit()

    flash(f"Connected {institution_name} (dev mode).", "success")
    return redirect(url_for("connections"))

#indicate if bank account is disconnected
@app.post("/connections/<int:connection_id>/disconnect")
def disconnect_connection(connection_id):
    if not app.config["ENABLE_DEV_TOOLS"]:
        abort(404)
    conn = BankConnection.query.get_or_404(connection_id)
    conn.status = "disconnected"
    db.session.commit()

    flash(f"Disconnected {conn.institution_name}.", "success")
    return redirect(url_for("connections"))

#This is a temporary fake sync route to test bank connections
@app.post("/connections/<int:connection_id>/sync")
def sync_connection(connection_id):
    if not app.config["ENABLE_DEV_TOOLS"]:
        abort(404)

    conn = BankConnection.query.get_or_404(connection_id)

    if conn.status != "connected":
        flash("Only connected accounts can be synced.", "error")
        return redirect(url_for("connections"))

    conn.last_sync_at = datetime.utcnow()
    db.session.commit()

    flash(f"Sync completed for {conn.institution_name}.", "success")
    return redirect(url_for("connections"))

@app.post("/connections/<int:connection_id>/reconnect")
def reconnect_connection(connection_id):
    if not app.config["ENABLE_DEV_TOOLS"]:
        abort(404)
    conn = BankConnection.query.get_or_404(connection_id)
    conn.status = "connected"
    db.session.commit()
    flash(f"Reconnected {conn.institution_name}.", "success")
    return redirect(url_for("connections"))

@app.post("/accounts/add")
def add_account():
    name = (request.form.get("name") or "").strip()
    institution = (request.form.get("institution") or "").strip() or None

    if not name:
        flash("Account name is required.", "error")
        return redirect(url_for("connections"))

    exists = Account.query.filter_by(name=name).first()
    if exists:
        flash("An account with that name already exists.", "error")
        return redirect(url_for("connections"))

    a = Account(name=name, institution=institution)
    db.session.add(a)
    db.session.commit()
    flash("Account added.", "success")
    return redirect(url_for("connections"))


@app.post("/accounts/<int:account_id>/rename")
def rename_account(account_id):
    a = Account.query.get_or_404(account_id)
    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("connections"))

    a.name = new_name
    db.session.commit()
    flash("Account renamed.", "success")
    return redirect(url_for("connections"))


@app.post("/accounts/<int:account_id>/delete")
def delete_account(account_id):
    a = Account.query.get_or_404(account_id)

    # safer for now: keep transactions, just detach them
    Transaction.query.filter_by(account_id=a.id).update({"account_id": None})

    db.session.delete(a)
    db.session.commit()
    flash("Account deleted (transactions kept).", "success")
    return redirect(url_for("connections"))
@app.get("/import")
def import_page():
    account_id = request.args.get("account_id", type=int)
    accounts = Account.query.order_by(Account.name.asc()).all()
    return render_template("import.html", accounts=accounts, account_id=account_id)

@app.post("/import")
def import_csv():
    f = request.files.get("file")
    if not f:
        flash("No file uploaded", "error")
        return redirect(url_for("import_page"))

    account_name = (request.form.get("account_name") or "").strip()
    account = None

    rows = load_rows_auto(f)
    account_id = request.form.get("account_id") or ""
    account_id = int(account_id) if account_id.strip() else None

    # 1) Explicit account selection wins
    if account_id:
        account = Account.query.get(account_id)

    # 2) Else use typed account name
    # Create/find account if we have a name (manual or auto)
    elif account_name:
        account = Account.query.filter_by(name=account_name).first()
        if not account:
            account = Account(name=account_name)
            db.session.add(account)
            #keeps the entire import operation inside one database transaction.
            db.session.flush()

    # Auto-detect account if user didn't provide one
    elif rows:
        # Try to detect from first ~10 rows to be safe
        probe = " ".join(
            str(r.get("description") or r.get("omschrijving") or r.get("details") or "")
            for r in rows[:10]
        )
        #This ensures automatically detected
        # transactions are actually connected to the detected account.
        # And we actually use the Account Object
        bank = detect_bank_from_text(probe)

        if bank:
            account = Account.query.filter_by(
                name=bank
            ).first()

            if not account:
                account = Account(
                    name=bank,
                    institution=bank,
                )
                db.session.add(account)
                db.session.flush()

    # Create the batch BEFORE looping
    batch = ImportBatch(
        filename=getattr(f, "filename", None),
        source="csv",
        account_id=account.id if account else None,
        duplicates=0
    )
    db.session.add(batch)
    db.session.flush()  # gives batch.id without commit


    inserted = 0
    skipped = 0
    duplicates = 0

    for r in rows:
        nr = normalize_transaction_row(r)

        # Invalid or incomplete row
        if not nr:
            skipped += 1
            continue

        nr["description"] = clean_note(
            nr.get("description", "")
        )
        nr["merchant"] = normalize_merchant_name(
            nr.get("merchant")
        )

        # Use one verified fingerprint implementation
        fp = tx_fingerprint(
            account.id if account else None,
            nr["posted_date"],
            nr["amount"],
            nr["merchant"],
            nr["description"],
        )

        # Skip already stored transaction
        exists = Transaction.query.filter_by(
            fingerprint=fp
        ).first()

        if exists:
            duplicates += 1
            continue

        # Try user rules first
        matched_category = apply_rules_to_row(
            nr["merchant"],
            nr["description"],
        )

        if matched_category:
            category = matched_category
        else:
            category_name = guess_category(
                nr["merchant"],
                nr["description"],
            )

            if category_name == "Uncategorized":
                category = None
            else:
                category = Category.query.filter_by(
                    name=category_name
                ).first()

                if not category:
                    category = Category(name=category_name)
                    db.session.add(category)
                    db.session.flush()

        tx = Transaction(
            posted_date=nr["posted_date"],
            merchant=nr["merchant"],
            description=nr["description"],
            amount=nr["amount"],
            currency=nr["currency"],
            account_id=account.id if account else None,
            category_id=category.id if category else None,
            fingerprint=fp,
            import_batch_id=batch.id,
        )

        try:
            # Savepoint: if this row fails, do not rollback
            # the complete import batch.
            with db.session.begin_nested():
                db.session.add(tx)
                db.session.flush()

            inserted += 1

        except IntegrityError:
            duplicates += 1

        # store stats on the batch
    batch.rows_inserted = inserted
    batch.rows_skipped = skipped
    batch.duplicates = duplicates

    db.session.commit()
    flash(f"Imported {inserted} transactions. Skipped {skipped}. Duplicates {duplicates}.", "success")
    return redirect(url_for("transactions"))

@app.get("/imports")
def imports_page():
    batches = ImportBatch.query.order_by(ImportBatch.created_at.desc()).all()

    # Add tx_count per batch (how many transactions exist for this batch) (SQLite friendly)
    for b in batches:
        b.tx_count = db.session.query(func.count(Transaction.id)) \
            .filter(Transaction.import_batch_id == b.id) \
            .scalar()

    return render_template("imports.html", batches=batches)

@app.post("/imports/<int:batch_id>/undo")
def undo_import(batch_id):
    batch = ImportBatch.query.get_or_404(batch_id)

    tx_count = Transaction.query.filter_by(import_batch_id=batch.id).count()

    if tx_count == 0:
        db.session.delete(batch)
        db.session.commit()
        flash("Batch removed (no transactions were imported).", "success")
        return redirect(url_for("imports_page"))

    Transaction.query.filter_by(import_batch_id=batch.id).delete(synchronize_session=False)
    db.session.delete(batch)
    db.session.commit()

    flash(f"Import undone (deleted {tx_count} transactions).", "success")
    return redirect(url_for("imports_page"))

@app.post("/dev/reset-transactions")
def dev_reset_transactions():
    if not app.config["ENABLE_DEV_TOOLS"]:
        abort(404)

    try:
        # Transactions reference import batches, so delete them first.
        Transaction.query.delete(synchronize_session=False)

        # Clear old import-history records for a clean demo.
        ImportBatch.query.delete(synchronize_session=False)

        db.session.commit()

        flash(
            "Transactions and import history were cleared. "
            "Rules, categories, budgets, and accounts were preserved.",
            "success",
        )

    except Exception:
        db.session.rollback()
        flash("The demo data could not be reset.", "error")

    return redirect(url_for("transactions"))

@app.get("/categories")
def categories_page():
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("categories.html", categories=categories)


#this is to recategorize the empty records in transactions
@app.post("/dev/recategorize")
def dev_recategorize():
    txs = Transaction.query.order_by(Transaction.posted_date.desc()).all()

    updated = 0
    for tx in txs:
        # Only fill missing categories (safe)
        if tx.category_id:
            continue

        cat_name = guess_category(tx.merchant, tx.description)
        if cat_name == "Uncategorized":
            continue

        category = Category.query.filter_by(name=cat_name).first()
        if not category:
            category = Category(name=cat_name)
            db.session.add(category)
            db.session.flush() #flush() sends pending changes to the database without completing the full transaction.

        tx.category_id = category.id
        updated += 1

    db.session.commit()
    flash(f"Auto-categorized {updated} transactions.", "success")
    return redirect(url_for("transactions"))


@app.post("/categories/create")
def create_category():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Category name cannot be empty.", "error")
        return redirect(url_for("transactions"))

    existing = Category.query.filter_by(name=name).first()
    if existing:
        flash("Category already exists.", "error")
        return redirect(url_for("transactions"))

    if name.lower() == "uncategorized":
        flash("You can't create a category named 'Uncategorized'. Use the default option.", "error")
        return redirect(url_for("transactions"))

    db.session.add(Category(name=name))
    db.session.commit()
    flash(f"Created category: {name}", "success")
    return redirect(url_for("categories_page"))

#Now we will be able to create/rename/and delete categories in the interface
@app.post("/categories/<int:cat_id>/rename")
def rename_category(cat_id: int):
    cat = Category.query.get_or_404(cat_id)
    new_name = (request.form.get("new_name") or "").strip()

    if not new_name:
        flash("New name cannot be empty.", "error")
        return redirect(url_for("transactions"))

    dup = Category.query.filter_by(name=new_name).first()
    if dup and dup.id != cat.id:
        flash("A category with that name already exists.", "error")
        return redirect(url_for("transactions"))

    cat.name = new_name
    db.session.commit()
    flash("Category renamed.", "success")
    return redirect(url_for("categories_page"))


@app.post("/categories/<int:cat_id>/delete")
def delete_category(cat_id: int):
    category = Category.query.get_or_404(cat_id)

    try:
        # Keep transactions but mark them as Uncategorized.
        transaction_count = Transaction.query.filter_by(
            category_id=category.id
        ).count()

        Transaction.query.filter_by(
            category_id=category.id
        ).update(
            {"category_id": None},
            synchronize_session=False,
        )

        # Rules cannot exist without a category.
        rule_count = Rule.query.filter_by(
            category_id=category.id
        ).count()

        Rule.query.filter_by(
            category_id=category.id
        ).delete(
            synchronize_session=False
        )

        # Budgets also cannot exist without a category.
        budget_count = Budget.query.filter_by(
            category_id=category.id
        ).count()

        Budget.query.filter_by(
            category_id=category.id
        ).delete(
            synchronize_session=False
        )

        category_name = category.name

        db.session.delete(category)
        db.session.commit()

        flash(
            f'Deleted category "{category_name}". '
            f"{transaction_count} transactions were set to Uncategorized, "
            f"{rule_count} rules were removed, and "
            f"{budget_count} budgets were removed.",
            "success",
        )

    except IntegrityError:
        db.session.rollback()

        flash(
            "The category could not be deleted because it is still "
            "referenced by another record.",
            "error",
        )

    return redirect(url_for("categories_page"))

@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    # pick month (default: current)
    today = date.today()

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))

    # start_date = date(year, month, 1)
    # last_day = calendar.monthrange(year, month)[1]
    # end_date = date(year, month, last_day)
    start_date, next_month = month_bounds(year, month)

    categories = Category.query.filter(Category.name != "Transfers").order_by(Category.name).all()


    # POST = save budget limits
    if request.method == "POST":
        for c in categories:
            key = f"limit_{c.id}"
            if key not in request.form:
                continue

            raw = (request.form.get(key) or "").strip()
            if raw == "":
                continue

            # allow "123,45" too
            raw = raw.replace(",", ".")
            try:
                limit_val = Decimal(raw)
            except:
                continue

            b = Budget.query.filter_by(category_id=c.id, year=year, month=month).first()
            if not b:
                b = Budget(category_id=c.id, year=year, month=month, limit_amount=limit_val)
                db.session.add(b)
            else:
                b.limit_amount = limit_val

        db.session.commit()
        flash("Budgets saved.", "success")
        return redirect(url_for("budgets", year=year, month=month))

    # --- Compute spent per category (expenses only) ---
    # spent = sum of negative amounts, turned positive
    spent_rows = (
        db.session.query(
            Transaction.category_id,
            func.sum(
                case(
                    (Transaction.amount < 0, -Transaction.amount),
                    else_=0
                )
            ).label("spent")
        )
        .filter(
            Transaction.posted_date >= start_date,
            #Transaction.posted_date <= end_date,
            Transaction.posted_date < next_month,
            Transaction.category_id.isnot(None),
        )
        .group_by(Transaction.category_id)
        .all()
    )
    spent_map = {cid: (spent if spent is not None else Decimal("0")) for cid, spent in spent_rows}
    # budgets for this month
    budget_rows = Budget.query.filter_by(year=year, month=month).all()
    budget_map = {b.category_id: b for b in budget_rows}

    # build view rows
    rows = []
    for c in categories:
        spent = spent_map.get(c.id, Decimal("0"))
        limit_amt = budget_map.get(c.id).limit_amount if c.id in budget_map else Decimal("0")

        remaining = limit_amt - spent
        pct = int((spent / limit_amt) * 100) if limit_amt and limit_amt > 0 else 0
        pct = min(pct, 999)

        rows.append({
            "category": c,
            "spent": spent,
            "limit": limit_amt,
            "remaining": remaining,
            "pct": pct,
            "over": spent > limit_amt if limit_amt > 0 else False
        })

    return render_template("budgets.html", rows=rows, year=year, month=month)

@app.get("/reports")
def reports():
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    trend_n = int(request.args.get("trend", 6))  #  3/6/12 toggle

    # start_date = date(year, month, 1)
    # last_day = calendar.monthrange(year, month)[1]
    # end_date = date(year, month, last_day)
    start_date, next_month = month_bounds(year, month)

    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)) \
        .filter(
            Transaction.posted_date >= start_date,
            Transaction.posted_date <= next_month,
            Transaction.amount > 0
        ).scalar()

    expenses = db.session.query(func.coalesce(func.sum(-Transaction.amount), 0)) \
        .filter(
            Transaction.posted_date >= start_date,
            #Transaction.posted_date <= end_date,
            Transaction.posted_date < next_month,
            Transaction.amount < 0
        ).scalar()

    # Convert Decimals -> float so Jinja formatting is easy and consistent
    income = float(income or 0)
    expenses = float(expenses or 0)
    net = float(income - expenses)

    rows = db.session.query(
        Category.name.label("name"),
        func.coalesce(func.sum(-Transaction.amount), 0).label("spent")
    ).join(Transaction, Transaction.category_id == Category.id) \
     .filter(
         Transaction.posted_date >= start_date,
         #Transaction.posted_date <= end_date,
        Transaction.posted_date < next_month,
         Transaction.amount < 0
     ) \
     .group_by(Category.name) \
     .order_by(func.sum(-Transaction.amount).desc()) \
     .all()

    by_category = [{"name": r.name, "spent": float(r.spent or 0)} for r in rows]

    # --- existing monthly summary code stays the same ---
    # income, expenses, net, by_category ... (your current logic)

    # ---------------- TREND SERIES (last N months ending selected month) ----------------
    # helper to step back months
    def add_months(y, m, delta):
        m2 = m + delta
        y2 = y + (m2 - 1) // 12
        m2 = (m2 - 1) % 12 + 1
        return y2, m2

    months = []
    for i in range(trend_n - 1, -1, -1):  # oldest -> newest
        y2, m2 = add_months(year, month, -i)
        months.append((y2, m2))

    labels = [f"{y2:04d}-{m2:02d}" for y2, m2 in months]

    dialect = db.engine.dialect.name

    # Group transactions by YYYY-MM
    if dialect == "sqlite":
        ym = func.strftime("%Y-%m", Transaction.posted_date)
    else:
        # Postgres
        ym = func.to_char(func.date_trunc("month", Transaction.posted_date), "YYYY-MM")

    trend_rows = (
        db.session.query(
            ym.label("ym"),
            func.coalesce(func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)), 0).label("income"),
            func.coalesce(func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0)), 0).label("expenses"),
        )
        .group_by("ym")
        .all()
    )

    trend_map = {r.ym: (float(r.income), float(r.expenses)) for r in trend_rows}

    trend_income = []
    trend_expenses = []
    net_series = []

    for lab in labels:
        inc, exp = trend_map.get(lab, (0.0, 0.0))
        trend_income.append(inc)
        trend_expenses.append(exp)
        net_series.append(inc - exp)

    # Optional: trim leading months that are all-zero (keeps your “clean” look)
    while labels and trend_income[0] == 0 and trend_expenses[0] == 0:
        labels.pop(0)
        trend_income.pop(0)
        trend_expenses.pop(0)
        net_series.pop(0)

    return render_template(
        "reports.html",
        year=year, month=month,
        income=income, expenses=expenses, net=net,
        by_category=by_category,
        trend_labels=labels,
        trend_income=trend_income,
        trend_expenses=trend_expenses,
        trend_net=net_series,
        trend_n=trend_n,
    )

@app.get("/rules")
def rules_page():
    rules = Rule.query.order_by(Rule.priority.asc(), Rule.id.asc()).all()
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("rules.html", rules=rules, categories=categories)

@app.post("/rules/from_tx/<int:tx_id>")
def rule_from_tx(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    match_field = request.form.get("match_field", "merchant")
    match_type = request.form.get("match_type", "contains")
    pattern = (request.form.get("pattern") or "").strip()
    category_id = int(request.form.get("category_id"))
    priority = int(request.form.get("priority") or 100)
    apply_existing = request.form.get("apply_existing") == "1"

    if not pattern:
        flash("Pattern cannot be empty.", "error")
        return redirect(url_for("transactions"))

    rule = Rule(
        match_field=match_field,
        match_type=match_type,
        pattern=pattern,
        category_id=category_id,
        priority=priority,
        is_active=True,
    )
    db.session.add(rule)

    # Optional: apply to existing transactions
    updated = 0
    if apply_existing and match_type == "contains":
        like = f"%{pattern}%"
        if match_field == "merchant":
            base = Transaction.query.filter(Transaction.merchant.ilike(like))
        else:
            base = Transaction.query.filter(Transaction.description.ilike(like))

        # safest default: only fill uncategorized
        base = base.filter(Transaction.category_id.is_(None))

        updated = base.update({Transaction.category_id: category_id}, synchronize_session=False)

    db.session.commit()

    if apply_existing:
        flash(f"Rule created and applied to {updated} existing transactions.", "success")
    else:
        flash("Rule created.", "success")

    return redirect(url_for("transactions"))

@app.post("/rules/add")
def add_rule():
    match_field = (request.form.get("match_field") or "merchant").strip()
    match_type = (request.form.get("match_type") or "contains").strip()
    pattern = (request.form.get("pattern") or "").strip()
    category_id = int(request.form.get("category_id"))
    priority = int(request.form.get("priority") or 100)
    apply_existing = request.form.get("apply_existing") == "1"

    if not pattern:
        flash("Pattern is required.", "error")
        return redirect(url_for("rules_page"))

    # 1) Create & save rule first
    r = Rule(
        match_field=match_field,
        match_type=match_type,
        pattern=pattern,
        category_id=category_id,
        priority=priority,
        is_active=True
    )
    db.session.add(r)
    db.session.commit()

    # 2) Optionally apply this NEW rule to existing txs
    if apply_existing:
        txs = Transaction.query.all()
        changed = 0

        for tx in txs:
            haystack = (tx.merchant or "") if r.match_field == "merchant" else (tx.description or "")
            if not haystack:
                continue

            if r.match_type == "contains":
                if r.pattern.lower().strip() in haystack.lower():
                    if tx.category_id != r.category_id:
                        tx.category_id = r.category_id
                        changed += 1
            else:  # regex
                try:
                    if re.search(r.pattern, haystack, flags=re.IGNORECASE):
                        if tx.category_id != r.category_id:
                            tx.category_id = r.category_id
                            changed += 1
                except re.error:
                    pass

        db.session.commit()
        flash(f"Rule added and applied to {changed} transactions.", "success")
    else:
        flash("Rule added.", "success")

    return redirect(url_for("rules_page"))

@app.post("/rules/test")
def test_rule():
    merchant = (request.form.get("merchant") or "").strip()
    description = (request.form.get("description") or "").strip()

    matched = apply_rules_to_row(merchant, description)

    if matched:
        flash(f"Matched category: {matched.name}", "success")
    else:
        flash("No rule matched.", "info")

    return redirect(url_for("rules_page"))


@app.post("/rules/<int:rule_id>/toggle")
def toggle_rule(rule_id):
    r = Rule.query.get_or_404(rule_id)
    r.is_active = not r.is_active
    db.session.commit()
    return redirect(url_for("rules_page"))

@app.post("/rules/<int:rule_id>/delete")
def delete_rule(rule_id):
    r = Rule.query.get_or_404(rule_id)
    db.session.delete(r)
    db.session.commit()
    flash("Rule deleted.", "success")
    return redirect(url_for("rules_page"))

@app.post("/rules/apply")
def apply_rules_bulk():
    txs = Transaction.query.all()
    changed = 0

    for tx in txs:
        matched_category = apply_rules_to_row(tx.merchant, tx.description)
        if matched_category:
            if tx.category_id != matched_category.id:
                tx.category_id = matched_category.id
                changed += 1

    db.session.commit()
    flash(f"Applied rules. Updated {changed} transactions.", "success")
    return redirect(url_for("rules_page"))



with app.app_context():
    db.create_all()





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"],)
