import os
import sqlite3
import tempfile
from datetime import datetime
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# APP CONFIG & SAFE DIRECTORY SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Material Inventory System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = tempfile.gettempdir()
DB_FILE = os.path.join(BASE_DIR, "inventory_v4.db")
IMAGES_DIR = os.path.join(BASE_DIR, "inventory_images")
DATASHEETS_DIR = os.path.join(BASE_DIR, "inventory_datasheets")

for directory in [IMAGES_DIR, DATASHEETS_DIR]:
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# DATABASE INITIALIZATION & HELPERS
# -----------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Table 1: Products
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icon TEXT DEFAULT '📦',
                sku TEXT UNIQUE NOT NULL,
                product TEXT NOT NULL,
                characteristics TEXT,
                suppliers TEXT,
                price REAL DEFAULT 0.0,
                discount REAL DEFAULT 0.0,
                transport_price REAL DEFAULT 0.0,
                expiring_date TEXT,
                delivery_time INTEGER DEFAULT 5,
                ubication TEXT,
                monthly_usage INTEGER DEFAULT 0,
                min_stock INTEGER DEFAULT 0,
                quantity REAL DEFAULT 0.0,
                description TEXT,
                where_used TEXT,
                source_origin TEXT,
                batch_lot TEXT,
                sds_hazard_class TEXT,
                photo_path TEXT,
                datasheet_path TEXT
            )
        """)

        # Table 2: Multiple Entries / Stock History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                note TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Seed Default Materials if DB is empty
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            seed_data = [
                (
                    "🏷️",
                    "MAT-VEL-401",
                    "Velcro 401 Black",
                    "1 Box = 14 U | Breakdown: 1 Box x 350 mts + 8 U x 25 mts",
                    "Velcro Industrial",
                    120.00,
                    5.0,
                    10.00,
                    "2030-12-31",
                    5,
                    "Zone A - Rack 01",
                    200,
                    250,
                    550.0,
                    "1 Box x 350 mts (350m) + 8 U x 25 mts (200m). Total: 550 mts.",
                    "Fijación textil vertical/horizontal y paneles modulares.",
                    "Barcelona, España",
                    "LOT-VEL401-26",
                    "No peligroso",
                ),
                (
                    "🏷️",
                    "MAT-VEL-758",
                    "Velcro 758 Black",
                    "1 Box = 11 U | Breakdown: 20 Box x 495 mts + 7 U x 45 mts",
                    "Velcro Industrial",
                    180.00,
                    8.0,
                    15.00,
                    "2030-12-31",
                    5,
                    "Zone A - Rack 02",
                    1500,
                    2000,
                    10215.0,
                    "20 Box x 495 mts (9,900m) + 7 U x 45 mts (315m). Total: 10,215 mts.",
                    "Cierre de cubiertas de gran envergadura y cortinas aislantes.",
                    "Barcelona, España",
                    "LOT-VEL758-26",
                    "No peligroso",
                ),
                (
                    "🧪",
                    "MAT-GLU-TUN400",
                    "Glue Tunsan 400 ml",
                    "1 Box = 28 U | Breakdown: 23 Box x 28 U + 10 U loose",
                    "Tunsan Chemical Supplies",
                    8.50,
                    5.0,
                    0.80,
                    "2027-06-30",
                    4,
                    "Zone B - Shelf 01",
                    150,
                    100,
                    654.0,
                    "23 Box x 28 U (644 U) + 10 U sueltas. Total: 654 U.",
                    "Sellado rápido de carcasas y adhesión ligera.",
                    "Valencia, España",
                    "LOT-TUN-400-A",
                    "Clase 3 Inflamable",
                ),
                (
                    "🧪",
                    "MAT-GLU-HUI600",
                    "Glue HUITIAN 600 ml",
                    "1 Box = 20 U | Total Stock: 15 U loose",
                    "Huitian Adhesives",
                    12.00,
                    0.0,
                    1.20,
                    "2027-04-15",
                    7,
                    "Zone B - Shelf 02",
                    30,
                    20,
                    15.0,
                    "15 U sueltas. Total: 15 U.",
                    "Sellado elástico e industrial de mamparas.",
                    "Hubei, China",
                    "LOT-HUI-600X",
                    "Irritante",
                ),
                (
                    "🧪",
                    "MAT-GLU-DOW600",
                    "Glue DOW 600 ml",
                    "1 Box = 20 U | Total Stock: 13 U loose",
                    "Dow Chemical Europe",
                    16.50,
                    10.0,
                    1.50,
                    "2027-09-30",
                    3,
                    "Zone B - Shelf 03",
                    40,
                    25,
                    13.0,
                    "13 U sueltas. Total: 13 U.",
                    "Sellado de cristales y juntas estructurales.",
                    "Wiesbaden, Alemania",
                    "LOT-DOW-600D",
                    "Bajo VOC",
                ),
                (
                    "🧪",
                    "MAT-GLU-SEA600",
                    "Glue SEAL 600 ml",
                    "1 Box = 12 U | Breakdown: 3 Box x 12 U",
                    "Seal Industrial Solutions",
                    11.00,
                    0.0,
                    1.00,
                    "2027-08-10",
                    5,
                    "Zone B - Shelf 04",
                    25,
                    15,
                    36.0,
                    "3 Box x 12 U. Total: 36 U.",
                    "Sellado impermeable de marcos y molduras.",
                    "Milán, Italia",
                    "LOT-SEA-36X",
                    "No peligroso",
                ),
                (
                    "⚡",
                    "MAT-PV-TRAD",
                    "PV TRADICIONAL",
                    "Módulo Fotovoltaico Estándar | Total Stock: 23 U",
                    "PV Solar Tech",
                    140.00,
                    12.0,
                    12.00,
                    "2035-12-31",
                    10,
                    "Zone C - Rack PV1",
                    15,
                    10,
                    23.0,
                    "23 U. Total: 23 U.",
                    "Instalación en cubiertas solares tradicionales.",
                    "Madrid, España",
                    "LOT-PV-TRAD-01",
                    "Eléctrico",
                ),
                (
                    "⚡",
                    "MAT-PV-560W",
                    "PV 560W",
                    "Panel Fotovoltaico Alta Eficiencia 560W | Total Stock: 5 U",
                    "PV Solar Tech",
                    210.00,
                    15.0,
                    18.00,
                    "2035-12-31",
                    10,
                    "Zone C - Rack PV2",
                    8,
                    10,
                    5.0,
                    "5 U. Total: 5 U.",
                    "Generación de energía solar de alta densidad.",
                    "Jiangsu, China",
                    "LOT-PV-560W-26",
                    "Eléctrico",
                ),
                (
                    "📦",
                    "MAT-PV-WGV",
                    "PV White Glue Velcro Vertical",
                    "Panel PV Blanco con Velcro Vertical Integrado | Total Stock: 127 U",
                    "Custom Solar Flex",
                    165.00,
                    10.0,
                    14.00,
                    "2032-12-31",
                    7,
                    "Zone C - Rack PV3",
                    50,
                    30,
                    127.0,
                    "127 U. Total: 127 U.",
                    "Montaje rápido fotovoltaico en posición vertical sobre lona.",
                    "Oporto, Portugal",
                    "LOT-PV-WGV-127",
                    "No peligroso",
                ),
                (
                    "📦",
                    "MAT-PV-WGH",
                    "PV White Glue Velcro Horizontal",
                    "Panel PV Blanco con Velcro Horizontal Integrado | Total Stock: 2 U",
                    "Custom Solar Flex",
                    165.00,
                    10.0,
                    14.00,
                    "2032-12-31",
                    7,
                    "Zone C - Rack PV3",
                    20,
                    15,
                    2.0,
                    "2 U. Total: 2 U.",
                    "Montaje rápido fotovoltaico en posición horizontal.",
                    "Oporto, Portugal",
                    "LOT-PV-WGH-02",
                    "No peligroso",
                ),
                (
                    "📦",
                    "MAT-PV-WHITE",
                    "PV White",
                    "Módulo PV Flex Blanco Estándar | Total Stock: 110 U",
                    "Custom Solar Flex",
                    150.00,
                    8.0,
                    12.00,
                    "2032-12-31",
                    6,
                    "Zone C - Rack PV4",
                    40,
                    25,
                    110.0,
                    "110 U. Total: 110 U.",
                    "Integración arquitectónica fotovoltaica blanca.",
                    "Oporto, Portugal",
                    "LOT-PV-W-110",
                    "No peligroso",
                ),
                (
                    "📦",
                    "MAT-PV-BLACK",
                    "PV Black",
                    "Módulo PV Flex Negro Full Black | Total Stock: 32 U",
                    "Custom Solar Flex",
                    155.00,
                    8.0,
                    12.00,
                    "2032-12-31",
                    6,
                    "Zone C - Rack PV4",
                    30,
                    20,
                    32.0,
                    "32 U. Total: 32 U.",
                    "Instalaciones estéticas Full Black sobre superficie oscura.",
                    "Oporto, Portugal",
                    "LOT-PV-B-32",
                    "No peligroso",
                ),
            ]

            for item in seed_data:
                cursor.execute(
                    """
                    INSERT INTO products (
                        icon, sku, product, characteristics, suppliers, price, discount, transport_price,
                        expiring_date, delivery_time, ubication, monthly_usage, min_stock, quantity,
                        description, where_used, source_origin, batch_lot, sds_hazard_class
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    item,
                )

                prod_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO stock_entries (product_id, entry_date, quantity, price, note)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        prod_id,
                        datetime.now().strftime("%Y-%m-%d"),
                        item[13],
                        item[5],
                        "Initial Batch",
                    ),
                )

        conn.commit()


init_db()


def calc_landed_cost(price, discount, transport):
    price = price or 0.0
    discount = discount or 0.0
    transport = transport or 0.0
    return round((price * (1 - discount / 100.0)) + transport, 2)


# -----------------------------------------------------------------------------
# TOP HEADER & TOP-RIGHT EMOJI LANGUAGE SWITCHER
# -----------------------------------------------------------------------------
if "current_lang" not in st.session_state:
    st.session_state["current_lang"] = "es"

col_header, col_lang = st.columns([5, 1])

with col_lang:
    lang_btn_text = (
        "🇬🇧 English"
        if st.session_state["current_lang"] == "es"
        else "🇪🇸 Español"
    )
    if st.button(lang_btn_text, key="top_lang_switcher", type="secondary"):
        st.session_state["current_lang"] = (
            "en" if st.session_state["current_lang"] == "es" else "es"
        )
        st.rerun()

es = st.session_state["current_lang"] == "es"

txt = {
    "title": (
        "📦 INVENTARIO DE MATERIALES" if es else "📦 MATERIAL INVENTORY SYSTEM"
    ),
    "search_lbl": "🔍 Búsqueda Universal" if es else "🔍 Universal Search",
    "search_ph": (
        "Buscar por Velcro, Tunsan, Dow, PV, Zona A..."
        if es
        else "Search by Velcro, Tunsan, Dow, PV, Zone A..."
    ),
    "sort_lbl": "Orden / Ranking" if es else "Sort / Ranking",
    "tab1": "🎴 Tarjetas / Vista Modal" if es else "🎴 Cards / Modal View",
    "tab2": "📊 Tabla Master Excel" if es else "📊 Master Excel Table",
    "add_btn": "➕ Añadir Nuevo Producto" if es else "➕ Add New Product",
    "save_btn": "💾 Guardar Cambios" if es else "💾 Save Changes",
    "delete_btn": "🗑️ Eliminar Producto" if es else "🗑️ Delete Product",
    "landed": "Coste Final Net" if es else "Landed Cost",
    "low_stock": "🚨 STOCK BAJO" if es else "🚨 LOW STOCK",
    "ok_stock": "🟢 STOCK OK" if es else "🟢 STOCK OK",
    "entries_sec": (
        "📅 Historial de Entradas (Múltiples Registros)"
        if es
        else "📅 Stock Entry History (Multiple Records)"
    ),
}

with col_header:
    st.title(txt["title"])


# -----------------------------------------------------------------------------
# DATA LOAD & FILTERING
# -----------------------------------------------------------------------------
def load_products():
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM products", conn)

    df["landed_cost"] = df.apply(
        lambda r: calc_landed_cost(r["price"], r["discount"], r["transport_price"]),
        axis=1,
    )
    return df


df_products = load_products()

col_search, col_sort = st.columns([3, 1])

with col_search:
    search_query = st.text_input(
        txt["search_lbl"], placeholder=txt["search_ph"]
    ).lower()

with col_sort:
    sort_option = st.selectbox(
        txt["sort_lbl"],
        options=[
            "Default",
            "Low Stock First",
            "High Stock First",
            "Landed Cost: Low to High",
            "Landed Cost: High to Low",
            "Name: A-Z",
        ],
    )

filtered_df = df_products.copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df.apply(
            lambda row: search_query in row.astype(str).str.lower().str.cat(sep=" "),
            axis=1,
        )
    ]

if sort_option == "Low Stock First":
    filtered_df["stock_diff"] = filtered_df["quantity"] - filtered_df["min_stock"]
    filtered_df = filtered_df.sort_values("stock_diff", ascending=True)
elif sort_option == "High Stock First":
    filtered_df = filtered_df.sort_values("quantity", ascending=False)
elif sort_option == "Landed Cost: Low to High":
    filtered_df = filtered_df.sort_values("landed_cost", ascending=True)
elif sort_option == "Landed Cost: High to Low":
    filtered_df = filtered_df.sort_values("landed_cost", ascending=False)
elif sort_option == "Name: A-Z":
    filtered_df = filtered_df.sort_values("product", ascending=True)

# -----------------------------------------------------------------------------
# MAIN APP TABS
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs([txt["tab1"], txt["tab2"]])

with tab1:
    if st.button(txt["add_btn"], type="primary"):
        with get_db_connection() as conn:
            cur = conn.cursor()
            new_sku = f"MAT-NEW-{int(datetime.now().timestamp())}"
            cur.execute(
                """
                INSERT INTO products (sku, product, quantity, min_stock, price)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    new_sku,
                    "Nuevo Material" if es else "New Material",
                    10.0,
                    5.0,
                    10.00,
                ),
            )
            conn.commit()
        st.rerun()

    st.write("---")

    cols = st.columns(3)
    for idx, row in filtered_df.reset_index().iterrows():
        col = cols[idx % 3]
        with col:
            is_low = row["quantity"] <= row["min_stock"]
            badge = txt["low_stock"] if is_low else txt["ok_stock"]

            with st.container(border=True):
                if row["photo_path"] and os.path.exists(row["photo_path"]):
                    st.image(row["photo_path"], use_container_width=True)
                else:
                    st.markdown(
                        f"<div style='height:120px; background:#1e293b; color:#94a3b8; display:flex; align-items:center; justify-content:center; border-radius:8px; font-weight:bold; font-size:24px;'>{row['icon']} {row['product'][:15]}</div>",
                        unsafe_allow_html=True,
                    )

                st.subheader(f"{row['icon']} {row['product']}")
                st.caption(f"SKU: {row['sku']} | {badge}")

                st.write(
                    f"📍 **{'Ubicación' if es else 'Location'}:** {row['ubication']}"
                )
                st.write(
                    f"📦 **{'Cantidad Total' if es else 'Total Qty'}:** `{row['quantity']}`"
                )
                st.write(f"💶 **{txt['landed']}:** `€{row['landed_cost']}`")

                if st.button(
                    f"📄 {'Ficha & Entradas' if es else 'Details & History'}",
                    key=f"card_btn_{row['id']}",
                ):
                    st.session_state["selected_product_id"] = row["id"]

# -----------------------------------------------------------------------------
# DETAILED PRODUCT MODAL WITH INDIVIDUAL ENTRY DELETION
# -----------------------------------------------------------------------------
if "selected_product_id" in st.session_state:
    p_id = st.session_state["selected_product_id"]

    with get_db_connection() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE id = ?", (p_id,)
        ).fetchone()

    if product:

        @st.dialog(
            f"{product['icon']} {product['product']}",
            width="large",
        )
        def product_modal():
            st.caption(
                f"SKU: {product['sku']} | Ubicación: {product['ubication']}"
            )

            st.markdown("### 🖼️ Photo & Technical Datasheet")
            col_img, col_pdf = st.columns(2)

            with col_img:
                if product["photo_path"] and os.path.exists(
                    product["photo_path"]
                ):
                    st.image(
                        product["photo_path"],
                        caption="Product Photo",
                        use_container_width=True,
                    )

                uploaded_img = st.file_uploader(
                    "Upload Photo (PNG/JPG)", type=["png", "jpg", "jpeg"]
                )
                if uploaded_img:
                    img_path = os.path.join(IMAGES_DIR, f"prod_{p_id}.png")
                    with open(img_path, "wb") as f:
                        f.write(uploaded_img.getbuffer())
                    with get_db_connection() as conn:
                        conn.execute(
                            "UPDATE products SET photo_path = ? WHERE id = ?",
                            (img_path, p_id),
                        )
                        conn.commit()
                    st.success("Photo updated!")
                    st.rerun()

            with col_pdf:
                if product["datasheet_path"] and os.path.exists(
                    product["datasheet_path"]
                ):
                    st.success("🟢 Technical Datasheet Attached")
                    with open(product["datasheet_path"], "rb") as pdf_file:
                        st.download_button(
                            "📥 Download Datasheet PDF",
                            pdf_file,
                            file_name=f"{product['sku']}_datasheet.pdf",
                        )

                uploaded_pdf = st.file_uploader(
                    "Upload Datasheet (PDF)", type=["pdf"]
                )
                if uploaded_pdf:
                    pdf_path = os.path.join(DATASHEETS_DIR, f"pdf_{p_id}.pdf")
                    with open(pdf_path, "wb") as f:
                        f.write(uploaded_pdf.getbuffer())
                    with get_db_connection() as conn:
                        conn.execute(
                            "UPDATE products SET datasheet_path = ? WHERE id = ?",
                            (pdf_path, p_id),
                        )
                        conn.commit()
                    st.success("Datasheet saved!")
                    st.rerun()

            st.write("---")

            # --- MULTIPLE STOCK ENTRIES HISTORY WITH INDIVIDUAL DELETION ---
            st.markdown(f"### {txt['entries_sec']}")

            with get_db_connection() as conn:
                entries = conn.execute(
                    "SELECT * FROM stock_entries WHERE product_id = ? ORDER BY entry_date DESC",
                    (p_id,),
                ).fetchall()

            if entries:
                for entry in entries:
                    e_col1, e_col2, e_col3, e_col4, e_col5 = st.columns(
                        [2, 2, 2, 3, 1]
                    )
                    e_col1.write(f"📅 {entry['entry_date']}")
                    e_col2.write(f"📦 `{entry['quantity']}`")
                    e_col3.write(f"💶 `€{entry['price']:.2f}`")
                    e_col4.caption(f"{entry['note'] or '-'}")

                    # Inline Delete Button for each entry
                    if e_col5.button("🗑️", key=f"del_entry_{entry['id']}"):
                        with get_db_connection() as conn:
                            conn.execute(
                                "DELETE FROM stock_entries WHERE id = ?",
                                (entry["id"],),
                            )
                            # Re-fetch latest remaining entry to auto-adjust total quantity
                            rem_entries = conn.execute(
                                "SELECT * FROM stock_entries WHERE product_id = ? ORDER BY entry_date DESC",
                                (p_id,),
                            ).fetchall()
                            if rem_entries:
                                latest = rem_entries[0]
                                conn.execute(
                                    "UPDATE products SET quantity = ?, price = ? WHERE id = ?",
                                    (latest["quantity"], latest["price"], p_id),
                                )
                            conn.commit()
                        st.success("Entry removed!")
                        st.rerun()

            # Form to register new stock entry
            with st.expander("➕ Register New Entry (Añadir Entrada)"):
                with st.form(key=f"add_entry_form_{p_id}"):
                    c1, c2, c3 = st.columns(3)
                    e_date = c1.date_input("Date", value=datetime.now())
                    e_qty = c2.number_input(
                        "Quantity", value=float(product["quantity"])
                    )
                    e_price = c3.number_input(
                        "Price (€)", value=float(product["price"])
                    )
                    e_note = st.text_input("Note / Comment", value="Restock")

                    if st.form_submit_button("Add Entry"):
                        with get_db_connection() as conn:
                            conn.execute(
                                """
                                INSERT INTO stock_entries (product_id, entry_date, quantity, price, note)
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                (
                                    p_id,
                                    e_date.strftime("%Y-%m-%d"),
                                    e_qty,
                                    e_price,
                                    e_note,
                                ),
                            )

                            conn.execute(
                                """
                                UPDATE products SET quantity = ?, price = ? WHERE id = ?
                            """,
                                (e_qty, e_price, p_id),
                            )
                            conn.commit()
                        st.success("Entry added!")
                        st.rerun()

            st.write("---")

            st.markdown("### 📘 Master Details & Pricing")
            with st.form(key=f"edit_prod_form_{p_id}"):
                col_a, col_b = st.columns(2)
                f_name = col_a.text_input("Product Name", value=product["product"])
                f_icon = col_b.text_input("Icon (Emoji)", value=product["icon"])

                f_desc = st.text_area(
                    "Description / Breakdown", value=product["description"]
                )
                f_char = st.text_area(
                    "Characteristics / Packaging",
                    value=product["characteristics"],
                )
                f_where = st.text_area(
                    "Where Used (Process)", value=product["where_used"]
                )

                c1, c2, c3 = st.columns(3)
                f_price = c1.number_input(
                    "Base Price (€)", value=float(product["price"])
                )
                f_disc = c2.number_input(
                    "Discount (%)", value=float(product["discount"])
                )
                f_trans = c3.number_input(
                    "Transport Fee (€)", value=float(product["transport_price"])
                )

                c4, c5, c6 = st.columns(3)
                f_qty = c4.number_input(
                    "Total Quantity", value=float(product["quantity"])
                )
                f_min = c5.number_input(
                    "Min Stock Level", value=int(product["min_stock"])
                )
                f_ubic = c6.text_input("Ubication", value=product["ubication"])

                btn_save = st.form_submit_button(
                    txt["save_btn"], type="primary"
                )

                if btn_save:
                    with get_db_connection() as conn:
                        conn.execute(
                            """
                            UPDATE products SET 
                                product = ?, icon = ?, description = ?, characteristics = ?,
                                where_used = ?, price = ?, discount = ?, transport_price = ?,
                                quantity = ?, min_stock = ?, ubication = ?
                            WHERE id = ?
                        """,
                            (
                                f_name,
                                f_icon,
                                f_desc,
                                f_char,
                                f_where,
                                f_price,
                                f_disc,
                                f_trans,
                                f_qty,
                                f_min,
                                f_ubic,
                                p_id,
                            ),
                        )
                        conn.commit()
                    st.success("Saved successfully!")
                    st.rerun()

            if st.button(txt["delete_btn"], type="secondary"):
                with get_db_connection() as conn:
                    conn.execute("DELETE FROM products WHERE id = ?", (p_id,))
                    conn.commit()
                del st.session_state["selected_product_id"]
                st.rerun()

        product_modal()

# -----------------------------------------------------------------------------
# TAB 2: EDITABLE SPREADSHEET MASTER TABLE
# -----------------------------------------------------------------------------
with tab2:
    st.markdown("### 📊 Master Editable Grid")

    edited_df = st.data_editor(
        filtered_df[
            [
                "id",
                "icon",
                "sku",
                "product",
                "characteristics",
                "suppliers",
                "price",
                "discount",
                "transport_price",
                "landed_cost",
                "quantity",
                "min_stock",
                "ubication",
            ]
        ],
        disabled=["id", "sku", "landed_cost"],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("💾 Apply Grid Edits to Database"):
        with get_db_connection() as conn:
            for idx, r in edited_df.iterrows():
                conn.execute(
                    """
                    UPDATE products SET
                        icon = ?, product = ?, characteristics = ?, suppliers = ?,
                        price = ?, discount = ?, transport_price = ?,
                        quantity = ?, min_stock = ?, ubication = ?
                    WHERE id = ?
                """,
                    (
                        r["icon"],
                        r["product"],
                        r["characteristics"],
                        r["suppliers"],
                        r["price"],
                        r["discount"],
                        r["transport_price"],
                        r["quantity"],
                        r["min_stock"],
                        r["ubication"],
                        r["id"],
                    ),
                )
            conn.commit()
        st.success("Database updated!")
        st.rerun()
