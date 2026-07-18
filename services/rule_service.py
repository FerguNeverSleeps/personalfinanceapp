from models import Rule  # adjust import path if needed

import re

#helper class to get cleaner categories
def guess_category(merchant: str, desc: str) -> str:
    text = f"{merchant or ''} {desc or ''}".lower()
    if "tikkie" in text:
        return "Transfers"
    if any(k in text for k in ["ns", "ov", "uber", "bolt"]):
        return "Transport"
    if any(k in text for k in ["netflix", "spotify", "apple", "google", "amazon"]):
        return "Subscriptions"

    if any(k in text for k in ["jumbo", "albert heijn", "ah ", "lidl", "aldi", "plus", "dirk"]):
        return "Groceries"
    if any(k in text for k in ["takeaway", "thuisbezorgd", "ubereats", "deliveroo", "restaurant", "cafe", "pizza"]):
        return "Dining out"

    if any(k in text for k in
           ["cinema", "movie", "bar", "club", "bowling", "game", "steam", "playstation", "ticketmaster"]):
        return "Leisure"

    if any(k in text for k in ["betaalpas", "pas", "bea,"]):
        # usually card payments -> don't auto-pick category by this alone,
        # but it helps for merchant keywords present in same line
        pass

    return "Uncategorized"

def apply_rules_to_row(merchant: str | None, description: str | None):
    """
    Returns a Category (model) if a rule matches; otherwise None.
    First match by priority wins.
    """
    merchant = (merchant or "")
    description = (description or "")

    rules = (
        Rule.query
        .filter_by(is_active=True)
        .order_by(Rule.priority.asc(), Rule.id.asc())
        .all()
    )

    for r in rules:
        hay = merchant if r.match_field == "merchant" else description
        hay_l = hay.lower()

        pat = (r.pattern or "").strip()
        if not pat:
            continue

        if r.match_type == "contains":
            # allow comma-separated keywords: "jumbo, thuisbezorgd"
            needles = [p.strip().lower() for p in pat.split(",") if p.strip()]
            if any(n in hay_l for n in needles):
                return r.category

        elif r.match_type == "regex":
            try:
                if re.search(pat, hay, flags=re.IGNORECASE):
                    return r.category
            except re.error:
                continue

    return None