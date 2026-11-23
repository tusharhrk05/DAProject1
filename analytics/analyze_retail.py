#!/usr/bin/env python3
"""Load a BahiPro JSON export into SQLite and create retail analysis reports."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
except ImportError as error:
    print(
        "Missing analytics dependencies. Install them with: "
        "python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from error


ANALYTICS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ANALYTICS_DIR / "output"
BLUE = "#185fa9"
LIGHT_BLUE = "#a8c7eb"
ORANGE = "#e87916"


def number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if pd.notna(result) else default


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def phone_key(value: Any) -> str:
    digits = re.sub(r"\D", "", text(value))
    return digits[-10:] if digits else ""


def load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read JSON export at {path}: {error}") from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise ValueError("Expected a BahiPro analytics JSON export (schemaVersion 1).")
    for collection in ("customers", "products", "bills", "purchases"):
        if not isinstance(payload.get(collection), list):
            raise ValueError(f"Export field '{collection}' must be a list.")
    return payload


def normalized_customers(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    used_ids: set[str] = set()
    for index, customer in enumerate(customers, start=1):
        customer_id = text(customer.get("id"), f"C-{index:04d}")
        if not customer_id or customer_id in used_ids:
            customer_id = f"C-{index:04d}"
        while customer_id in used_ids:
            customer_id += "-copy"
        used_ids.add(customer_id)
        result.append({**customer, "id": customer_id})
    return result


def resolve_customer(bill: dict[str, Any], customers: list[dict[str, Any]]) -> str | None:
    customer_id = text(bill.get("customerId"))
    if customer_id and any(text(customer.get("id")) == customer_id for customer in customers):
        return customer_id

    bill_phone = phone_key(bill.get("phone"))
    if bill_phone:
        match = next(
            (customer for customer in customers if phone_key(customer.get("phone")) == bill_phone),
            None,
        )
        if match:
            return text(match.get("id")) or None

    bill_name = text(bill.get("customer")).casefold()
    match = next(
        (customer for customer in customers if text(customer.get("name")).casefold() == bill_name),
        None,
    )
    return (text(match.get("id")) or None) if match else None


def make_payment_rows(
    payments: Any, amount_paid: float, date: str, method: str
) -> list[dict[str, Any]]:
    if isinstance(payments, list) and payments:
        return [payment for payment in payments if isinstance(payment, dict)]
    if amount_paid > 0:
        return [{"date": date, "amount": amount_paid, "method": method}]
    return []


def clear_snapshot(connection: sqlite3.Connection) -> None:
    for table in (
        "bill_payments",
        "bill_items",
        "purchase_payments",
        "purchase_items",
        "bills",
        "purchases",
        "customers",
        "products",
        "business_profile",
    ):
        connection.execute(f"DELETE FROM {table}")


def load_snapshot(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, int]:
    customers = normalized_customers(payload["customers"])
    products = payload["products"]
    bills = payload["bills"]
    purchases = payload["purchases"]
    product_ids = {text(product.get("id")) for product in products}
    counts = {
        "customers": 0, "products": 0, "bills": 0, "bill_items": 0,
        "bill_payments": 0, "purchases": 0, "purchase_items": 0,
        "purchase_payments": 0,
    }

    with connection:
        clear_snapshot(connection)
        profile = payload.get("profile") or {}
        connection.execute(
            """INSERT INTO business_profile VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (
                text(profile.get("name")),
                text(profile.get("role")),
                text(profile.get("businessSector")),
                text(profile.get("storeName")),
                text(profile.get("location")),
                text(payload.get("exportedAt")) or None,
            ),
        )

        for product in products:
            product_id = text(product.get("id"))
            if not product_id:
                continue
            connection.execute(
                """INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    text(product.get("name"), "Unnamed product"),
                    text(product.get("category"), "Other"),
                    number(product.get("price")),
                    number(product.get("purchaseRate")),
                    int(bool(product.get("purchaseRateEstimated"))),
                    int(number(product.get("stock"))),
                    int(number(product.get("reorder"))),
                    text(product.get("supplier")),
                    text(product.get("lastPurchaseDate")) or None,
                ),
            )
            counts["products"] += 1

        for customer in customers:
            connection.execute(
                """INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    text(customer.get("id")),
                    text(customer.get("name"), "Unnamed customer"),
                    text(customer.get("companyName")),
                    text(customer.get("phone")),
                    text(customer.get("email")),
                    text(customer.get("createdAt")) or None,
                ),
            )
            counts["customers"] += 1

        for bill in bills:
            bill_id = text(bill.get("id"))
            if not bill_id:
                continue
            total = max(0.0, number(bill.get("total")))
            paid = min(total, max(0.0, number(bill.get("paidAmount"))))
            balance = max(0.0, total - paid)
            method = text(bill.get("method"))
            bill_date = text(bill.get("date"))
            connection.execute(
                """INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bill_id,
                    resolve_customer(bill, customers),
                    text(bill.get("customer"), "Unknown customer"),
                    text(bill.get("customerCompanyName")),
                    text(bill.get("phone")),
                    bill_date,
                    text(bill.get("status"), "Pending"),
                    total,
                    paid,
                    balance,
                    method,
                ),
            )
            counts["bills"] += 1

            lines = bill.get("lines") if isinstance(bill.get("lines"), list) else []
            for line_number, line in enumerate(lines, start=1):
                quantity = number(line.get("quantity"))
                unit_price = number(line.get("unitPrice"))
                product_id = text(line.get("productId"))
                connection.execute(
                    """INSERT INTO bill_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        bill_id,
                        line_number,
                        product_id if product_id in product_ids else None,
                        text(line.get("productName"), "Unnamed product"),
                        text(line.get("category"), "Other"),
                        quantity,
                        unit_price,
                        number(line.get("lineTotal"), quantity * unit_price),
                    ),
                )
                counts["bill_items"] += 1

            for payment_number, payment in enumerate(
                make_payment_rows(bill.get("payments"), paid, bill_date, method), start=1
            ):
                connection.execute(
                    """INSERT INTO bill_payments VALUES (?, ?, ?, ?, ?)""",
                    (
                        bill_id,
                        payment_number,
                        text(payment.get("date")) or None,
                        max(0.0, number(payment.get("amount"))),
                        text(payment.get("method")),
                    ),
                )
                counts["bill_payments"] += 1

        for purchase in purchases:
            purchase_id = text(purchase.get("id"))
            if not purchase_id:
                continue
            total = max(0.0, number(purchase.get("total")))
            paid = min(total, max(0.0, number(purchase.get("paidAmount"))))
            supplier = text(purchase.get("supplier"), "Unknown supplier")
            purchase_date = text(purchase.get("date"))
            method = text(purchase.get("method"))
            connection.execute(
                """INSERT INTO purchases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    purchase_id,
                    text(purchase.get("invoiceNumber")),
                    supplier,
                    purchase_date,
                    text(purchase.get("status"), "Pending"),
                    total,
                    paid,
                    max(0.0, total - paid),
                    method,
                ),
            )
            counts["purchases"] += 1
            lines = purchase.get("lines") if isinstance(purchase.get("lines"), list) else []
            for line_number, line in enumerate(lines, start=1):
                quantity = number(line.get("quantity"))
                rate = number(line.get("purchaseRate"))
                product_id = text(line.get("productId"))
                connection.execute(
                    """INSERT INTO purchase_items VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        purchase_id,
                        line_number,
                        product_id if product_id in product_ids else None,
                        text(line.get("productName"), "Unnamed product"),
                        quantity,
                        rate,
                        number(line.get("lineTotal"), quantity * rate),
                    ),
                )
                counts["purchase_items"] += 1

            for payment_number, payment in enumerate(
                make_payment_rows(purchase.get("payments"), paid, purchase_date, method), start=1
            ):
                connection.execute(
                    """INSERT INTO purchase_payments VALUES (?, ?, ?, ?, ?)""",
                    (
                        purchase_id,
                        payment_number,
                        text(payment.get("date")) or None,
                        max(0.0, number(payment.get("amount"))),
                        text(payment.get("method")),
                    ),
                )
                counts["purchase_payments"] += 1

    return counts


def read_queries(connection: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    sql_text = (ANALYTICS_DIR / "queries.sql").read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {}
    current_name: str | None = None
    for line in sql_text.splitlines():
        marker = re.match(r"\s*--\s*query:\s*([a-z0-9_]+)\s*$", line, re.I)
        if marker:
            current_name = marker.group(1)
            sections[current_name] = []
        elif current_name:
            sections[current_name].append(line)
    if not sections:
        raise ValueError(f"No named queries found in {ANALYTICS_DIR / 'queries.sql'}.")

    reports = {}
    for name, lines in sections.items():
        query = "\n".join(lines).strip().rstrip(";").strip()
        reports[name] = pd.read_sql_query(query, connection)
    return reports


def write_charts(reports: dict[str, pd.DataFrame], output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    chart_count = 0

    monthly = reports["monthly_sales"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if monthly.empty:
        ax.text(0.5, 0.5, "No sales recorded yet", ha="center", va="center", color="#6d8097")
        ax.set_axis_off()
    else:
        ax.bar(monthly["month"], monthly["sales"], color=BLUE, width=0.66, label="Sales")
        ax.plot(monthly["month"], monthly["collected"], color=ORANGE, marker="o", label="Collected")
        ax.set_ylabel("Amount (INR)")
        ax.legend(frameon=False)
        ax.tick_params(axis="x", rotation=35)
    ax.set_title("Monthly sales and payments", loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "monthly_sales.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    chart_count += 1

    categories = reports["category_sales"].head(10).sort_values("sales")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if categories.empty:
        ax.text(0.5, 0.5, "No item sales recorded yet", ha="center", va="center", color="#6d8097")
        ax.set_axis_off()
    else:
        ax.barh(categories["category"], categories["sales"], color=LIGHT_BLUE)
        ax.set_xlabel("Sales (INR)")
    ax.set_title("Sales by product category", loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "category_sales.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    chart_count += 1

    inventory = reports["inventory_health"]
    status_counts = inventory["stock_status"].value_counts().reindex(
        ["Healthy", "Reorder", "Out of stock"], fill_value=0
    )
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(status_counts.index, status_counts.values, color=[BLUE, ORANGE, "#bd5b56"], width=0.58)
    ax.set_ylabel("Products")
    ax.set_title("Current inventory health", loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "inventory_health.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    chart_count += 1

    customers = reports["customer_lifetime"].head(10).sort_values("lifetime_spend")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if customers.empty:
        ax.text(0.5, 0.5, "No customer sales recorded yet", ha="center", va="center", color="#6d8097")
        ax.set_axis_off()
    else:
        ax.barh(customers["customer"], customers["lifetime_spend"], color=BLUE, label="Lifetime spend")
        ax.barh(customers["customer"], customers["lifetime_pending"], color=ORANGE, label="Pending")
        ax.set_xlabel("Amount (INR)")
        ax.legend(frameon=False)
    ax.set_title("Customer lifetime value and pending", loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "customer_lifetime.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    chart_count += 1
    return chart_count


def run(input_path: Path, output_dir: Path) -> None:
    payload = load_payload(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "bahipro_analytics.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript((ANALYTICS_DIR / "schema.sql").read_text(encoding="utf-8"))
        counts = load_snapshot(connection, payload)
        reports = read_queries(connection)

    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in reports.items():
        frame.to_csv(reports_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    chart_count = write_charts(reports, output_dir / "charts")

    print(f"Loaded BahiPro export from: {input_path}")
    print(f"SQLite database: {database_path}")
    print(f"CSV reports: {reports_dir} ({len(reports)} files)")
    print(f"Charts: {output_dir / 'charts'} ({chart_count} files)")
    print("Imported records: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    if not counts["bills"]:
        print("No bills were in this snapshot; sales and customer-spend reports are empty until you record sales.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build BahiPro's SQLite retail analytics database and report pack."
    )
    parser.add_argument("--input", required=True, type=Path, help="JSON snapshot exported from BahiPro")
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output folder (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    try:
        run(args.input.expanduser().resolve(), args.output_dir.expanduser().resolve())
    except (ValueError, OSError, sqlite3.Error, pd.errors.DatabaseError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
