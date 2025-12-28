# pylint: skip-file
import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import plotly.express as px
import extra_streamlit_components as stx
import time
from io import BytesIO

# 1. ALGEMENE CONFIGURATIE
st.set_page_config(page_title="Project Portaal", layout="wide", page_icon="📈")

# --- 2. COOKIE MANAGER ---
cookie_manager = stx.CookieManager()

# --- 3. DATABASE & PROFESSIONELE EXPORT ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='Di@gnosis_supper_unfounded2', 
            database='implementatie_tracker',
            auth_plugin='mysql_native_password'
        )
    except Error:
        return None

def get_all_data():
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT * FROM project_status", conn)
        conn.close()
        return df
    return pd.DataFrame()

def to_excel_professional(df):
    """Maakt een professionele Excel-matrix: 1 rij per klant, fases als kolommen."""
    output = BytesIO()
    report_df = df.pivot(index='klantnaam', columns='fase', values='status')
    
    if 'score' in df.columns:
        avg_scores = df.groupby('klantnaam')['score'].mean().round(0).astype(int)
        report_df['Voortgang %'] = avg_scores
    
    # Chronologische volgorde voor Excel
    fase_volgorde = ["Inventarisatie", "Configuratie", "Acceptatietest (UAT)", "Training", "Go-Live", "Voortgang %"]
    existing_cols = [f for f in fase_volgorde if f in report_df.columns]
    report_df = report_df.reindex(columns=existing_cols)

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        report_df.to_excel(writer, sheet_name='Portfolio_Overzicht')
        workbook  = writer.book
        worksheet = writer.sheets['Portfolio_Overzicht']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#4F81BD', 'font_color': 'white', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})

        for col_num, value in enumerate(report_df.columns.values):
            worksheet.write(0, col_num + 1, value, header_fmt)
            width = 20 if value != "Voortgang %" else 15
            worksheet.set_column(col_num + 1, col_num + 1, width, cell_fmt)
        worksheet.set_column(0, 0, 30, cell_fmt)

    return output.getvalue()

def check_login(user, pw):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        query = "SELECT * FROM gebruikers WHERE gebruikersnaam = %s AND wachtwoord = %s"
        cursor.execute(query, (user, pw))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    return False

# --- 4. AUTHENTICATIE LOGICA (MET FIX VOOR KEYERROR) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'logout_in_progress' not in st.session_state:
    st.session_state.logout_in_progress = False

# Verbeterde Logout: voorkom KeyError 'auth_token'
if "logout" in st.query_params or st.session_state.logout_in_progress:
    st.session_state.authenticated = False
    st.session_state.logout_in_progress = False
    
    # Check eerst of de cookie bestaat voor we hem proberen te verwijderen
    all_cookies = cookie_manager.get_all()
    if all_cookies and "auth_token" in all_cookies:
        cookie_manager.delete("auth_token")
    
    st.query_params.clear()
    st.rerun()

# Cookie check bij refresh
if not st.session_state.authenticated:
    time.sleep(0.2) # Iets korter voor snellere respons
    token = cookie_manager.get(cookie="auth_token")
    if token:
        st.session_state.authenticated = True

# Inlogscherm
if not st.session_state.authenticated:
    st.title("🔐 Project Portaal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            st.subheader("Inloggen")
            u = st.text_input("Gebruikersnaam")
            p = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Login", use_container_width=True, type="primary"):
                if check_login(u, p):
                    st.session_state.authenticated = True
                    cookie_manager.set("auth_token", u, key="login_key")
                    st.rerun()
                else:
                    st.error("Onjuiste inloggegevens.")
    st.stop()

# --- 5. NAVIGATIE MENU ---
with st.sidebar:
    st.header("🧭 Navigatie")
    menu = st.radio("Ga naar:", ["📊 Dashboard", "⚙️ Projecten Updaten", "👤 Gebruikersbeheer"])
    st.divider()
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state.logout_in_progress = True
        st.rerun()

# --- 6. PAGINA: DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Project Portfolio Overzicht")
    data = get_all_data()
    
    if not data.empty:
        data['score'] = data['status'].map({"Voltooid": 100, "Bezig": 50, "Nog niet gestart": 0})
        
        if 'selected_project' not in st.session_state:
            st.session_state.selected_project = None

        if st.session_state.selected_project is None:
            k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
            k1.metric("Actieve Dossiers", data['klantnaam'].nunique())
            k2.metric("Gem. Voortgang", f"{int(data['score'].mean())}%")
            k3.metric("Status", "Beveiligd")
            with k4:
                st.write("") 
                st.download_button(
                    label="📥 Export Rapportage (Excel)",
                    data=to_excel_professional(data),
                    file_name='portfolio_rapportage.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True
                )

            st.divider()
            summary = data.groupby('klantnaam')['score'].mean().reset_index()
            cols = st.columns(3)
            for idx, row in summary.iterrows():
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"### {row['klantnaam']}")
                        st.progress(int(row['score']) / 100)
                        if st.button("Details", key=f"btn_{row['klantnaam']}", use_container_width=True):
                            st.session_state.selected_project = row['klantnaam']
                            st.rerun()
        else:
            sel = st.session_state.selected_project
            c_back, c_exp = st.columns([3, 1])
            with c_back:
                if st.button("⬅️ Terug naar Portfolio"):
                    st.session_state.selected_project = None
                    st.rerun()
            
            display_df = data[data['klantnaam'] == sel].copy()
            with c_exp:
                st.download_button(label=f"📥 Export {sel}", data=to_excel_professional(display_df), file_name=f'export_{sel}.xlsx', use_container_width=True)

            st.header(f"Project: {sel}")
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.plotly_chart(px.bar(display_df, x='fase', y='score', color='score', range_y=[0,105], text_auto=True, color_continuous_scale='RdYlGn'), use_container_width=True)
            with col_r:
                st.plotly_chart(px.pie(display_df, names='status', color_discrete_map={'Voltooid':'#28a745','Bezig':'#ffa500','Nog niet gestart':'#ff4b4b'}), use_container_width=True)
            
            st.subheader("📋 Status Matrix")
            matrix_df = display_df.pivot(index='klantnaam', columns='fase', values='status')
            
            # CHRONOLOGISCHE VOLGORDE MATRIX
            fase_volgorde = ["Inventarisatie", "Configuratie", "Acceptatietest (UAT)", "Training", "Go-Live"]
            matrix_cols = [f for f in fase_volgorde if f in matrix_df.columns]
            matrix_df = matrix_df.reindex(columns=matrix_cols)
            
            st.dataframe(matrix_df, use_container_width=True)
    else:
        st.info("Geen data gevonden.")

# --- 7. PAGINA: PROJECTEN UPDATEN ---
elif menu == "⚙️ Projecten Updaten":
    st.title("⚙️ Projectstatussen Bijwerken")
    data = get_all_data()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        project_opties = ["+ Nieuw Project"] + (sorted(data['klantnaam'].unique().tolist()) if not data.empty else [])
        sel_p = st.selectbox("Selecteer Project", project_opties)
        klant_naam = st.text_input("Projectnaam").strip().title() if sel_p == "+ Nieuw Project" else sel_p

    with col_b:
        fases = ["Inventarisatie", "Configuratie", "Acceptatietest (UAT)", "Training", "Go-Live"]
        nieuwe_status = {}
        for f in fases:
            d_idx = 0
            if not data.empty and klant_naam in data['klantnaam'].values:
                curr = data[(data['klantnaam'] == klant_naam) & (data['fase'] == f)]
                if not curr.empty:
                    try:
                        d_idx = ["Nog niet gestart", "Bezig", "Voltooid"].index(curr['status'].iloc[0])
                    except ValueError: d_idx = 0
            nieuwe_status[f] = st.selectbox(f, ["Nog niet gestart", "Bezig", "Voltooid"], index=d_idx, key=f"upd_{f}")

        if st.button("💾 Gegevens Opslaan", type="primary", use_container_width=True):
            if klant_naam:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    for f, s in nieuwe_status.items():
                        query = "INSERT INTO project_status (klantnaam, fase, status) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE status = VALUES(status)"
                        cursor.execute(query, (klant_naam, f, s))
                    conn.commit()
                    conn.close()
                    st.success("Opgeslagen!")
                    time.sleep(1)
                    st.rerun()

# --- 8. PAGINA: GEBRUIKERSBEHEER ---
elif menu == "👤 Gebruikersbeheer":
    st.title("👤 Gebruikersbeheer")
    with st.form("user_mgmt"):
        new_u = st.text_input("Nieuwe Gebruikersnaam")
        new_p = st.text_input("Nieuw Wachtwoord", type="password")
        if st.form_submit_button("Gebruiker Aanmaken", use_container_width=True):
            conn = get_db_connection()
            if conn and new_u and new_p:
                try:
                    cursor = conn.cursor()
                    query = "INSERT INTO gebruikers (gebruikersnaam, wachtwoord) VALUES (%s, %s)"
                    cursor.execute(query, (new_u, new_p))
                    conn.commit()
                    st.success(f"Gebruiker toegevoegd.")
                except Error:
                    st.error("Fout bij toevoegen.")
                finally:
                    conn.close()