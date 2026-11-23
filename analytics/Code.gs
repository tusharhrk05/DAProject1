/**
 * BahiPro Google Sheets receiver.
 * Store BAHIPRO_SPREADSHEET_ID and BAHIPRO_EXPORT_TOKEN in Script Properties.
 */
function doGet(event) {
  const parameters = event && event.parameter ? event.parameter : {};
  if (parameters.action !== 'status') {
    return ContentService.createTextOutput('BahiPro Sheets receiver is ready.');
  }

  const callback = String(parameters.callback || '');
  const requestId = String(parameters.id || '');
  if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(callback)) {
    return ContentService.createTextOutput('Invalid callback.');
  }
  const cached = /^[a-f0-9]{32}$/.test(requestId)
    ? CacheService.getScriptCache().get('bahipro-export-' + requestId)
    : null;
  const result = cached ? JSON.parse(cached) : { pending: true };
  const safeJson = JSON.stringify(result).replace(/</g, '\\u003c');
  return ContentService.createTextOutput(callback + '(' + safeJson + ');')
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function doPost(event) {
  let request = {};
  try {
    const properties = PropertiesService.getScriptProperties();
    const expectedToken = properties.getProperty('BAHIPRO_EXPORT_TOKEN') || '';
    const spreadsheetId = properties.getProperty('BAHIPRO_SPREADSHEET_ID') || '';
    const raw = event && event.parameter && event.parameter.payload
      ? event.parameter.payload
      : event && event.postData && event.postData.contents
        ? event.postData.contents
        : '';
    request = JSON.parse(raw || '{}');

    if (!expectedToken || !request.token || request.token !== expectedToken) {
      return recordResult_(request.requestId, { ok: false, error: 'Invalid export token.' });
    }
    if (!spreadsheetId) {
      return recordResult_(request.requestId, { ok: false, error: 'Spreadsheet ID is not configured.' });
    }
    if (!request.data || request.data.schemaVersion !== 1) {
      return recordResult_(request.requestId, { ok: false, error: 'Unsupported BahiPro export payload.' });
    }

    const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
    const tabs = buildTabs_(request.data);
    Object.keys(tabs).forEach(function (name) {
      writeTab_(spreadsheet, name, tabs[name]);
    });

    return recordResult_(request.requestId, { ok: true, updated: Object.keys(tabs) });
  } catch (error) {
    return recordResult_(request.requestId, {
      ok: false,
      error: String(error && error.message || error).slice(0, 300)
    });
  }
}

function recordResult_(requestId, result) {
  if (/^[a-f0-9]{32}$/.test(String(requestId || ''))) {
    CacheService.getScriptCache().put(
      'bahipro-export-' + requestId,
      JSON.stringify(result),
      300
    );
  }
  return jsonResponse_(result);
}

function authorizeBahiProSheetsExport() {
  const spreadsheetId = PropertiesService.getScriptProperties()
    .getProperty('BAHIPRO_SPREADSHEET_ID');
  if (!spreadsheetId) throw new Error('Set BAHIPRO_SPREADSHEET_ID in Script Properties first.');
  SpreadsheetApp.openById(spreadsheetId).getName();
}

function jsonResponse_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}

function buildTabs_(data) {
  const customers = Array.isArray(data.customers) ? data.customers : [];
  const products = Array.isArray(data.products) ? data.products : [];
  const bills = Array.isArray(data.bills) ? data.bills : [];
  const purchases = Array.isArray(data.purchases) ? data.purchases : [];
  const profile = data.profile || {};
  const pending = function (record) {
    return Math.max(0, numeric_(record.total) - numeric_(record.paidAmount));
  };
  const billItems = [];
  const billPayments = [];
  const purchaseItems = [];
  const supplierPayments = [];

  bills.forEach(function (bill) {
    (Array.isArray(bill.lines) ? bill.lines : []).forEach(function (line, index) {
      billItems.push([
        bill.id, index + 1, line.productId || '', line.productName || '', line.category || '',
        numeric_(line.quantity), numeric_(line.unitPrice), numeric_(line.lineTotal)
      ]);
    });
    paymentRows_(bill).forEach(function (payment) {
      billPayments.push([bill.id, payment.date || bill.date || '', numeric_(payment.amount), payment.method || '']);
    });
  });

  purchases.forEach(function (purchase) {
    (Array.isArray(purchase.lines) ? purchase.lines : []).forEach(function (line, index) {
      purchaseItems.push([
        purchase.id, index + 1, line.productId || '', line.productName || '',
        numeric_(line.quantity), numeric_(line.purchaseRate), numeric_(line.lineTotal)
      ]);
    });
    paymentRows_(purchase).forEach(function (payment) {
      supplierPayments.push([
        purchase.id, purchase.supplier || '', payment.date || purchase.date || '',
        numeric_(payment.amount), payment.method || ''
      ]);
    });
  });

  const customerRows = customers.map(function (customer) {
    const matched = bills.filter(function (bill) { return sameCustomer_(customer, bill); });
    return [
      customer.id || '', customer.name || '', customer.companyName || '', customer.phone || '',
      customer.email || '', matched.length,
      matched.reduce(function (sum, bill) { return sum + numeric_(bill.total); }, 0),
      matched.reduce(function (sum, bill) { return sum + pending(bill); }, 0)
    ];
  });

  const totalSales = bills.reduce(function (sum, bill) { return sum + numeric_(bill.total); }, 0);
  const collected = bills.reduce(function (sum, bill) { return sum + numeric_(bill.paidAmount); }, 0);
  const totalPending = bills.reduce(function (sum, bill) { return sum + pending(bill); }, 0);
  const stockValue = products.reduce(function (sum, product) {
    return sum + numeric_(product.stock) * numeric_(product.purchaseRate);
  }, 0);

  return {
    Overview: {
      headers: ['Metric', 'Value'],
      rows: [
        ['Store', profile.storeName || ''],
        ['Business sector', profile.businessSector || ''],
        ['Owner', profile.name || ''],
        ['Exported at', data.exportedAt || ''],
        ['Bills', bills.length],
        ['Recorded sales (INR)', totalSales],
        ['Collected from customers (INR)', collected],
        ['Customer balance pending (INR)', totalPending],
        ['Customers', customers.length],
        ['Products', products.length],
        ['Inventory cost value (INR)', stockValue],
        ['Purchases', purchases.length],
        ['Supplier balance due (INR)', purchases.reduce(function (sum, purchase) {
          return sum + pending(purchase);
        }, 0)]
      ]
    },
    Bills: {
      headers: ['Invoice', 'Customer', 'Company', 'Phone', 'Date', 'Status', 'Items', 'Total (INR)', 'Paid (INR)', 'Pending (INR)', 'Payment method'],
      rows: bills.map(function (bill) {
        return [bill.id || '', bill.customer || '', bill.customerCompanyName || '', bill.phone || '',
          bill.date || '', bill.status || '', numeric_(bill.items), numeric_(bill.total),
          numeric_(bill.paidAmount), pending(bill), bill.method || ''];
      })
    },
    'Bill Items': {
      headers: ['Invoice', 'Line', 'Product ID', 'Product', 'Category', 'Quantity', 'Unit price (INR)', 'Line total (INR)'],
      rows: billItems
    },
    'Bill Payments': {
      headers: ['Invoice', 'Date', 'Amount (INR)', 'Method'],
      rows: billPayments
    },
    Customers: {
      headers: ['Customer ID', 'Customer', 'Company', 'Phone', 'Email', 'Visits', 'Lifetime spend (INR)', 'Lifetime pending (INR)'],
      rows: customerRows
    },
    Inventory: {
      headers: ['Product ID', 'Product', 'Category', 'Selling price (INR)', 'Purchase rate (INR)', 'Rate source', 'Unit margin (INR)', 'Supplier', 'Last purchase date', 'Stock', 'Stock cost value (INR)', 'Reorder level', 'Status'],
      rows: products.map(function (product) {
        const stock = numeric_(product.stock);
        const reorder = numeric_(product.reorder);
        return [product.id || '', product.name || '', product.category || '',
          numeric_(product.price), numeric_(product.purchaseRate),
          product.purchaseRateEstimated ? 'Estimated' : 'Recorded',
          numeric_(product.price) - numeric_(product.purchaseRate), product.supplier || '',
          product.lastPurchaseDate || '', stock,
          stock * numeric_(product.purchaseRate), reorder,
          stock === 0 ? 'Out of stock' : stock <= reorder ? 'Reorder' : 'Healthy'];
      })
    },
    Purchases: {
      headers: ['Purchase ID', 'Supplier invoice', 'Supplier', 'Date', 'Items', 'Total (INR)', 'Paid (INR)', 'Pending (INR)', 'Status', 'Payment method'],
      rows: purchases.map(function (purchase) {
        return [purchase.id || '', purchase.invoiceNumber || '', purchase.supplier || '',
          purchase.date || '', numeric_(purchase.items), numeric_(purchase.total),
          numeric_(purchase.paidAmount), pending(purchase), purchase.status || '', purchase.method || ''];
      })
    },
    'Purchase Items': {
      headers: ['Purchase ID', 'Line', 'Product ID', 'Product', 'Quantity', 'Purchase rate (INR)', 'Line total (INR)'],
      rows: purchaseItems
    },
    'Supplier Payments': {
      headers: ['Purchase ID', 'Supplier', 'Date', 'Amount (INR)', 'Method'],
      rows: supplierPayments
    }
  };
}

function paymentRows_(record) {
  if (Array.isArray(record.payments) && record.payments.length) return record.payments;
  if (numeric_(record.paidAmount) > 0) {
    return [{ date: record.date || '', amount: record.paidAmount, method: record.method || '' }];
  }
  return [];
}

function sameCustomer_(customer, bill) {
  const customerPhone = digits_(customer.phone);
  const billPhone = digits_(bill.phone);
  if (customerPhone && billPhone) return customerPhone === billPhone;
  return String(customer.name || '').trim().toLowerCase() ===
    String(bill.customer || '').trim().toLowerCase();
}

function digits_(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits ? digits.slice(-10) : '';
}

function numeric_(value) {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

function safeCell_(value) {
  if (typeof value === 'string' && /^[=+\-@]/.test(value)) return "'" + value;
  return value == null ? '' : value;
}

function writeTab_(spreadsheet, name, table) {
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) sheet = spreadsheet.insertSheet(name);
  sheet.clearContents();
  const values = [table.headers].concat(table.rows).map(function (row) {
    return row.map(safeCell_);
  });
  if (sheet.getMaxColumns() < table.headers.length) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), table.headers.length - sheet.getMaxColumns());
  }
  if (sheet.getMaxRows() < values.length) {
    sheet.insertRowsAfter(sheet.getMaxRows(), values.length - sheet.getMaxRows());
  }
  sheet.getRange(1, 1, values.length, table.headers.length).setValues(values);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, table.headers.length)
    .setBackground('#133c70')
    .setFontColor('#ffffff')
    .setFontWeight('bold');
  sheet.autoResizeColumns(1, table.headers.length);
  for (let column = 1; column <= table.headers.length; column++) {
    if (sheet.getColumnWidth(column) > 320) sheet.setColumnWidth(column, 320);
  }
}
