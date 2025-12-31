# pylint: skip-file
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import extra_streamlit_components as stx
import time
import datetime   # <-- deze erbij
from io import BytesIO

# ========= DATABASE CONFIG MET CACHING =========
@st.cache_resource
def get_engine():
    # We halen de URL uit de secrets
    url = st.secrets["DB_URL"]
    # We maken de engine één keer aan en hergebruiken deze
    return create_engine(url, pool_pre_ping=True)

# Roep de functie aan om de engine beschikbaar te maken voor de rest van de app
engine = get_engine()

@st.cache_data(ttl=600)  # Onthoudt de data voor 10 minuten
def get_data_from_db(query):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn)



# Test connectie
try:
    pd.read_sql("SELECT 1", engine)
    st.success("✅ Database connectie OK")
except Exception as e:
    st.error(f"❌ Database fout: {e}")
    st.stop()

# ========= APP CONFIG =========
st.set_page_config(page_title="Project Portaal", layout="wide", page_icon="📈")
cookie_manager = stx.CookieManager()

# ========= HULPFUNCTIES =========
def get_all_data():
    """Haalt alle projecten op uit de database."""
    try:
        df = get_data_from_db("SELECT * FROM projecten")
        return df
    except Exception as e:
        st.error(f"Fout bij ophalen data: {e}")
        return pd.DataFrame()

def check_login(username, password):
    """Eenvoudige login check."""
    try:
        query = text('SELECT * FROM gebruikers WHERE username = :u AND password = :p')
        with engine.connect() as conn:
            result = conn.execute(query, {"u": username, "p": password}).fetchone()
            return result is not None
    except Exception as e:
        st.error(f"Login fout: {e}")
        return False

def to_excel_professional(df):
    """Export naar professionele Excel."""
    output = BytesIO()
    report_df = df.pivot(index='naam', columns='fase', values='status')

    if 'score' in df.columns:
        avg_scores = df.groupby('naam')['score'].mean().round(0).astype(int)
        report_df['Voortgang %'] = avg_scores

    fase_volgorde = [
        "Inventarisatie", "Configuratie", "Acceptatietest (UAT)",
        "Training", "Go-Live", "Voortgang %"
    ]
    existing_cols = [f for f in fase_volgorde if f in report_df.columns]
    report_df = report_df.reindex(columns=existing_cols)

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        report_df.to_excel(writer, sheet_name='Portfolio_Overzicht')
        workbook = writer.book
        worksheet = writer.sheets['Portfolio_Overzicht']

        header_fmt = workbook.add_format(
            {'bold': True, 'bg_color': '#4F81BD',
             'font_color': 'white', 'border': 1}
        )
        cell_fmt = workbook.add_format({'border': 1})

        for col_num, value in enumerate(report_df.columns.values):
            worksheet.write(0, col_num + 1, value, header_fmt)
            width = 20 if value != "Voortgang %" else 15
            worksheet.set_column(col_num + 1, col_num + 1, width, cell_fmt)
        worksheet.set_column(0, 0, 30, cell_fmt)

    return output.getvalue()

# ========= SESSION STATE =========
if 'permanent_login' not in st.session_state:
    st.session_state.permanent_login = False
    st.session_state.username = None
if 'selected_project' not in st.session_state:
    st.session_state.selected_project = None

# Permanente login vanuit cookie
try:
    auth_token = cookie_manager.get(cookie="auth_token")
    if auth_token:
        st.session_state.permanent_login = True
        st.session_state.username = auth_token
except Exception:
    pass

# Logout via query param
if st.query_params.get("logout"):
    st.session_state.permanent_login = False
    st.session_state.username = None
    try:
        cookie_manager.delete("auth_token")
    except Exception:
        pass
    st.query_params.clear()
    st.rerun()

# ========= LOGIN SCHERM =========
if not st.session_state.permanent_login:
    st.title("🔐 Project Portaal - Inloggen")

    col1, col2 = st.columns([1, 3])
    with col2:
        with st.form("login"):
            username = st.text_input("👤 Gebruikersnaam", placeholder="admin")
            password = st.text_input("🔑 Wachtwoord", type="password", placeholder="admin")
            if st.form_submit_button("🚀 Inloggen", type="primary"):
                if check_login(username, password):
                    st.session_state.permanent_login = True
                    st.session_state.username = username
                    expires_at = datetime.datetime.now() + datetime.timedelta(days=7)
                    cookie_manager.set("auth_token", username, expires_at=expires_at)
                    st.success(f"✅ Welkom {username}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Verkeerde gebruikersnaam of wachtwoord! (admin/admin)")
    st.stop()

# ========= GEAUTHENTICEERDE APP =========
st.sidebar.title(f"👋 {st.session_state.username}")
menu = st.sidebar.radio(
    "Navigeer:",
    ["📊 Dashboard", "➕ Nieuw Project", "⚙️ Updaten", "👤 Gebruikers"]
)

if st.sidebar.button("🚪 Uitloggen"):
    # Wis alle belangrijke status-variabelen
    for key in ["permanent_login", "username", "authenticated"]:
        if key in st.session_state:
            st.session_state[key] = False if key != "username" else None
    
    # Verwijder de cookie
    cookie_manager.delete("auth_token")
    
    # Forceer een schone herstart
    st.rerun()

# ----- Dashboard -----
if menu == "📊 Dashboard":
    st.title("📊 Project Portfolio Overzicht")
    data = get_all_data()

    if not data.empty:
        data['score'] = data['status'].map({
            "Voltooid": 100,
            "Bezig": 50,
            "Nog niet gestart": 0,
            "Start": 10
        }).fillna(0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📁 Actieve Projecten", data['naam'].nunique())
        col2.metric("📈 Gem. Voortgang", f"{int(data['score'].mean())}%")
        col3.metric("🔒 Status", "Beveiligd")
        with col4:
            st.download_button(
                label="📥 Excel Export",
                data=to_excel_professional(data),
                file_name='portfolio_overzicht.xlsx',
                mime=(
                    'application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet'
                )
            )

        st.divider()

        summary = data.groupby('naam')['score'].mean().reset_index()
        cols = st.columns(3)
        for idx, row in summary.iterrows():
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### {row['naam']}")
                    st.progress(int(row['score']) / 100)
                    if st.button("👁️ Details", key=f"detail_{row['naam']}"):
                        st.session_state.selected_project = row['naam']
                        st.rerun()
    else:
        st.warning("⚠️ Geen projecten gevonden. Voeg er een toe!")

# ----- Project details -----
if st.session_state.selected_project and menu == "📊 Dashboard":
    st.header(f"📋 {st.session_state.selected_project}")

    col_back, col_export = st.columns([3, 1])
    with col_back:
        if st.button("⬅️ Terug naar Overzicht"):
            st.session_state.selected_project = None
            st.rerun()

    with col_export:
        display_data = get_all_data()
        display_data['score'] = display_data['status'].map({
            "Voltooid": 100,
            "Bezig": 50,
            "Nog niet gestart": 0,
            "Start": 10
        }).fillna(0)
        proj_data = display_data[
            display_data['naam'] == st.session_state.selected_project
        ]
        st.download_button(
            label="📥 Project Export",
            data=to_excel_professional(proj_data),
            file_name=f'{st.session_state.selected_project}.xlsx'
        )

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_bar = px.bar(
            proj_data, x='fase', y='score', color='score',
            range_y=[0, 110], text_auto=True,
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        fig_pie = px.pie(
            proj_data, names='status',
            color_discrete_map={
                'Voltooid': '#28a745',
                'Bezig': '#ffa500',
                'Nog niet gestart': '#ff4b4b',
                'Start': '#17a2b8'
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("📊 Status Matrix")
    matrix_df = proj_data.pivot(index='naam', columns='fase', values='status')
    st.dataframe(matrix_df, use_container_width=True)

# ----- Nieuw project -----
elif menu == "➕ Nieuw Project":
    st.title("➕ Nieuw Project Toevoegen")
    with st.form("new_project"):
        naam = st.text_input("Projectnaam")
        fases = [
            "Inventarisatie", "Configuratie",
            "Acceptatietest (UAT)", "Training", "Go-Live"
        ]
        statussen = {}
        for fase in fases:
            statussen[fase] = st.selectbox(
                f"{fase}:",
                ["Nog niet gestart", "Bezig", "Voltooid", "Start"],
                key=f"new_{fase}"
            )

        if st.form_submit_button("💾 Project Opslaan", type="primary"):
            try:
                with engine.connect() as conn:
                    for fase, status in statussen.items():
                        conn.execute(
                            text(
                                "INSERT INTO projecten (naam, fase, status) "
                                "VALUES (:n, :f, :s)"
                            ),
                            {"n": naam, "f": fase, "s": status}
                        )
                    conn.commit()
                    st.cache_data.clear() 
                    st.success("✅ Project succesvol opgeslagen!")
                st.rerun()
                st.success(f"✅ Project '{naam}' toegevoegd!")
            except Exception as e:
                st.error(f"❌ Fout: {e}")

# ----- Updaten -----
elif menu == "⚙️ Updaten":
    st.title("⚙️ Project Status Bijwerken")
    data = get_all_data()

    col1, col2 = st.columns([1, 2])
    with col1:
        projecten = sorted(data['naam'].unique()) if not data.empty else []
        selected_project = st.selectbox("Project", [""] + projecten)

    if selected_project:
        with col2:
            fases = [
                "Inventarisatie", "Configuratie",
                "Acceptatietest (UAT)", "Training", "Go-Live"
            ]
            status_updates = {}

            for fase in fases:
                current_status = data[
                    (data['naam'] == selected_project) &
                    (data['fase'] == fase)
                ]['status']
                idx = 0 if current_status.empty else [
                    "Nog niet gestart", "Start", "Bezig", "Voltooid"
                ].index(current_status.iloc[0])
                status_updates[fase] = st.selectbox(
                    f"{fase}",
                    ["Nog niet gestart", "Start", "Bezig", "Voltooid"],
                    index=idx, key=f"update_{fase}"
                )

            if st.button("💾 Bijwerken", type="primary"):
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text("DELETE FROM projecten WHERE naam = :n"),
                            {"n": selected_project}
                        )
                        for fase, status in status_updates.items():
                            conn.execute(
                                text(
                                    "INSERT INTO projecten (naam, fase, status) "
                                    "VALUES (:n, :f, :s)"
                                ),
                                {"n": selected_project, "f": fase, "s": status}
                            )
                        conn.commit()
                    st.success("✅ Project bijgewerkt!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Fout: {e}")

# ----- Gebruikers -----
elif menu == "👤 Gebruikers":
    st.title("👤 Gebruikersbeheer")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Nieuwe Gebruiker")
        with st.form("new_user"):
            new_username = st.text_input("Gebruikersnaam")
            new_password = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Toevoegen"):
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                "INSERT INTO gebruikers (username, password) "
                                "VALUES (:u, :p)"
                            ),
                            {"u": new_username, "p": new_password}
                        )
                        conn.commit()
                    st.success("✅ Gebruiker toegevoegd!")
                except Exception as e:
                    st.error(f"❌ Fout: {e}")

    with col2:
        st.subheader("📋 Huidige Gebruikers")
        try:
            users = pd.read_sql("SELECT username FROM gebruikers", engine)
            st.dataframe(users)
        except Exception:
            st.info("Geen gebruikers gevonden.")
