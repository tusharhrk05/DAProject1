"""Private, local rule-based retail suggestions backed by BahiPro's SQLite data."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any


def _money(value: Any) -> str:
    return f"₹{float(value or 0):,.2f}".rstrip("0").rstrip(".")


def _restock_plan(connection: sqlite3.Connection, product: sqlite3.Row) -> dict[str, int]:
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    recent = connection.execute(
        """SELECT COALESCE(SUM(bi.quantity), 0) AS units
           FROM bill_items bi JOIN bills b ON b.bill_id = bi.bill_id
           WHERE bi.product_id = ? AND b.bill_date >= ?""",
        (product["product_id"], cutoff),
    ).fetchone()["units"]
    reorder = int(product["reorder_level"] or 0)
    target = max(reorder * 2, int(float(recent) * 1.5 + 0.999), reorder + 1)
    return {"quantity": max(0, target - int(product["stock"] or 0)), "recentUnits": int(recent)}


def _low_stock(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT product_id, name, stock, reorder_level, category
           FROM products WHERE stock <= reorder_level
           ORDER BY stock ASC, name COLLATE NOCASE"""
    ).fetchall()


def suggestions(connection: sqlite3.Connection) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    low = _low_stock(connection)
    if low:
        top_ups = [f"{row['name']}: add about {_restock_plan(connection, row)['quantity']}" for row in low[:3]]
        remaining = f"; {len(low) - 3} more need review" if len(low) > 3 else ""
        items.append({
            "icon": "▦",
            "title": f"Restock {len(low)} low-stock item{'s' if len(low) != 1 else ''}",
            "body": f"Suggested top-ups: {'; '.join(top_ups)}{remaining}. Quantities aim for roughly twice the reorder point, adjusted for recent 30-day sales.",
            "page": "inventory",
            "action": "Review inventory",
        })

    due = connection.execute(
        """SELECT COUNT(*) AS count, COALESCE(SUM(balance_due), 0) AS amount
           FROM bills WHERE balance_due > 0"""
    ).fetchone()
    if due["amount"]:
        oldest = connection.execute(
            "SELECT bill_id FROM bills WHERE balance_due > 0 ORDER BY bill_date LIMIT 1"
        ).fetchone()
        items.append({
            "icon": "₹",
            "title": f"Follow up on {_money(due['amount'])} due",
            "body": f"{due['count']} bill{'s' if due['count'] != 1 else ''} still have a balance. {oldest['bill_id'] if oldest else ''} is the oldest open bill.",
            "page": "billing",
            "action": "Review pending bills",
        })

    today = date.today()
    current_month = today.strftime("%Y-%m")
    previous_month_date = today.replace(day=1) - timedelta(days=1)
    previous_month = previous_month_date.strftime("%Y-%m")
    sales = connection.execute(
        """SELECT substr(bill_date, 1, 7) AS month, COALESCE(SUM(total), 0) AS total
           FROM bills WHERE substr(bill_date, 1, 7) IN (?, ?) GROUP BY substr(bill_date, 1, 7)""",
        (current_month, previous_month),
    ).fetchall()
    monthly = {row["month"]: row["total"] for row in sales}
    current, previous = monthly.get(current_month, 0), monthly.get(previous_month, 0)
    if current or previous:
        if previous:
            percent = round(abs((current - previous) / previous * 100))
            body = f"Recorded sales are {'up' if current >= previous else 'down'} {percent}% versus last month ({_money(current)} vs {_money(previous)})."
        else:
            body = f"{_money(current)} in sales recorded so far this month. No sales were recorded last month for comparison."
        items.append({"icon": "↗", "title": "Monthly sales pulse", "body": body, "page": "reports", "action": "Open reports"})

    best = connection.execute(
        """SELECT product_name, SUM(quantity) AS units
           FROM bill_items GROUP BY product_id, product_name
           ORDER BY units DESC, product_name COLLATE NOCASE LIMIT 1"""
    ).fetchone()
    if best:
        items.append({
            "icon": "★",
            "title": f"{best['product_name']} leads recorded sales",
            "body": f"{int(best['units'])} units sold in saved bills. Check its current stock before your next order.",
            "page": "inventory",
            "action": "Check product stock",
        })
    if not items:
        items.append({
            "icon": "✦",
            "title": "Start with your first bill",
            "body": "Once you record sales, BahiPro can highlight top products, monthly sales movement, and customer balances.",
            "page": "billing",
            "action": "Create a bill",
        })
    return items[:4]


def answer(connection: sqlite3.Connection, question: str) -> str:
    query = re.sub(r"\s+", " ", str(question or "").strip().lower())
    if not query:
        return "Ask about sales, pending payments, stock, top products, customers, purchases, or estimated margins."

    if re.search(r"pending|due|owe|unpaid|collect|balance", query):
        totals = connection.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(balance_due), 0) AS amount FROM bills WHERE balance_due > 0"
        ).fetchone()
        if not totals["amount"]:
            return "There are no customer bill balances pending in this workspace."
        largest = connection.execute(
            """SELECT bill_id, customer_name, balance_due FROM bills WHERE balance_due > 0
               ORDER BY balance_due DESC LIMIT 3"""
        ).fetchall()
        examples = ", ".join(f"{row['bill_id']} ({row['customer_name']}: {_money(row['balance_due'])})" for row in largest)
        return f"{_money(totals['amount'])} is pending across {totals['count']} bill(s). Largest balances: {examples}. Open Billing to record a payment or follow up."

    if re.search(r"stock|inventory|restock|reorder", query):
        low = _low_stock(connection)
        if not low:
            return "All products are currently above their reorder levels."
        details = []
        for product in low[:5]:
            plan = _restock_plan(connection, product)
            details.append(f"{product['name']}: {product['stock']} left; consider adding about {plan['quantity']}")
        return f"{len(low)} product(s) need attention: {'; '.join(details)}. Suggested quantities aim for roughly twice each reorder point and account for recent 30-day sales. Review Inventory before ordering."

    if re.search(r"sales|revenue|month|today|collection", query):
        month = date.today().strftime("%Y-%m")
        row = connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS sales,
                      COALESCE(SUM(paid_amount), 0) AS collected
               FROM bills WHERE substr(bill_date, 1, 7) = ?""",
            (month,),
        ).fetchone()
        today = connection.execute(
            "SELECT COALESCE(SUM(total), 0) FROM bills WHERE bill_date = ?", (date.today().isoformat(),)
        ).fetchone()[0]
        return f"This month: {_money(row['sales'])} recorded across {row['count']} bill(s), with {_money(row['collected'])} collected and {_money(row['sales'] - row['collected'])} still due. Today's sales are {_money(today)}."

    if re.search(r"top|best|popular|selling|product|sold", query):
        rows = connection.execute(
            """SELECT product_name, SUM(quantity) AS units FROM bill_items
               GROUP BY product_id, product_name ORDER BY units DESC LIMIT 3"""
        ).fetchall()
        if not rows:
            return "No bill line items are recorded yet. Save bills with products to see top sellers."
        ranked = "; ".join(f"{index}. {row['product_name']} ({int(row['units'])} sold)" for index, row in enumerate(rows, 1))
        return f"Top products by units in saved bills: {ranked}."

    if re.search(r"customer|client|buyer", query):
        count = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        biggest = connection.execute(
            """SELECT customer_name, SUM(total) AS lifetime_spend FROM bills
               GROUP BY customer_id, customer_name ORDER BY lifetime_spend DESC LIMIT 1"""
        ).fetchone()
        if biggest:
            return f"{count} customer(s) saved. {biggest['customer_name']} has the highest bill-recorded lifetime spend at {_money(biggest['lifetime_spend'])}."
        return f"{count} customer(s) saved. Add customers while billing to build customer purchase history."

    if re.search(r"purchase|supplier|payable", query):
        row = connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS total,
                      COALESCE(SUM(balance_due), 0) AS due,
                      SUM(CASE WHEN balance_due > 0 THEN 1 ELSE 0 END) AS open_count
               FROM purchases"""
        ).fetchone()
        return f"{row['count']} purchase(s) recorded for {_money(row['total'])} total. {_money(row['due'])} remains payable across {row['open_count'] or 0} purchase(s)."

    if re.search(r"profit|margin|cost", query):
        row = connection.execute(
            """SELECT COALESCE(SUM((bi.unit_price - p.purchase_rate) * bi.quantity), 0) AS estimate,
                      COALESCE(MAX(p.purchase_rate_estimated), 0) AS has_estimates
               FROM bill_items bi JOIN products p ON p.product_id = bi.product_id"""
        ).fetchone()
        qualifier = "Some purchase rates are estimates, so treat this as a rough guide." if row["has_estimates"] else "This is a guide, not an accounting profit figure."
        return f"Estimated gross margin on saved bill items is {_money(row['estimate'])}, using each product's current purchase rate. {qualifier}"

    return "I can answer about sales, pending payments, stock and reorder items, top products, customers, purchases, and estimated margins. Try one of the example questions."
