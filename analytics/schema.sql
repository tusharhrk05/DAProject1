PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS business_profile (
    profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
    owner_name TEXT,
    role TEXT,
    business_sector TEXT,
    store_name TEXT,
    location TEXT,
    exported_at TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company_name TEXT,
    phone TEXT,
    email TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    selling_price REAL NOT NULL DEFAULT 0,
    purchase_rate REAL NOT NULL DEFAULT 0,
    purchase_rate_estimated INTEGER NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 0,
    supplier TEXT,
    last_purchase_date TEXT
);

CREATE TABLE IF NOT EXISTS bills (
    bill_id TEXT PRIMARY KEY,
    customer_id TEXT,
    customer_name TEXT NOT NULL,
    customer_company_name TEXT,
    customer_phone TEXT,
    bill_date TEXT,
    status TEXT,
    total REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    payment_method TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bill_items (
    bill_id TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    product_id TEXT,
    product_name TEXT NOT NULL,
    category TEXT,
    quantity REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (bill_id, line_number),
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bill_payments (
    bill_id TEXT NOT NULL,
    payment_number INTEGER NOT NULL,
    payment_date TEXT,
    amount REAL NOT NULL DEFAULT 0,
    payment_method TEXT,
    PRIMARY KEY (bill_id, payment_number),
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchases (
    purchase_id TEXT PRIMARY KEY,
    invoice_number TEXT,
    supplier TEXT NOT NULL,
    purchase_date TEXT,
    status TEXT,
    total REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    payment_method TEXT
);

CREATE TABLE IF NOT EXISTS purchase_items (
    purchase_id TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    product_id TEXT,
    product_name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    purchase_rate REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (purchase_id, line_number),
    FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS purchase_payments (
    purchase_id TEXT NOT NULL,
    payment_number INTEGER NOT NULL,
    payment_date TEXT,
    amount REAL NOT NULL DEFAULT 0,
    payment_method TEXT,
    PRIMARY KEY (purchase_id, payment_number),
    FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(bill_date);
CREATE INDEX IF NOT EXISTS idx_bills_customer ON bills(customer_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_product ON bill_items(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchase_items_product ON purchase_items(product_id);
