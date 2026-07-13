from datetime import datetime
from extensions import db

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    institution = db.Column(db.String(120), nullable=True)

    transactions = db.relationship("Transaction", backref="account", lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    transactions = db.relationship("Transaction", backref="category", lazy=True)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    posted_date = db.Column(db.Date, nullable=False)
    merchant = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(500), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(8), default="EUR")


    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)

    fingerprint = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    import_batch_id = db.Column(db.Integer, db.ForeignKey("import_batch.id"), nullable=True)
    import_batch = db.relationship("ImportBatch", backref=db.backref("transactions", lazy=True))

    __table_args__ = (
        # Prevent duplicates for same account:
        db.UniqueConstraint("account_id", "fingerprint", name="uq_tx_account_fingerprint"),
    )


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Budget is for one category in one month
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    category = db.relationship("Category", backref=db.backref("budgets", lazy=True))

    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1..12

    # how much you allow to spend (positive number)
    limit_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("category_id", "year", "month", name="uq_budget_category_month"),
    )

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # What field to match on
    # e.g. "merchant" or "description"
    match_field = db.Column(db.String(20), nullable=False)

    # How to match: contains (easy) or regex (optional)
    match_type = db.Column(db.String(20), nullable=False, default="contains")

    # Pattern to match
    pattern = db.Column(db.String(255), nullable=False)

    # Which category to set if it matches
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    category = db.relationship("Category", backref=db.backref("rules", lazy=True))

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    priority = db.Column(db.Integer, nullable=False, default=100)  # lower = earlier

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ImportBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    filename = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(50), default="csv", nullable=False)  # csv / api later

    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    account = db.relationship("Account", backref=db.backref("import_batches", lazy=True))

    rows_inserted = db.Column(db.Integer, default=0, nullable=False)
    rows_skipped = db.Column(db.Integer, default=0, nullable=False)
    duplicates = db.Column(db.Integer, nullable=False, default=0)

    note = db.Column(db.String(255), nullable=True)


class BankConnection(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    provider = db.Column(db.String(50), nullable=False)  # enable_banking / bunq / csv
    institution_name = db.Column(db.String(120), nullable=True)

    provider_user_id = db.Column(db.String(120), nullable=True)
    provider_account_id = db.Column(db.String(120), nullable=True)

    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    account = db.relationship("Account", backref=db.backref("bank_connections", lazy=True))

    status = db.Column(db.String(30), nullable=False, default="pending")
    # pending / connected / expired / error / disconnected

    consent_expires_at = db.Column(db.DateTime, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)






