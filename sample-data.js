/* Fictional retail records for demonstrating BahiPro's reports and workflows. */
(function () {
  const productCatalog = [
    ["Basmati Rice 5 kg", "Grocery", 650, 520, "🌾"],
    ["Toor Dal 1 kg", "Grocery", 190, 150, "🫘"],
    ["Sunflower Oil 1 L", "Grocery", 165, 132, "🫒"],
    ["Sugar 1 kg", "Grocery", 52, 42, "🍚"],
    ["Whole Wheat Atta 5 kg", "Grocery", 285, 235, "🌾"],
    ["Salt 1 kg", "Grocery", 25, 16, "🧂"],
    ["Tea 500 g", "Beverages", 280, 220, "🍵"],
    ["Coffee 200 g", "Beverages", 245, 190, "☕"],
    ["Milk 1 L", "Dairy", 66, 54, "🥛"],
    ["Curd 500 g", "Dairy", 45, 34, "🥣"],
    ["Bread Loaf", "Bakery", 45, 32, "🍞"],
    ["Eggs 12 Pack", "Dairy", 95, 76, "🥚"],
    ["Butter 100 g", "Dairy", 62, 48, "🧈"],
    ["Biscuits Family Pack", "Snacks", 80, 58, "🍪"],
    ["Potato Chips", "Snacks", 40, 27, "🥔"],
    ["Chocolate Bar", "Snacks", 50, 33, "🍫"],
    ["Soft Drink 750 ml", "Beverages", 48, 33, "🥤"],
    ["Mineral Water 1 L", "Beverages", 20, 12, "💧"],
    ["Dishwash Liquid 500 ml", "Household", 115, 85, "🧽"],
    ["Laundry Powder 1 kg", "Household", 150, 112, "🧺"],
    ["Bath Soap 3 Pack", "Personal Care", 135, 96, "🧼"],
    ["Shampoo 180 ml", "Personal Care", 175, 132, "🧴"],
    ["Toothpaste 150 g", "Personal Care", 125, 92, "🪥"],
    ["Notebook 200 Pages", "Stationery", 85, 55, "📓"],
    ["Ball Pen 5 Pack", "Stationery", 60, 38, "🖊️"]
  ];

  const customerNames = [
    "Aarav Mehta", "Aditi Rao", "Anaya Iyer", "Arjun Nair", "Diya Kapoor", "Ishaan Shah",
    "Kavya Menon", "Kabir Joshi", "Mira Desai", "Neel Verma", "Riya Patel", "Rohan Kulkarni",
    "Sana Khan", "Vihaan Reddy", "Tara Bose", "Dev Malhotra", "Nisha Shetty", "Rehan Ali"
  ];
  const companyNames = [
    "Green Basket Cafe", "Lakeview Office", "Bluebell Studio", "Northside Hostel",
    "Maple Corner Shop", "Bright Day Clinic"
  ];
  const suppliers = [
    "Metro Wholesale", "FreshCart Distributors", "Cityline Traders", "Evergreen Supply Co.",
    "Prime Retail Goods", "Sunrise Wholesale"
  ];
  const paymentMethods = ["UPI", "Cash", "Card", "Bank transfer"];

  function createRandom() {
    let state = 0xBA4170;
    return function random() {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 4294967296;
    };
  }

  function roundMoney(value) {
    return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
  }

  function pad(value, length = 2) {
    return String(value).padStart(length, "0");
  }

  function dateDaysAgo(days) {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() - days);
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function dateAfter(isoDate, days) {
    const [year, month, day] = isoDate.split("-").map(Number);
    const date = new Date(year, month - 1, day, 12);
    date.setDate(date.getDate() + days);
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function createPayment(total, mode, transactionDate, daysAgo, random, split) {
    if (mode === "pending") return { paidAmount: 0, method: "Credit", payments: [] };

    const paidAmount = mode === "paid"
      ? roundMoney(total)
      : roundMoney(total * (0.24 + random() * 0.48));
    const methods = paymentMethods;
    const chunks = split && mode === "partial"
      ? [roundMoney(paidAmount * 0.58), roundMoney(paidAmount - roundMoney(paidAmount * 0.58))]
      : [paidAmount];
    const maxDaysAfter = Math.min(28, daysAgo);
    const paymentOffsets = chunks.length === 1
      ? [Math.floor(random() * (maxDaysAfter + 1))]
      : [Math.floor(maxDaysAfter * 0.28), Math.floor(maxDaysAfter * 0.82)];
    const payments = chunks.map((amount, index) => ({
      date: dateAfter(transactionDate, paymentOffsets[index]),
      amount,
      method: methods[Math.floor(random() * methods.length)]
    }));
    payments.sort((left, right) => left.date.localeCompare(right.date));
    return { paidAmount, method: payments[payments.length - 1].method, payments };
  }

  function chooseMode(index, interval) {
    const position = index % interval;
    if (position < interval * 0.6) return "paid";
    if (position < interval * 0.9) return "partial";
    return "pending";
  }

  function createPurchase(idNumber, dateAge, lines, supplier, mode, random, split) {
    const date = dateDaysAgo(dateAge);
    const total = roundMoney(lines.reduce((sum, line) => sum + line.lineTotal, 0));
    const payment = createPayment(total, mode, date, dateAge, random, split);
    const status = payment.paidAmount >= total
      ? "Paid"
      : payment.paidAmount > 0 ? "Partially paid" : "Pending";
    return {
      id: `PUR-SMP-${pad(idNumber, 4)}`,
      invoiceNumber: `DEMO-PO-${pad(idNumber, 4)}`,
      supplier,
      date,
      items: lines.reduce((sum, line) => sum + line.quantity, 0),
      lines,
      total,
      paidAmount: payment.paidAmount,
      status,
      method: payment.method,
      payments: payment.payments
    };
  }

  window.createBahiProSampleWorkspace = function createBahiProSampleWorkspace() {
    const random = createRandom();
    const randomInt = (min, max) => min + Math.floor(random() * (max - min + 1));
    const products = productCatalog.map(([name, category, price, purchaseRate, emoji], index) => ({
      id: `SKU-SMP-${pad(index + 1)}`,
      name,
      category,
      price,
      purchaseRate,
      purchaseRateEstimated: false,
      stock: 0,
      reorder: 12 + (index % 11),
      supplier: "Metro Wholesale",
      lastPurchaseDate: "",
      emoji
    }));
    const customers = customerNames.map((name, index) => ({
      id: `C-SMP-${pad(index + 1)}`,
      name,
      companyName: index % 3 === 0 ? companyNames[index % companyNames.length] : "",
      phone: `000000${pad(index + 1, 4)}`,
      email: `sample.customer${pad(index + 1)}@example.com`,
      createdAt: dateDaysAgo(250 + index),
      visits: 0,
      spent: 0
    }));

    const soldUnits = new Map(products.map(product => [product.id, 0]));
    const bills = [];
    for (let index = 0; index < 150; index += 1) {
      const daysAgo = Math.max(0, 149 - Math.floor(index * 150 / 150) - randomInt(0, 1));
      const date = dateDaysAgo(daysAgo);
      const customer = customers[randomInt(0, customers.length - 1)];
      const selected = new Set();
      const lineCount = randomInt(1, 4);
      while (selected.size < lineCount) selected.add(randomInt(0, products.length - 1));
      const lines = [...selected].map(productIndex => {
        const product = products[productIndex];
        const quantity = randomInt(1, 4);
        const lineTotal = roundMoney(product.price * quantity);
        soldUnits.set(product.id, soldUnits.get(product.id) + quantity);
        return {
          productId: product.id,
          productName: product.name,
          category: product.category,
          quantity,
          unitPrice: product.price,
          lineTotal
        };
      });
      const total = roundMoney(lines.reduce((sum, line) => sum + line.lineTotal, 0));
      const mode = chooseMode(index, 10);
      const payment = createPayment(total, mode, date, daysAgo, random, index % 3 === 0);
      customer.visits += 1;
      customer.spent = roundMoney(customer.spent + total);
      bills.push({
        id: `INV-SMP-${pad(index + 1, 4)}`,
        customerId: customer.id,
        customer: customer.name,
        customerCompanyName: customer.companyName,
        phone: customer.phone,
        date,
        items: lines.reduce((sum, line) => sum + line.quantity, 0),
        lines,
        total,
        status: payment.paidAmount >= total ? "Paid" : "Pending",
        method: payment.method,
        paidAmount: payment.paidAmount,
        payments: payment.payments
      });
    }

    const purchases = [];
    const purchasedUnits = new Map(products.map(product => [product.id, 0]));
    let purchaseNumber = 1;
    products.forEach((product, index) => {
      const purchaseRate = product.purchaseRate;
      const quantity = soldUnits.get(product.id) + 8;
      const lineTotal = roundMoney(quantity * purchaseRate);
      const lines = [{
        productId: product.id,
        productName: product.name,
        quantity,
        purchaseRate,
        lineTotal
      }];
      const dateAge = 210 - index;
      const supplier = suppliers[index % suppliers.length];
      purchases.push(createPurchase(
        purchaseNumber,
        dateAge,
        lines,
        supplier,
        chooseMode(purchaseNumber - 1, 10),
        random,
        purchaseNumber % 3 === 0
      ));
      purchasedUnits.set(product.id, purchasedUnits.get(product.id) + quantity);
      product.supplier = supplier;
      product.lastPurchaseDate = dateDaysAgo(dateAge);
      product.lastPurchaseInvoice = `DEMO-PO-${pad(purchaseNumber, 4)}`;
      purchaseNumber += 1;
    });

    for (let extra = 0; extra < 10; extra += 1) {
      const selected = new Set();
      const lineCount = randomInt(3, 5);
      while (selected.size < lineCount) selected.add(randomInt(0, products.length - 1));
      const supplier = suppliers[(extra + 2) % suppliers.length];
      const lines = [...selected].map(productIndex => {
        const product = products[productIndex];
        const purchaseRate = roundMoney(product.purchaseRate * (0.98 + random() * 0.04));
        const quantity = randomInt(8, 18);
        const lineTotal = roundMoney(quantity * purchaseRate);
        purchasedUnits.set(product.id, purchasedUnits.get(product.id) + quantity);
        product.purchaseRate = purchaseRate;
        product.supplier = supplier;
        return { productId: product.id, productName: product.name, quantity, purchaseRate, lineTotal };
      });
      const dateAge = 180 - extra * 3;
      const purchase = createPurchase(
        purchaseNumber,
        dateAge,
        lines,
        supplier,
        chooseMode(purchaseNumber - 1, 10),
        random,
        purchaseNumber % 3 === 0
      );
      purchases.push(purchase);
      lines.forEach(line => {
        const product = products.find(item => item.id === line.productId);
        product.lastPurchaseDate = purchase.date;
        product.lastPurchaseInvoice = purchase.invoiceNumber;
      });
      purchaseNumber += 1;
    }

    products.forEach(product => {
      product.stock = purchasedUnits.get(product.id) - soldUnits.get(product.id);
    });
    bills.sort((left, right) => right.date.localeCompare(left.date) || right.id.localeCompare(left.id));
    purchases.sort((left, right) => right.date.localeCompare(left.date) || right.id.localeCompare(left.id));

    return {
      profile: {
        name: "BahiPro Demo Owner",
        role: "Store owner",
        storeName: "BahiPro Sample Store",
        location: "Bengaluru",
        businessSector: "Grocery & convenience retail"
      },
      products,
      bills,
      customers,
      purchases
    };
  };

  document.addEventListener("click", event => {
    const button = event.target.closest('[data-action="sample-data"]');
    if (!button) return;
    const confirmed = window.confirm(
      "Replace this app workspace with 150 sample sales, 35 sample purchases, 25 products, and 18 customers? Current app data will be replaced. Export it first if you need to keep it. A separate Google Sheet will not be changed."
    );
    if (!confirmed) return;
    if (typeof window.createBahiProSampleWorkspace !== "function") {
      toast("The sample data could not be loaded. Refresh the app and try again.");
      return;
    }
    store = window.createBahiProSampleWorkspace();
    saveStore({ syncSheets: false });
    updateNavBadge();
    renderPage();
    toast("Sample data loaded: 150 sales, 35 purchases, 25 products, 18 customers.");
  });
})();
