# BahiPro — Your Digital Munim

BahiPro is a Python-backed retail management and analytics application. Flask serves the app and its local API, Python validates and saves workspace changes, and SQLite is the main data store. The browser interface uses JavaScript for interactive screens and remains available with local-browser storage if the Python server is offline.

## Publish a public link

The project includes a Render Blueprint in `render.yaml`. It runs the Flask app with Gunicorn on Render's free public web service.

1. In VS Code, open **Source Control**, commit the project files, then choose **Publish to GitHub**. Choose a private repository if you want to keep the source code private; the app link can still be public.
2. Create or sign in to a Render account, choose **New → Blueprint**, and connect that GitHub repository.
3. Render reads `render.yaml`. Review the free service details, then apply the Blueprint.
4. Wait for the first deploy to finish. Render will show a public `https://...onrender.com` link; share that link with visitors.

The free service gives you a public link without a hosting charge. Render may put it to sleep after 15 minutes without traffic, so the first visit after a quiet period can take longer. Its server-side SQLite files are temporary and may be removed during restarts or deploys. BahiPro also saves every change in that browser's local storage and restores the server copy when that same browser returns. Keep an exported backup; clearing browser site data removes the saved workspace. For persistent server storage, Render requires a paid web plan and disk (currently starting around $7.25/month for this setup). See [Render's Flask guide](https://render.com/docs/deploy-flask), [persistent disk guide](https://render.com/docs/disks), [service sleep behavior](https://render.com/docs/faq), and [pricing](https://render.com/pricing).

Every browser profile automatically gets a separate random workspace. The link opens BahiPro for anyone, but the app has no login: the same browser profile continues to access its workspace, while a different browser or device starts empty. Use **Reports & insights → Export analysis data** and **Settings → Import previous data** to move a workspace between browsers. Do not enter sensitive financial or customer information on a shared device. Clearing that browser's site data also removes the workspace ID needed to reopen its server copy.

The deployed website has a different browser origin from the local version, so local browser storage does not copy over automatically. Before switching, open your existing BahiPro copy and choose **Reports & insights → Export analysis data**. After deployment, open the public link and choose **Settings → Import previous data** to load that JSON into your hosted workspace. Other visitors get their own empty workspace.

## Run BahiPro

Install Python 3.10 or later. Then double-click `start_bahipro.bat`; it installs the project dependencies on first run and starts the local server. Alternatively, open PowerShell in the project folder and run:

```powershell
python -m pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:8000` in your browser. Keep the terminal window open while using BahiPro. The first run creates a separate hashed SQLite database under `data/workspaces/` for that browser. The server binds to this computer only.

If PowerShell says Python was not found, install Python and enable **Add python.exe to PATH**, then reopen PowerShell and retry the commands.

## What Python handles

- Flask routes for the app, workspace API, assistant, and analytics suggestions
- SQLite storage for the store profile, products, customers, bills, payments, purchases, and line items
- Validation and transactional updates that keep the saved workspace and SQL reporting tables in sync
- Local retail analysis for pending balances, reorder suggestions, sales movement, top products, customers, purchases, and estimated margins

The dashboard's BahiPro assistant uses local rules and SQL queries; it does not call a cloud AI service. The JavaScript interface still handles page layout, forms, charts, invoice previews, printing, and browser interactions.

## Features

- First-run guided tour through Overview, Billing, Purchases, Inventory, Customers, Reports, Settings, and search/alerts; reopen it from **Help**
- Demo dataset import with 150 sales, 35 purchase invoices, 25 products, 18 customers, split payments, and outstanding balances
- Sales overview, pending balances, customer lifetime spend, and lifetime payment due
- Searchable billing with multiple products and paid, partial, or pending payment
- Invoice preview, print, WhatsApp share, and PDF sharing
- Inventory with sales and purchase rates, suppliers, stock adjustments, and CSV export
- Purchases with supplier invoices, received stock, partial payments, and balances due
- Customer and product create, edit, search, and remove options
- Store profile, business sector, customer company names, and branded invoices
- Google Sheets reporting with automatic updates after saved changes
- SQL and Python analytics pipeline that builds a SQLite report database, CSV reports, and charts

## Data storage and backup

The Python server stores each browser workspace in a separate, hashed SQLite file under `data/workspaces/`. The app also keeps a browser copy for continuity and offline use. When the server is offline, edits stay in that browser and are reconciled when the Python server reconnects. On free hosting, the server copy is temporary; the browser copy remains the durable copy for that browser. Use **Reports & insights → Export analysis data** or the CSV exports to keep a portable backup.

New workspaces start empty, with no sample store or demo products. **Settings → Reset data** asks for confirmation and clears the profile, products, customers, bills, and purchases from this app's browser cache and SQLite database. It does not clear a separate Google Sheet.

To move data from the earlier browser-only app, open that copy, choose **Reports & insights → Export analysis data**, then open the Python version and choose **Settings → Import previous data**. Select the downloaded BahiPro JSON export once; it will be saved to SQLite.

The local app has no account sign-in. When deployed, its selected hosting provider stores the workspace database; each browser gets a separate workspace identifier. The Flask development server is only for local use; use the Render Blueprint and Gunicorn for a public deployment.

Google Sheets connection settings remain stored in the browser. The deployed link has separate browser storage from your local copy, so reconnect Google Sheets from **Reports & insights** on the deployed site. The export token is not included in the GitHub project.

## SQL and Python analytics reports

From **Reports & insights**, choose **Export analysis data** to download a JSON snapshot with bills and line items, payments, customers, products, and purchases. The snapshot can contain customer contact details, so keep it secure.

To generate the separate report pack from a snapshot:

```powershell
python -m pip install -r requirements.txt
python analytics/analyze_retail.py --input path/to/bahipro-analytics.json
```

The pipeline creates `analytics/output/bahipro_analytics.sqlite`, runs `analytics/queries.sql`, and saves CSV reports and charts under `analytics/output/reports` and `analytics/output/charts`. See [analytics/README.md](analytics/README.md) for the schema and report definitions.

## Google Sheets

Connect Sheets from **Reports & insights** with the Apps Script web app URL and export token from your Google account setup. Saved workspace changes sync automatically to separate tabs for bills, line items, payments, customers, inventory, purchases, supplier payments, and an overview. See [analytics/README.md](analytics/README.md) for the one-time Apps Script setup.
