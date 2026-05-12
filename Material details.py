import streamlit as st
import sqlite3
import pandas as pd
import io
from datetime import date

# Connect to database
conn = sqlite3.connect("civil_materials.db")
c = conn.cursor()

# Create tables
c.execute("""CREATE TABLE IF NOT EXISTS purchase_orders (
    po_number TEXT PRIMARY KEY,
    supplier TEXT,
    date TEXT)""")

c.execute("""CREATE TABLE IF NOT EXISTS po_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT,
    material TEXT,
    unit TEXT,
    quantity REAL)""")

c.execute("""CREATE TABLE IF NOT EXISTS materials_received (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT,
    material TEXT,
    quantity REAL,
    date TEXT)""")

c.execute("""CREATE TABLE IF NOT EXISTS materials_supplied (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT,
    contractor TEXT,
    material TEXT,
    quantity REAL,
    date TEXT)""")

conn.commit()

st.title("🏗️ Civil Materials Management")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Purchase Orders", "Materials Received", "Materials Supplied", "Inventory", "Export"]
)

# ---------------- TAB 1: Purchase Orders ----------------
with tab1:
    st.subheader("Add Purchase Order")
    po_number = st.text_input("PO Number", key="po_number")
    supplier = st.text_input("Supplier", key="supplier")
    po_date = st.date_input("PO Date", date.today(), key="po_date")
    if st.button("Save PO", key="save_po"):
        try:
            c.execute("INSERT INTO purchase_orders VALUES (?,?,?)", (po_number, supplier, str(po_date)))
            conn.commit()
            st.success("Purchase Order saved!")
        except sqlite3.IntegrityError:
            st.error("PO Number already exists!")

    st.subheader("Add Materials to PO")
    po_for_material = st.text_input("PO Number (existing)", key="po_mat")
    mat_name = st.text_input("Material Name", key="mat_name")
    mat_unit = st.text_input("Unit (e.g. bags, tons)", key="mat_unit")
    mat_qty = st.number_input("Quantity as per PO", min_value=0.0, key="mat_qty")
    if st.button("Save Material", key="save_material"):
        c.execute("INSERT INTO po_materials (po_number, material, unit, quantity) VALUES (?,?,?,?)",
                  (po_for_material, mat_name, mat_unit, mat_qty))
        conn.commit()
        st.success("Material added to PO!")

# ---------------- TAB 2: Materials Received ----------------
with tab2:
    st.subheader("Record Materials Received")
    po_list = [row[0] for row in c.execute("SELECT po_number FROM purchase_orders").fetchall()]
    po_select = st.selectbox("Select PO Number", po_list, key="received_po")

    if po_select:
        po_materials = c.execute("SELECT material, unit, quantity FROM po_materials WHERE po_number=?", (po_select,)).fetchall()
        rec_summary = c.execute("SELECT material, SUM(quantity) FROM materials_received WHERE po_number=? GROUP BY material", (po_select,)).fetchall()

        rows = []
        for i, (mat, unit, po_qty) in enumerate(po_materials, start=1):
            already_rec = next((r[1] for r in rec_summary if r[0] == mat), 0)
            balance = po_qty - already_rec
            rows.append({
                "Sl.No": i,
                "Material": mat,
                "Unit": unit,
                "PO Qty": po_qty,
                "Already Received": already_rec,
                "New Received Qty": 0.0,
                "Received Date": str(date.today()),
                "Balance Qty": balance
            })

        df = pd.DataFrame(rows)
        edited_df = st.data_editor(
            df,
            num_rows="fixed",
            key="received_editor",
            disabled=["Sl.No", "Material", "Unit", "PO Qty", "Already Received", "Balance Qty"]
        )

        if st.button("Save All Received Entries", key="save_received"):
            for _, row in edited_df.iterrows():
                new_qty = row["New Received Qty"]
                rec_date = row["Received Date"]
                if new_qty < 0:
                    st.error(f"{row['Material']}: Negative qty not allowed")
                elif new_qty > row["Balance Qty"]:
                    st.error(f"{row['Material']}: Cannot exceed PO balance")
                elif new_qty > 0:
                    c.execute("INSERT INTO materials_received (po_number, material, quantity, date) VALUES (?,?,?,?)",
                              (po_select, row["Material"], new_qty, rec_date))
            conn.commit()
            st.success("All received entries saved!")

# ---------------- TAB 3: Materials Supplied ----------------
with tab3:
    st.subheader("Record Materials Supplied")
    po_select_sup = st.selectbox("Select PO Number", po_list, key="sup_po")

    if po_select_sup:
        po_materials = c.execute("SELECT material, unit, quantity FROM po_materials WHERE po_number=?", (po_select_sup,)).fetchall()
        rec_summary = c.execute("SELECT material, SUM(quantity) FROM materials_received WHERE po_number=? GROUP BY material", (po_select_sup,)).fetchall()
        sup_summary = c.execute("SELECT material, SUM(quantity) FROM materials_supplied WHERE po_number=? GROUP BY material", (po_select_sup,)).fetchall()

        rows = []
        for i, (mat, unit, po_qty) in enumerate(po_materials, start=1):
            rec_qty = next((r[1] for r in rec_summary if r[0] == mat), 0)
            sup_qty = next((s[1] for s in sup_summary if s[0] == mat), 0)
            stock = rec_qty - sup_qty
            rows.append({
                "Sl.No": i,
                "Material": mat,
                "Unit": unit,
                "PO Qty": po_qty,
                "Received Qty": rec_qty,
                "Already Supplied": sup_qty,
                "New Supply Qty": 0.0,
                "Supply Date": str(date.today()),
                "Contractor": "",
                "Stock Qty": stock
            })

        df = pd.DataFrame(rows)
        edited_df = st.data_editor(
            df,
            num_rows="fixed",
            key="supplied_editor",
            disabled=["Sl.No", "Material", "Unit", "PO Qty", "Received Qty", "Already Supplied", "Stock Qty"]
        )

        if st.button("Save All Supplied Entries", key="save_supplied"):
            for _, row in edited_df.iterrows():
                new_qty = row["New Supply Qty"]
                sup_date = row["Supply Date"]
                contractor = row["Contractor"]
                if new_qty < 0:
                    st.error(f"{row['Material']}: Negative qty not allowed")
                elif new_qty > row["Stock Qty"]:
                    st.error(f"{row['Material']}: Cannot exceed stock")
                elif new_qty > 0 and contractor.strip() != "":
                    c.execute("INSERT INTO materials_supplied (po_number, contractor, material, quantity, date) VALUES (?,?,?,?,?)",
                              (po_select_sup, contractor, row["Material"], new_qty, sup_date))
            conn.commit()
            st.success("All supplied entries saved!")

# ---------------- TAB 4: Inventory ----------------
with tab4:
    st.subheader("📦 Inventory per PO")
    po_inv = st.selectbox("Select PO Number", po_list, key="inv_po")

    if po_inv:
        po_materials = c.execute("SELECT material, unit, quantity FROM po_materials WHERE po_number=?", (po_inv,)).fetchall()
        rec_summary = c.execute("SELECT material, SUM(quantity) FROM materials_received WHERE po_number=? GROUP BY material", (po_inv,)).fetchall()
        sup_summary = c.execute("SELECT material, SUM(quantity) FROM materials_supplied WHERE po_number=? GROUP BY material", (po_inv,)).fetchall()

        rows = []
        for i, (mat, unit, po_qty) in enumerate(po_materials, start=1):
            rec_qty = next((r[1] for r in rec_summary if r[0] == mat), 0)
            sup_qty = next((s[1] for s in sup_summary if s[0] == mat), 0)
            stock = rec_qty - sup_qty
            rows.append({
                "Sl.No": i,
                "Material": mat,
                "Unit": unit,
                "PO Qty": po_qty,
                "Received Qty": rec_qty,
                "Supplied Qty": sup_qty,
                "Stock Qty": stock
            })

        df_inv = pd.DataFrame(rows)
        st.dataframe(df_inv, use_container_width=True, key="inventory_editor")

# ---------------- TAB 5: Export ----------------
with tab5:
    st.subheader("📤 Export Data")
    po_export = st.selectbox("Select PO Number", po_list, key="exp_po")

    if po_export:
        df_po = pd.read_sql_query("SELECT * FROM purchase_orders WHERE po_number=?", conn, params=(po_export,))
        df_po_mat = pd.read_sql_query("SELECT * FROM po_materials WHERE po_number=?", conn, params=(po_export,))
