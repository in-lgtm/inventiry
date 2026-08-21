# Material Inventory Management System

A password-protected Streamlit app for managing material/product inventory,
backed by a real **SQLite database** with separate folders for uploaded files:

```
material_inventory/
├── app.py              ← the whole application
├── requirements.txt
├── inventory.db         ← created automatically on first run (SQLite database)
├── images/               ← uploaded product photos are saved here
└── datasheets/           ← uploaded technical datasheets (PDF/image) are saved here
```

**Database tables**
- `products` — one row per product (SKU, name, description, pricing, supplier,
  stock levels, location, technical data, plus the *path* to its photo/datasheet
  file — not the file itself, so the DB stays small and fast).
- `stock_entries` — every stock movement/restock entry for a product (date,
  quantity, price, note), linked to `products` by `product_id`. Multiple
  entries per product are fully supported, exactly like the original mock-up.

## 1. Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). Log in with:

```

```

The database (`inventory.db`) and the `images/` / `datasheets/` folders are
created automatically the first time the app runs — nothing to configure.
12 sample products are pre-loaded so you can see it working immediately;
delete them from the app once you add your real inventory.

## 2. Deploy it for free (Streamlit Community Cloud) — works immediately

1. Create a new **public or private GitHub repo** and push this entire folder
   to it (including `requirements.txt`).
2. Go to **https://share.streamlit.io** → "New app" → pick your repo/branch →
   set **Main file path** to `app.py` → Deploy.
3. That's it — no extra configuration needed. The app builds its own database
   and folders on first launch.

### Changing the password without touching the code
Instead of the built-in fallback password, you can set your own in
Streamlit Cloud under **App settings → Secrets**:

```toml
APP_PASSWORD = "your-new-password"
```

If no secret is set, the app uses the default password above.

### ⚠️ Important note on file persistence
Streamlit Community Cloud's filesystem is **ephemeral** — it's reset whenever
the app redeploys, sleeps for inactivity, or is restarted. That means
`inventory.db`, `images/`, and `datasheets/` will persist while the app is
running, but **could be wiped on a redeploy**. For a small internal tool this
is often fine, but if you need guaranteed long-term persistence, either:
- Deploy on a host with a persistent disk (Render, Railway, a VPS, Fly.io, etc.)
  — the same `app.py` works unchanged there, or
- Point `DB_PATH` / `IMAGES_DIR` / `DATASHEETS_DIR` at a mounted persistent
  volume, or
- Swap SQLite for a hosted database (e.g. Postgres) later — the DB layer is
  isolated in a handful of functions near the top of `app.py`, so this is a
  contained change.

## 3. Using the app

- **Cards tab** — browse products as photo cards with a low-stock badge.
  Click **"Open / Edit"** on any card to view/edit full details, upload a
  new photo or datasheet, and add/delete stock entries.
- **Table tab** — a spreadsheet-style overview of every product.
- **Sidebar** — search, sort (low stock first, cost, expiration, etc.),
  add a new product, export everything to CSV, and log out.
- **Add New Product** — opens a blank form; saving creates the product and
  its first stock entry.
- Deleting a product also removes its uploaded photo/datasheet files and
  its stock-entry history.

## 4. Backing up your data
Your data lives in three places: `inventory.db`, `images/`, `datasheets/`.
Back up (or download) all three together to have a complete copy of your
inventory, including uploaded files.
