"""
Material Inventory Management System
-------------------------------------
A Streamlit app backed by a real SQLite database.
- Product photos  -> saved in /images
- Datasheets (PDF) -> saved in /datasheets
- Product records + stock-entry history -> saved in inventory.db (SQLite)
- Password-protected access

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    Push this whole folder to a GitHub repo and point Streamlit Cloud's
    "New app" wizard at app.py. No extra setup is required — the database
    and folders are created automatically on first run.
"""

import os
import tempfile
import uuid
from datetime import date, datetime

import pandas as pd
import sqlite3
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def ensure_dir(path: str, _depth: int = 0) -> str:
    """
    Return a writable directory at `path`. Handles two real-world failure
    modes seen on hosted platforms:
      1. A race where multiple sessions/threads create the same folder at
         once (os.makedirs(exist_ok=True) can still raise in that window).
      2. Something already exists at `path` but is a *file*, not a folder
         (e.g. it got uploaded to the repo as a plain file named "images"
         instead of a real images/ directory). In that case we fall back
         to an alternate directory name rather than crashing.
    """
    if os.path.isdir(path):
        return path
    if os.path.exists(path) and not os.path.isdir(path):
        if _depth > 5:
            raise OSError(f"Could not find or create a usable directory near {path}")
        alt = path.rstrip("/\\") + "_data"
        return ensure_dir(alt, _depth + 1)
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except FileExistsError:
        if os.path.isdir(path):
            return path
        if _depth > 5:
            raise
        alt = path.rstrip("/\\") + "_data"
        return ensure_dir(alt, _depth + 1)


def _resolve_data_dir() -> str:
    """
    Pick a writable directory to store the database and uploaded files.
    Some hosts (Streamlit Community Cloud, certain containers) mount the
    source folder read-only, so writing next to app.py can fail with a
    PermissionError. This tries, in order:
      1. DATA_DIR environment variable, if set (lets you point at a
         mounted persistent volume on Railway/Render/etc.)
      2. the folder app.py lives in (works on most hosts, and keeps data
         next to the code for easy local development)
      3. a folder under the system temp directory (always writable, but
         not persistent across restarts — used only as a last resort)
    """
    candidates = []
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates.append(SOURCE_DIR)
    candidates.append(os.path.join(tempfile.gettempdir(), "material_inventory_data"))

    for candidate in candidates:
        try:
            resolved = ensure_dir(candidate)
            probe = os.path.join(resolved, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return resolved
        except OSError:
            continue
    return tempfile.mkdtemp(prefix="material_inventory_")


BASE_DIR = _resolve_data_dir()
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
IMAGES_DIR = ensure_dir(os.path.join(BASE_DIR, "images"))
DATASHEETS_DIR = ensure_dir(os.path.join(BASE_DIR, "datasheets"))

# Password: can be overridden via .streamlit/secrets.toml with APP_PASSWORD = "..."
# Falls back to the password below so the app works immediately out of the box.
try:
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except Exception:
    APP_PASSWORD = "Clearnanotech12@"

st.set_page_config(page_title="Material Inventory Management System", page_icon="📦", layout="wide")

ICONS = ["📦", "🏷️", "🧪", "⚡", "🛢️", "🔧"]

PRODUCT_FIELDS = [
    "sku", "icon", "product", "description", "where_used", "characteristics",
    "source_origin", "batch_lot", "sds_hazard_class", "temp_range", "cure_time", "mix_ratio",
    "suppliers", "price", "discount", "transport_price", "expiring_date", "delivery_time",
    "ubication", "monthly_usage", "min_stock", "quantity", "photo_path", "datasheet_path",
]

# ----------------------------------------------------------------------------
# DATABASE
# ----------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


conn = get_connection()


def insert_product(data: dict) -> int:
    cur = conn.cursor()
    cols = PRODUCT_FIELDS + ["created_at"]
    values = [data.get(f) for f in PRODUCT_FIELDS] + [datetime.now().isoformat()]
    placeholders = ",".join(["?"] * len(cols))
    cur.execute(f"INSERT INTO products ({','.join(cols)}) VALUES ({placeholders})", values)
    conn.commit()
    return cur.lastrowid


def update_product(product_id: int, data: dict):
    if not data:
        return
    cur = conn.cursor()
    sets = ",".join([f"{f}=?" for f in data.keys()])
    values = list(data.values()) + [product_id]
    cur.execute(f"UPDATE products SET {sets} WHERE id=?", values)
    conn.commit()


def get_product(product_id: int):
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (product_id,))
    return cur.fetchone()


def get_all_products() -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM products ORDER BY id DESC", conn)


def delete_product_db(product_id: int):
    p = get_product(product_id)
    if p:
        for col in ("photo_path", "datasheet_path"):
            rel = p[col]
            if rel:
                full = os.path.join(BASE_DIR, rel)
                if os.path.exists(full):
                    try:
                        os.remove(full)
                    except OSError:
                        pass
    cur = conn.cursor()
    cur.execute("DELETE FROM stock_entries WHERE product_id=?", (product_id,))
    cur.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()


def get_entries(product_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM stock_entries WHERE product_id=? ORDER BY entry_date ASC, id ASC",
        conn, params=(product_id,),
    )


def add_stock_entry_db(product_id: int, entry_date: str, quantity: float, price: float, note: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO stock_entries (product_id, entry_date, quantity, price, note) VALUES (?,?,?,?,?)",
        (product_id, entry_date, quantity, price, note or ""),
    )
    # Mirror the pattern from the original app: latest entry becomes current qty/price
    cur.execute("UPDATE products SET quantity=?, price=? WHERE id=?", (quantity, price, product_id))
    conn.commit()


def delete_stock_entry_db(entry_id: int, product_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM stock_entries WHERE id=?", (entry_id,))
    conn.commit()
    remaining = get_entries(product_id)
    if not remaining.empty:
        latest = remaining.iloc[-1]
        cur.execute(
            "UPDATE products SET quantity=?, price=? WHERE id=?",
            (float(latest["quantity"]), float(latest["price"]), product_id),
        )
        conn.commit()


def seed_default_data():
    samples = [
        dict(sku="MAT-VEL-401", icon="🏷️", product="Velcro 401 Black",
             description="1 Box x 350m + 8 units x 25m. Total: 550m.",
             where_used="Vertical/horizontal textile fastening and modular panels.",
             characteristics="1 Box = 14 U | Breakdown: 1 Box x 350m + 8 U x 25m",
             source_origin="Barcelona, Spain", batch_lot="LOT-VEL401-26", sds_hazard_class="Non-hazardous",
             temp_range="-20C to +90C", cure_time="Immediate", mix_ratio="N/A",
             suppliers="Velcro Industrial", price=120.00, discount=5, transport_price=10.00,
             expiring_date="2030-12-31", delivery_time=5, ubication="Zone A - Rack 01",
             monthly_usage=200, min_stock=250, quantity=550,
             entries=[("2026-08-01", 500, 115.00, "Initial monthly batch"),
                      ("2026-08-21", 550, 120.00, "Restock update (+50m)")]),
        dict(sku="MAT-VEL-758", icon="🏷️", product="Velcro 758 Black",
             description="20 Box x 495m + 7 units x 45m. Total: 10,215m.",
             where_used="Closure of large covers and insulating curtains.",
             characteristics="1 Box = 11 U | Breakdown: 20 Box x 495m + 7 U x 45m",
             source_origin="Barcelona, Spain", batch_lot="LOT-VEL758-26", sds_hazard_class="Non-hazardous",
             temp_range="-20C to +90C", cure_time="Immediate", mix_ratio="N/A",
             suppliers="Velcro Industrial", price=180.00, discount=8, transport_price=15.00,
             expiring_date="2030-12-31", delivery_time=5, ubication="Zone A - Rack 02",
             monthly_usage=1500, min_stock=2000, quantity=10215,
             entries=[("2026-08-05", 10000, 175.00, "Bulk shipment"),
                      ("2026-08-21", 10215, 180.00, "Inventory check update")]),
        dict(sku="MAT-GLU-TUN400", icon="🧪", product="Glue Tunsan 400 ml",
             description="23 Box x 28 U + 10 loose units. Total: 654 U.",
             where_used="Fast sealing of casings and light adhesion.",
             characteristics="1 Box = 28 U | Breakdown: 23 Box x 28 U + 10 U loose",
             source_origin="Valencia, Spain", batch_lot="LOT-TUN-400-A", sds_hazard_class="Class 3 Flammable",
             temp_range="-10C to +80C", cure_time="20 min", mix_ratio="Single-component",
             suppliers="Tunsan Chemical Supplies", price=8.50, discount=5, transport_price=0.80,
             expiring_date="2027-06-30", delivery_time=4, ubication="Zone B - Shelf 01",
             monthly_usage=150, min_stock=100, quantity=654,
             entries=[("2026-08-10", 600, 8.20, "Initial delivery"),
                      ("2026-08-21", 654, 8.50, "Weekly count (+54 U)")]),
        dict(sku="MAT-GLU-HUI600", icon="🧪", product="Glue HUITIAN 600 ml",
             description="15 loose units. Total: 15 U.",
             where_used="Elastic and industrial sealing of partitions.",
             characteristics="1 Box = 20 U | Total Stock: 15 U loose",
             source_origin="Hubei, China", batch_lot="LOT-HUI-600X", sds_hazard_class="Irritant",
             temp_range="-30C to +100C", cure_time="24h", mix_ratio="Single-component",
             suppliers="Huitian Adhesives", price=12.00, discount=0, transport_price=1.20,
             expiring_date="2027-04-15", delivery_time=7, ubication="Zone B - Shelf 02",
             monthly_usage=30, min_stock=20, quantity=15,
             entries=[("2026-08-15", 15, 12.00, "Remaining stock check")]),
        dict(sku="MAT-GLU-DOW600", icon="🧪", product="Glue DOW 600 ml",
             description="13 loose units. Total: 13 U.",
             where_used="Glass sealing and structural joints.",
             characteristics="1 Box = 20 U | Total Stock: 13 U loose",
             source_origin="Wiesbaden, Germany", batch_lot="LOT-DOW-600D", sds_hazard_class="Low VOC",
             temp_range="-40C to +120C", cure_time="12h", mix_ratio="Single-component",
             suppliers="Dow Chemical Europe", price=16.50, discount=10, transport_price=1.50,
             expiring_date="2027-09-30", delivery_time=3, ubication="Zone B - Shelf 03",
             monthly_usage=40, min_stock=25, quantity=13,
             entries=[("2026-08-15", 13, 16.50, "Stock count")]),
        dict(sku="MAT-GLU-SEA600", icon="🧪", product="Glue SEAL 600 ml",
             description="3 Box x 12 U. Total: 36 U.",
             where_used="Waterproof sealing of frames and moldings.",
             characteristics="1 Box = 12 U | Breakdown: 3 Box x 12 U",
             source_origin="Milan, Italy", batch_lot="LOT-SEA-36X", sds_hazard_class="Non-hazardous",
             temp_range="-20C to +90C", cure_time="24h", mix_ratio="Single-component",
             suppliers="Seal Industrial Solutions", price=11.00, discount=0, transport_price=1.00,
             expiring_date="2027-08-10", delivery_time=5, ubication="Zone B - Shelf 04",
             monthly_usage=25, min_stock=15, quantity=36,
             entries=[("2026-08-15", 36, 11.00, "Full boxes count")]),
        dict(sku="MAT-PV-TRAD", icon="⚡", product="PV TRADICIONAL",
             description="23 U. Total: 23 U.",
             where_used="Installation on traditional solar roofs.",
             characteristics="Standard Photovoltaic Module | Total Stock: 23 U",
             source_origin="Madrid, Spain", batch_lot="LOT-PV-TRAD-01", sds_hazard_class="Electrical",
             temp_range="-40C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="PV Solar Tech", price=140.00, discount=12, transport_price=12.00,
             expiring_date="2035-12-31", delivery_time=10, ubication="Zone C - Rack PV1",
             monthly_usage=15, min_stock=10, quantity=23,
             entries=[("2026-08-15", 23, 140.00, "Warehouse check")]),
        dict(sku="MAT-PV-560W", icon="⚡", product="PV 560W",
             description="5 U. Total: 5 U.",
             where_used="High-density solar power generation.",
             characteristics="High Efficiency Photovoltaic Panel 560W | Total Stock: 5 U",
             source_origin="Jiangsu, China", batch_lot="LOT-PV-560W-26", sds_hazard_class="Electrical",
             temp_range="-40C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="PV Solar Tech", price=210.00, discount=15, transport_price=18.00,
             expiring_date="2035-12-31", delivery_time=10, ubication="Zone C - Rack PV2",
             monthly_usage=8, min_stock=10, quantity=5,
             entries=[("2026-08-15", 5, 210.00, "Initial batch")]),
        dict(sku="MAT-PV-WGV", icon="📦", product="PV White Glue Velcro Vertical",
             description="127 U. Total: 127 U.",
             where_used="Fast photovoltaic assembly, vertical position on tarp.",
             characteristics="White PV Panel with Integrated Vertical Velcro | Total Stock: 127 U",
             source_origin="Porto, Portugal", batch_lot="LOT-PV-WGV-127", sds_hazard_class="Non-hazardous",
             temp_range="-30C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="Custom Solar Flex", price=165.00, discount=10, transport_price=14.00,
             expiring_date="2032-12-31", delivery_time=7, ubication="Zone C - Rack PV3",
             monthly_usage=50, min_stock=30, quantity=127,
             entries=[("2026-08-15", 127, 165.00, "Stock check")]),
        dict(sku="MAT-PV-WGH", icon="📦", product="PV White Glue Velcro Horizontal",
             description="2 U. Total: 2 U.",
             where_used="Fast photovoltaic assembly, horizontal position.",
             characteristics="White PV Panel with Integrated Horizontal Velcro | Total Stock: 2 U",
             source_origin="Porto, Portugal", batch_lot="LOT-PV-WGH-02", sds_hazard_class="Non-hazardous",
             temp_range="-30C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="Custom Solar Flex", price=165.00, discount=10, transport_price=14.00,
             expiring_date="2032-12-31", delivery_time=7, ubication="Zone C - Rack PV3",
             monthly_usage=20, min_stock=15, quantity=2,
             entries=[("2026-08-15", 2, 165.00, "Remaining units")]),
        dict(sku="MAT-PV-WHITE", icon="📦", product="PV White",
             description="110 U. Total: 110 U.",
             where_used="White photovoltaic architectural integration.",
             characteristics="Standard White Flex PV Module | Total Stock: 110 U",
             source_origin="Porto, Portugal", batch_lot="LOT-PV-W-110", sds_hazard_class="Non-hazardous",
             temp_range="-30C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="Custom Solar Flex", price=150.00, discount=8, transport_price=12.00,
             expiring_date="2032-12-31", delivery_time=6, ubication="Zone C - Rack PV4",
             monthly_usage=40, min_stock=25, quantity=110,
             entries=[("2026-08-15", 110, 150.00, "Stock count")]),
        dict(sku="MAT-PV-BLACK", icon="📦", product="PV Black",
             description="32 U. Total: 32 U.",
             where_used="Full Black aesthetic installations on dark surfaces.",
             characteristics="Full Black Flex PV Module | Total Stock: 32 U",
             source_origin="Porto, Portugal", batch_lot="LOT-PV-B-32", sds_hazard_class="Non-hazardous",
             temp_range="-30C to +85C", cure_time="N/A", mix_ratio="N/A",
             suppliers="Custom Solar Flex", price=155.00, discount=8, transport_price=12.00,
             expiring_date="2032-12-31", delivery_time=6, ubication="Zone C - Rack PV4",
             monthly_usage=30, min_stock=20, quantity=32,
             entries=[("2026-08-15", 32, 155.00, "Stock count")]),
    ]
    for s in samples:
        entries = s.pop("entries")
        s["photo_path"] = None
        s["datasheet_path"] = None
        pid = insert_product(s)
        cur = conn.cursor()
        for e_date, e_qty, e_price, e_note in entries:
            cur.execute(
                "INSERT INTO stock_entries (product_id, entry_date, quantity, price, note) VALUES (?,?,?,?,?)",
                (pid, e_date, e_qty, e_price, e_note),
            )
        conn.commit()


def init_db():
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT, icon TEXT, product TEXT, description TEXT, where_used TEXT,
            characteristics TEXT, source_origin TEXT, batch_lot TEXT, sds_hazard_class TEXT,
            temp_range TEXT, cure_time TEXT, mix_ratio TEXT, suppliers TEXT,
            price REAL DEFAULT 0, discount REAL DEFAULT 0, transport_price REAL DEFAULT 0,
            expiring_date TEXT, delivery_time REAL DEFAULT 0, ubication TEXT,
            monthly_usage REAL DEFAULT 0, min_stock REAL DEFAULT 0, quantity REAL DEFAULT 0,
            photo_path TEXT, datasheet_path TEXT, created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            entry_date TEXT, quantity REAL, price REAL, note TEXT,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        seed_default_data()


init_db()

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def save_uploaded_file(uploaded_file, directory: str, prefix: str) -> str:
    safe_prefix = "".join(c for c in (prefix or "product") if c.isalnum() or c in "-_") or "product"
    ext = os.path.splitext(uploaded_file.name)[1]
    fname = f"{safe_prefix}_{uuid.uuid4().hex[:8]}{ext}"
    full_path = os.path.join(directory, fname)
    with open(full_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    rel_dir = os.path.basename(directory)
    return f"{rel_dir}/{fname}"


def calc_landed_cost(price, discount, transport) -> float:
    price = price or 0
    discount = discount or 0
    transport = transport or 0
    return round((price * (1 - discount / 100)) + transport, 2)


# ----------------------------------------------------------------------------
# AUTH
# ----------------------------------------------------------------------------
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.markdown("## 🔒 Material Inventory Management System")
    st.caption("Enter the access password to continue.")
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if pwd == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

# ----------------------------------------------------------------------------
# PRODUCT DIALOG (add / edit / delete / stock entries)
# ----------------------------------------------------------------------------
@st.dialog("Product Details")
def product_dialog(product_id=None):
    is_new = product_id is None
    if is_new:
        p = {f: "" for f in PRODUCT_FIELDS}
        p.update(price=0.0, discount=0.0, transport_price=0.0, delivery_time=0.0,
                 monthly_usage=0.0, min_stock=0.0, quantity=0.0,
                 expiring_date=str(date.today()), icon="📦")
        entries_df = pd.DataFrame(columns=["id", "entry_date", "quantity", "price", "note"])
        title = "➕ New Product"
    else:
        row = get_product(product_id)
        if row is None:
            st.error("Product not found.")
            return
        p = dict(row)
        entries_df = get_entries(product_id)
        title = f"{p.get('icon') or '📦'} {p.get('product')}"

    st.subheader(title)
    if not is_new:
        st.caption(f"SKU: {p.get('sku') or '-'}  |  Supplier: {p.get('suppliers') or '-'}  |  Location: {p.get('ubication') or '-'}")

    st.markdown("#### 🖼️ Product Photo")
    pc1, pc2 = st.columns([1, 2])
    with pc1:
        if p.get("photo_path") and os.path.exists(os.path.join(BASE_DIR, p["photo_path"])):
            st.image(os.path.join(BASE_DIR, p["photo_path"]), width=160)
        else:
            st.markdown(
                "<div style='height:110px;width:140px;background:#1e293b;color:#94a3b8;"
                "display:flex;align-items:center;justify-content:center;border-radius:8px;"
                "font-size:11px;font-weight:700;text-align:center;'>NO PHOTO</div>",
                unsafe_allow_html=True,
            )
    with pc2:
        photo_file = st.file_uploader("Upload photo (PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"photo_{product_id}")

    st.markdown("#### 📄 Technical Datasheet")
    dc1, dc2 = st.columns([1, 2])
    with dc1:
        if p.get("datasheet_path") and os.path.exists(os.path.join(BASE_DIR, p["datasheet_path"])):
            st.success("Datasheet attached")
            with open(os.path.join(BASE_DIR, p["datasheet_path"]), "rb") as f:
                st.download_button("⬇️ Download", f, file_name=os.path.basename(p["datasheet_path"]), key=f"dl_{product_id}")
        else:
            st.warning("No datasheet attached")
    with dc2:
        datasheet_file = st.file_uploader("Upload datasheet (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"], key=f"ds_{product_id}")

    st.markdown("#### 📘 Overview")
    product_name = st.text_input("Product Name", value=p.get("product") or "")
    sku = st.text_input("SKU", value=p.get("sku") or "")
    icon = st.selectbox("Icon", ICONS, index=ICONS.index(p.get("icon")) if p.get("icon") in ICONS else 0)
    description = st.text_area("Description / Breakdown", value=p.get("description") or "", height=70)
    where_used = st.text_area("Where Used (Assembly line / process)", value=p.get("where_used") or "", height=70)
    characteristics = st.text_area("Characteristics & Packaging Format", value=p.get("characteristics") or "", height=70)

    st.markdown("#### 🔬 Technical Data")
    t1, t2, t3 = st.columns(3)
    with t1:
        source_origin = st.text_input("Source Origin", value=p.get("source_origin") or "")
        temp_range = st.text_input("Temp Range", value=p.get("temp_range") or "")
    with t2:
        batch_lot = st.text_input("Batch / Lot #", value=p.get("batch_lot") or "")
        cure_time = st.text_input("Cure Time", value=p.get("cure_time") or "")
    with t3:
        sds_hazard_class = st.text_input("SDS Classification", value=p.get("sds_hazard_class") or "")
        mix_ratio = st.text_input("Mix Ratio", value=p.get("mix_ratio") or "")

    st.markdown("#### 📦 Inventory Controls")
    i1, i2, i3, i4 = st.columns(4)
    with i1:
        quantity = st.number_input("Total Quantity", value=float(p.get("quantity") or 0))
    with i2:
        min_stock = st.number_input("Min Stock", value=float(p.get("min_stock") or 0))
    with i3:
        ubication = st.text_input("Location", value=p.get("ubication") or "")
    with i4:
        try:
            exp_default = datetime.strptime(p.get("expiring_date") or str(date.today()), "%Y-%m-%d").date()
        except Exception:
            exp_default = date.today()
        expiring_date = st.date_input("Expiration Date", value=exp_default)

    st.markdown("#### 💰 Pricing & Supplier")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        suppliers = st.text_input("Supplier", value=p.get("suppliers") or "")
    with s2:
        price = st.number_input("Price (€)", value=float(p.get("price") or 0), step=0.01, format="%.2f")
    with s3:
        discount = st.number_input("Discount (%)", value=float(p.get("discount") or 0))
    with s4:
        transport_price = st.number_input("Transport (€)", value=float(p.get("transport_price") or 0), step=0.01, format="%.2f")

    d1, d2 = st.columns(2)
    with d1:
        delivery_time = st.number_input("Delivery Time (days)", value=float(p.get("delivery_time") or 0))
    with d2:
        monthly_usage = st.number_input("Monthly Usage", value=float(p.get("monthly_usage") or 0))

    st.caption(f"📊 Landed Cost: €{calc_landed_cost(price, discount, transport_price):.2f}")

    if not is_new:
        st.markdown("#### 📅 Stock Entry History")
        if not entries_df.empty:
            st.dataframe(entries_df[["entry_date", "quantity", "price", "note"]], width="stretch", hide_index=True)
            options = [None] + list(entries_df["id"])
            del_id = st.selectbox("Delete an entry", options=options, format_func=lambda x: "—" if x is None else f"Entry #{x}")
            if del_id and st.button("🗑️ Delete selected entry"):
                delete_stock_entry_db(int(del_id), product_id)
                st.rerun()
        else:
            st.caption("No entries recorded.")

        st.markdown("##### ➕ Add New Stock Entry")
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            e_date = st.date_input("Entry date", value=date.today(), key=f"edate_{product_id}")
        with e2:
            e_qty = st.number_input("Entry quantity", value=0.0, key=f"eqty_{product_id}")
        with e3:
            e_price = st.number_input("Entry price (€)", value=0.0, step=0.01, format="%.2f", key=f"eprice_{product_id}")
        with e4:
            e_note = st.text_input("Note", key=f"enote_{product_id}")
        if st.button("➕ Add Entry"):
            add_stock_entry_db(product_id, str(e_date), e_qty, e_price, e_note)
            st.rerun()

    st.divider()
    b1, b2, b3 = st.columns(3)
    save_clicked = b1.button("💾 Save Product", type="primary", width="stretch")
    cancel_clicked = b2.button("Cancel", width="stretch")
    delete_clicked = (not is_new) and b3.button("🗑️ Delete Product", width="stretch")

    if cancel_clicked:
        st.rerun()

    if delete_clicked:
        delete_product_db(product_id)
        st.rerun()

    if save_clicked:
        data = {
            "sku": sku, "icon": icon, "product": product_name, "description": description,
            "where_used": where_used, "characteristics": characteristics,
            "source_origin": source_origin, "batch_lot": batch_lot, "sds_hazard_class": sds_hazard_class,
            "temp_range": temp_range, "cure_time": cure_time, "mix_ratio": mix_ratio,
            "suppliers": suppliers, "price": price, "discount": discount, "transport_price": transport_price,
            "expiring_date": str(expiring_date), "delivery_time": delivery_time, "ubication": ubication,
            "monthly_usage": monthly_usage, "min_stock": min_stock, "quantity": quantity,
        }
        if photo_file is not None:
            data["photo_path"] = save_uploaded_file(photo_file, IMAGES_DIR, sku or "product")
        if datasheet_file is not None:
            data["datasheet_path"] = save_uploaded_file(datasheet_file, DATASHEETS_DIR, sku or "product")

        if is_new:
            new_id = insert_product(data)
            if quantity:
                add_stock_entry_db(new_id, str(date.today()), quantity, price, "Initial creation")
        else:
            update_product(product_id, data)
        st.rerun()


# ----------------------------------------------------------------------------
# MAIN UI
# ----------------------------------------------------------------------------
st.title("📦 Material Inventory Management System")

with st.sidebar:
    st.success("Logged in")
    if st.button("🚪 Log out", width="stretch"):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    if st.button("➕ Add New Product", width="stretch", type="primary"):
        product_dialog(None)
    st.divider()
    search_val = st.text_input("🔍 Search", placeholder="Product, SKU, supplier...")
    sort_option = st.selectbox("Sort by", [
        "Default", "Low Stock First", "High Stock First", "Cost: Low to High",
        "Cost: High to Low", "Name A-Z", "Earliest Expiration",
    ])
    st.divider()
    export_df = get_all_products()
    if not export_df.empty:
        csv_bytes = export_df.drop(columns=["photo_path", "datasheet_path"], errors="ignore").to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export CSV", csv_bytes, file_name="material_inventory_export.csv", width="stretch")

df = get_all_products()

if search_val:
    s = search_val.lower()
    mask = df.apply(
        lambda r: s in str(r.get("product", "")).lower()
        or s in str(r.get("sku", "")).lower()
        or s in str(r.get("suppliers", "")).lower()
        or s in str(r.get("characteristics", "")).lower()
        or s in str(r.get("ubication", "")).lower(),
        axis=1,
    )
    df = df[mask]

if sort_option == "Low Stock First":
    df = df.assign(_gap=df["quantity"] - df["min_stock"]).sort_values("_gap")
elif sort_option == "High Stock First":
    df = df.sort_values("quantity", ascending=False)
elif sort_option == "Cost: Low to High":
    df = df.sort_values("price", ascending=True)
elif sort_option == "Cost: High to Low":
    df = df.sort_values("price", ascending=False)
elif sort_option == "Name A-Z":
    df = df.sort_values("product", ascending=True)
elif sort_option == "Earliest Expiration":
    df = df.sort_values("expiring_date", ascending=True)

tab_cards, tab_table = st.tabs(["🗂️ Cards", "📊 Table"])

with tab_cards:
    if df.empty:
        st.info("No products matched your search.")
    else:
        cols_per_row = 3
        for start in range(0, len(df), cols_per_row):
            chunk = df.iloc[start:start + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, (_, item) in zip(cols, chunk.iterrows()):
                with col:
                    with st.container(border=True):
                        photo_path = item.get("photo_path")
                        if photo_path and os.path.exists(os.path.join(BASE_DIR, photo_path)):
                            st.image(os.path.join(BASE_DIR, photo_path), width="stretch")
                        else:
                            st.markdown(
                                "<div style='height:120px;background:#1e293b;color:#94a3b8;"
                                "display:flex;align-items:center;justify-content:center;"
                                "border-radius:8px;font-size:12px;font-weight:700;'>NO PHOTO</div>",
                                unsafe_allow_html=True,
                            )
                        is_low = (item["quantity"] or 0) <= (item["min_stock"] or 0)
                        badge = "🚨 LOW STOCK" if is_low else "🟢 OK"
                        st.markdown(
                            f"**{item.get('icon') or '📦'} {item['product']}**  \n"
                            f"<span style='font-size:12px;color:#64748b'>{item['sku']}</span>  \n"
                            f"{badge}",
                            unsafe_allow_html=True,
                        )
                        st.caption((item.get("description") or "")[:120])
                        m1, m2 = st.columns(2)
                        m1.metric("Quantity", f"{item['quantity']:g}")
                        m2.metric("Landed Cost", f"€{calc_landed_cost(item['price'], item['discount'], item['transport_price']):.2f}")
                        st.caption(f"📍 {item.get('ubication') or '-'}   🏭 {item.get('suppliers') or '-'}")
                        if st.button("📄 Open / Edit", key=f"open_{item['id']}", width="stretch"):
                            product_dialog(int(item["id"]))

with tab_table:
    if df.empty:
        st.info("No products matched your search.")
    else:
        show_cols = ["sku", "icon", "product", "suppliers", "price", "discount", "transport_price",
                     "expiring_date", "delivery_time", "ubication", "monthly_usage", "min_stock", "quantity"]
        display_df = df[show_cols].copy()
        display_df["landed_cost"] = df.apply(
            lambda r: calc_landed_cost(r["price"], r["discount"], r["transport_price"]), axis=1
        )
        st.dataframe(display_df, width="stretch", hide_index=True)
        st.caption("Open a product from the Cards tab to edit its details or manage stock entries.")
