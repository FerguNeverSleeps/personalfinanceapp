import io
import re
from typing import Optional

import pandas as pd

from decimal import Decimal
from dateutil import parser as dateparser


from datetime import date
import hashlib


# helper classes to help proccess import files
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _pick(d: dict, keys: list[str]) -> Optional[str]:
    # pick first non-empty from possible column names
    for k in keys:
        if k in d and str(d[k]).strip() not in ("", "nan", "None"):
            return str(d[k]).strip()
    return None

def load_rows_auto(file_storage) -> list[dict]:
    """
    Reads CSV/XLS/XLSX/TXT and returns a list of dict rows with normalized headers.
    """
    filename = (file_storage.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    raw = file_storage.read()
    file_storage.stream.seek(0)

    if ext in ("xls", "xlsx"):
        # pandas reads both; engine inferred (openpyxl for xlsx, xlrd for xls)
        df = pd.read_excel(io.BytesIO(raw))

    else:
        # CSV/TXT: try utf-8 first; fallback latin-1 if needed
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

        # Let pandas detect delimiter; works for comma/semicolon/tab in most exports
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")

    # Normalize column headers
    df.columns = [_norm(str(c)) for c in df.columns]

    # Convert to list of dicts
    rows = df.fillna("").to_dict(orient="records")
    return rows

def extract_merchant_from_description(desc: str) -> str | None:
    if not desc:
        return None

    d = str(desc)

    # ABN iDEAL /TRTP style: /NAME/<merchant>/
    m = re.search(r"/NAME/([^/]+)", d)
    if m:
        return m.group(1).strip()

    # ABN card payments often look like:
    # "BEA, Betaalpas   PRIMARK ENSCHEDE,PAS954 ..."
    m = re.search(r"BEA,\s*Betaalpas\s+(.+?),PAS", d, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Fallback: first chunk before comma (rough but useful)
    first = d.split(",")[0].strip()
    return first if first else None


def normalize_transaction_row(r: dict) -> Optional[dict]:
    # ABN headers are like transactiondate / valuedate (no space)
    date_raw = _pick(r, [
        "transactiondate", "valuedate",
        "date", "transaction date", "booking date",
        "boekingsdatum", "datum",
        "value date", "valuta datum", "valutadatum"
    ])

    amount_raw = _pick(r, [
        "amount", "bedrag", "mutatie", "transaction amount"
    ])

    desc = _pick(r, [
        "description", "omschrijving", "details", "remittance information", "note"
    ])

    currency = _pick(r, ["currency", "valuta", "mutationcode"]) or "EUR"

    if not date_raw or not amount_raw:
        return None

    # Parse date like 20260110
    posted_date = dateparser.parse(str(date_raw)).date()

    # Parse amount, handle comma decimals
    a = str(amount_raw).replace("€", "").replace("\u20ac", "").replace(" ", "")
    if a.count(",") == 1 and a.count(".") == 0:
        a = a.replace(",", ".")
    a = a.replace(",", "")
    try:
        amount = Decimal(a)
    except Exception:
        return None

    merchant = extract_merchant_from_description(desc)

    return {
        "posted_date": posted_date,
        "merchant": merchant,
        "description": desc,
        "amount": amount,
        "currency": currency
    }
#helper function to delete txt when importing records
def clean_note(desc: str) -> str:
    if not desc:
        return ""

    d = str(desc)

    # Remove structured slash sections like /TRTP/... /IBAN/... /BIC/... etc.
    d = re.sub(r"/(TRTP|IBAN|BIC|NAME|REMI|EREF)/[^/]*", "", d)
    d = re.sub(r"/(iDEAL|SEPA|Wero)\b", "", d)

    # Remove long IDs / references (8+ digits or long alphanumerics)
    d = re.sub(r"\b[A-Z0-9]{14,}\b", "", d)
    d = re.sub(r"\b\d{8,}\b", "", d)

    # Normalize whitespace/slashes
    d = d.replace("/", " ")
    d = re.sub(r"\s+", " ", d).strip()

    return d[:140] + "…" if len(d) > 140 else d

def normalize_merchant_name(name: str | None) -> str | None:
    if not name:
        return None
    n = str(name).strip()
    n = re.sub(r"\s+via\s+.*$", "", n, flags=re.IGNORECASE)  # remove "via ..."
    n = re.sub(r"\s+", " ", n).strip()
    return n

def detect_bank_from_text(text: str) -> str | None:
    """Detect bank based on IBAN/BIC patterns in description or other strings."""
    if not text:
        return None

    t = str(text).upper()

    # BIC patterns
    if "ABNANL2A" in t or "ABNA" in t and "NL" in t:
        return "ABN AMRO"
    if "INGBNL2A" in t or "INGB" in t and "NL" in t:
        return "ING"
    if "BUNQNL2A" in t or "BUNQ" in t and "NL" in t:
        return "bunq"

    # IBAN bank-code patterns (NL IBAN format: NLkk + 4 bank letters)
    # Example: NL31ABNA...
    m = re.search(r"\bNL\d{2}([A-Z]{4})\b", t)
    if m:
        code = m.group(1)
        return {
            "ABNA": "ABN AMRO",
            "INGB": "ING",
            "BUNQ": "bunq",
            # add more as you need
        }.get(code)

    return None


def extract_iban_last4(text: str) -> str | None:
    """Extract last 4 digits of IBAN (useful for naming accounts)."""
    if not text:
        return None
    t = str(text).upper().replace(" ", "")

    # Find an IBAN-like substring NL..ABNA.... (basic)
    m = re.search(r"(NL\d{2}[A-Z]{4}[0-9A-Z]{10,30})", t)
    if not m:
        return None
    iban = m.group(1)
    # last 4 chars of IBAN (often digits, sometimes alnum)
    return iban[-4:] if len(iban) >= 4 else None



def tx_fingerprint(account_id, posted_date, amount, merchant, description):
    # Normalize to stable strings
    a = str(account_id or "")
    d = posted_date.isoformat() if posted_date else ""
    amt = f"{amount:.2f}" if amount is not None else ""
    m = (merchant or "").strip().lower()
    desc = (description or "").strip().lower()

    raw = "|".join([a, d, amt, m, desc])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
