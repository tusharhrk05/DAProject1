# BahiPro retail analytics

This local pipeline turns a BahiPro workspace export into a relational SQLite database, named SQL analysis reports, CSV outputs, and PNG charts. It reads a snapshot; there is no live connection to browser local storage and it does not change the app's records.

## Run it

1. Open BahiPro in the browser that contains your store records.
2. Go to **Reports & insights** and click **Export analysis data**.
3. Install the project dependencies from the project folder:

   ```powershell
   python -m pip install -r requirements.txt
   ```

   Use Python 3.10 or later.

4. Import the downloaded JSON file:

   ```powershell
   python analytics/analyze_retail.py --input path/to/bahipro-analytics.json
   ```

Use `--output-dir path/to/folder` to choose a different destination. Each run replaces the output database with the selected snapshot and recreates its reports and charts.

## Data model

`schema.sql` defines customers, products, bills, bill line items, customer payment events, purchases, purchase line items, and supplier payment events. Invoice and purchase headers keep the totals and payment balances recorded by the app. Detail tables preserve the transaction-level records needed for product, category, customer, and supplier analysis.

`queries.sql` contains the SQL used to create the report pack:

- Business sales, collection, outstanding balance, and average-bill KPIs
- Monthly sales and collection trend
- Sales and units by category
- Best-selling products
- Customer lifetime visits, spend, paid, and pending amounts
- Stock status and inventory cost value
- Purchase totals and payables by supplier
- Recorded customer payment methods

The Python script loads the JSON snapshot into SQLite, executes each named query with pandas, exports the result to `analytics/output/reports/*.csv`, and creates charts in `analytics/output/charts/*.png`. Inventory value uses the product's current purchase rate; a rate marked estimated by the app is flagged in the inventory report and should be treated as an estimate. If a new store has no transactions yet, the sales and customer reports remain empty while the inventory report is still useful.

The JSON export includes customer names, company names, phone numbers, and email addresses when present. Store the export and generated database securely.

## Export directly to Google Sheets

The Reports page can send the current workspace to a Google spreadsheet through the included Apps Script receiver. Each business deploys its own receiver and selects its own spreadsheet; no Google account connection is built into or shared by this static app.

1. Create a Google spreadsheet for the store and copy its ID from the URL between `/d/` and `/edit`.
2. Open [script.google.com](https://script.google.com), create a standalone Apps Script project, and paste `Code.gs` from this folder.
3. In the script's **Project Settings → Script Properties**, add `BAHIPRO_SPREADSHEET_ID` with the spreadsheet ID and `BAHIPRO_EXPORT_TOKEN` with a long random secret (at least 32 characters).
4. In the editor, select and run `authorizeBahiProSheetsExport` once, then approve the requested Sheets access.
5. Select **Deploy → New deployment → Web app**. Set **Execute as** to your account and **Who has access** to **Anyone** if your Google account permits it. Deploy and copy the URL ending in `/exec`.
6. In BahiPro, open **Reports & insights → Connect Google Sheets**, paste the web app URL and the same token, and save. Choose **Export to Google Sheets** to send the workspace.

The receiver checks the token and only writes to the spreadsheet ID stored in its script properties. The token is saved in this browser's local storage; keep it private and use the app only on a device you trust. A Sheets export replaces the contents of the receiver's named BahiPro tabs, leaving unrelated spreadsheet tabs alone. After the connection is saved, each successful app save automatically syncs the workspace to Sheets after a short pause. The export button remains available for a manual sync. If your account does not allow anonymous web apps, use the CSV exports and import those files into Sheets.

If you replace `Code.gs` with an updated version, open **Deploy → Manage deployments**, click the edit icon for your web app, choose **New version**, and deploy it again. BahiPro polls the receiver for a result and shows the updated tab names or a returned error. If it reports no reply, check that the saved URL is the deployed `/exec` URL and that the deployment is accessible.
