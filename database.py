"""SQLite persistence and reporting queries for the BahiPro retail workspace."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_DIR / "data"
SCHEMA_PATH = PROJECT_DIR / "analytics" / "schema.sql"


def _database_path(workspace_id: str) -> Path:
    """Return an isolated, non-guessable SQLite path for a UUID workspace key."""
    try:
        canonical_id = str(uuid.UUID(workspace_id))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("A valid workspace ID is required.") from error
    filename = hashlib.sha256(canonical_id.encode("ascii")).hexdigest()
    return DATABASE_DIR / "workspaces" / f"{filename}.sqlite3"


def connect(workspace_id: str) -> sqlite3.Connection:
    path = _database_path(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database_connection(workspace_id: str):
    connection = connect(workspace_id)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(workspace_id: str) -> None:
    with database_connection(workspace_id) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute(
            """CREATE TABLE IF NOT EXISTS workspace_state (
                workspace_id INTEGER PRIMARY KEY CHECK (workspace_id = 1),
                workspace_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_workspace(workspace_id: str) -> tuple[dict[str, Any] | None, str | None]:
    with database_connection(workspace_id) as connection:
        row = connection.execute(
            "SELECT workspace_json, updated_at FROM workspace_state WHERE workspace_id = 1"
        ).fetchone()
    if row is None:
        return None, None
    return json.loads(row["workspace_json"]), row["updated_at"]


def _number(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) != float("inf") else default


def _list_of_dicts(workspace: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = workspace.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Workspace field '{key}' must be a list of records.")
    return value


def _record_id(record: dict[str, Any], key: str, collection: str) -> str:
    value = str(record.get(key) or "").strip()
    if not value:
        raise ValueError(f"Every record in '{collection}' needs an ID.")
    return value


def _validate_workspace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Workspace must be a JSON object.")
    for collection in ("products", "bills", "customers", "purchases"):
        records = _list_of_dicts(value, collection)
        id_field = {"products": "id", "bills": "id", "customers": "id", "purchases": "id"}[collection]
        ids = [_record_id(record, id_field, collection) for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError(f"The '{collection}' collection contains duplicate IDs.")
    profile = value.get("profile", {})
    if not isinstance(profile, dict):
        raise ValueError("Workspace profile must be a JSON object.")
    for collection in ("bills", "purchases"):
        for record in _list_of_dicts(value, collection):
            for nested in ("lines", "payments"):
                entries = record.get(nested, [])
                if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                    raise ValueError(f"Each '{nested}' field in '{collection}' must be a list of records.")
    # Round-trip here also rejects values JSON cannot safely persist (such as NaN).
    json.dumps(value, ensure_ascii=False, allow_nan=False)
    return value


def save_workspace(value: Any, workspace_id: str) -> str:
    workspace = _validate_workspace(value)
    products = _list_of_dicts(workspace, "products")
    bills = _list_of_dicts(workspace, "bills")
    customers = _list_of_dicts(workspace, "customers")
    purchases = _list_of_dicts(workspace, "purchases")
    product_ids = {str(record["id"]) for record in products}
    customer_ids = {str(record["id"]) for record in customers}
    workspace_json = json.dumps(workspace, ensure_ascii=False, allow_nan=False)
    updated_at = utc_now()

    with database_connection(workspace_id) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("DELETE FROM bill_payments")
            connection.execute("DELETE FROM bill_items")
            connection.execute("DELETE FROM purchase_payments")
            connection.execute("DELETE FROM purchase_items")
            connection.execute("DELETE FROM bills")
            connection.execute("DELETE FROM purchases")
            connection.execute("DELETE FROM customers")
            connection.execute("DELETE FROM products")
            connection.execute("DELETE FROM business_profile")

            profile = workspace.get("profile") or {}
            connection.execute(
                """INSERT INTO business_profile
                   (profile_id, owner_name, role, business_sector, store_name, location, exported_at)
                   VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (profile.get("name", ""), profile.get("role", ""), profile.get("businessSector", ""),
                 profile.get("storeName", ""), profile.get("location", ""), updated_at),
            )

            for customer in customers:
                connection.execute(
                    """INSERT INTO customers
                       (customer_id, name, company_name, phone, email, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(customer["id"]), customer.get("name", "Unknown customer"), customer.get("companyName", ""),
                     customer.get("phone", ""), customer.get("email", ""), customer.get("createdAt", "")),
                )

            for product in products:
                connection.execute(
                    """INSERT INTO products
                       (product_id, name, category, selling_price, purchase_rate, purchase_rate_estimated,
                        stock, reorder_level, supplier, last_purchase_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(product["id"]), product.get("name", "Unnamed product"), product.get("category", ""),
                     _number(product.get("price")), _number(product.get("purchaseRate")),
                     int(bool(product.get("purchaseRateEstimated"))), int(_number(product.get("stock"))),
                     int(_number(product.get("reorder"))), product.get("supplier", ""),
                     product.get("lastPurchaseDate", "")),
                )

            for bill in bills:
                bill_id = str(bill["id"])
                customer_id = str(bill.get("customerId") or "")
                if customer_id not in customer_ids:
                    customer_id = None
                total = _number(bill.get("total"))
                paid = _number(bill.get("paidAmount"))
                connection.execute(
                    """INSERT INTO bills
                       (bill_id, customer_id, customer_name, customer_company_name, customer_phone,
                        bill_date, status, total, paid_amount, balance_due, payment_method)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (bill_id, customer_id, bill.get("customer", "Unknown customer"),
                     bill.get("customerCompanyName", ""), bill.get("phone", ""), bill.get("date", ""),
                     bill.get("status", "Pending"), total, paid, max(0, total - paid), bill.get("method", "")),
                )
                for line_number, line in enumerate(bill.get("lines") or [], start=1):
                    product_id = str(line.get("productId") or "")
                    if product_id not in product_ids:
                        product_id = None
                    connection.execute(
                        """INSERT INTO bill_items
                           (bill_id, line_number, product_id, product_name, category, quantity, unit_price, line_total)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (bill_id, line_number, product_id, line.get("productName", "Item"), line.get("category", ""),
                         _number(line.get("quantity")), _number(line.get("unitPrice")), _number(line.get("lineTotal"))),
                    )
                for payment_number, payment in enumerate(bill.get("payments") or [], start=1):
                    connection.execute(
                        """INSERT INTO bill_payments
                           (bill_id, payment_number, payment_date, amount, payment_method)
                           VALUES (?, ?, ?, ?, ?)""",
                        (bill_id, payment_number, payment.get("date", bill.get("date", "")),
                         _number(payment.get("amount")), payment.get("method", "")),
                    )

            for purchase in purchases:
                purchase_id = str(purchase["id"])
                total = _number(purchase.get("total"))
                paid = _number(purchase.get("paidAmount"))
                connection.execute(
                    """INSERT INTO purchases
                       (purchase_id, invoice_number, supplier, purchase_date, status,
                        total, paid_amount, balance_due, payment_method)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (purchase_id, purchase.get("invoiceNumber", ""), purchase.get("supplier", "Unknown supplier"),
                     purchase.get("date", ""), purchase.get("status", "Pending"), total, paid,
                     max(0, total - paid), purchase.get("method", "")),
                )
                for line_number, line in enumerate(purchase.get("lines") or [], start=1):
                    product_id = str(line.get("productId") or "")
                    if product_id not in product_ids:
                        product_id = None
                    connection.execute(
                        """INSERT INTO purchase_items
                           (purchase_id, line_number, product_id, product_name, quantity, purchase_rate, line_total)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (purchase_id, line_number, product_id, line.get("productName", "Item"),
                         _number(line.get("quantity")), _number(line.get("purchaseRate")),
                         _number(line.get("lineTotal"))),
                    )
                for payment_number, payment in enumerate(purchase.get("payments") or [], start=1):
                    connection.execute(
                        """INSERT INTO purchase_payments
                           (purchase_id, payment_number, payment_date, amount, payment_method)
                           VALUES (?, ?, ?, ?, ?)""",
                        (purchase_id, payment_number, payment.get("date", purchase.get("date", "")),
                         _number(payment.get("amount")), payment.get("method", "")),
                    )

            connection.execute(
                """INSERT INTO workspace_state (workspace_id, workspace_json, updated_at)
                   VALUES (1, ?, ?)
                   ON CONFLICT(workspace_id) DO UPDATE SET
                     workspace_json = excluded.workspace_json,
                     updated_at = excluded.updated_at""",
                (workspace_json, updated_at),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return updated_at


def load_rows(query: str, workspace_id: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with database_connection(workspace_id) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]
