# pylint: skip-file
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import extra_streamlit_components as stx
from io import BytesIO
import datetime


# =========================
# APP CONFIG
# =========================
st.set_page_config(
    page_title="Project Portaal",
    page_icon="📈",
    layout="wide"
)

cookie_manager = stx.CookieManager()

# =========================
# DATABASE
# =========================
@st.cache_resource
def get_engine():
    return create_engine(
        st.secrets["DB_URL"],
        pool_pre_ping=True
    )

engine = get_engine()

@st.cache_data(ttl=600)
def get_data(query: str, params: dict | None = None):
    with engine.connect() as conn:
        return pd.read_sql(
            text(query),
            conn,
            params=params
        )


# =========================
# AUTH
# =========================
def check_login(username, password):
    query = text("""
        SELECT 1 FROM gebruikers
        WHERE username = :u AND password = :p
    """)
    with engine.connect() as conn:
        return conn.execute(
            query, {"u": username, "p": password}
        ).fetchone() is not None

def logout():
    try:
        cookie_manager.delete("auth_token")
    except:
        pass
    st.session_state.clear()
    st.query_params["logout"] = "true"
    st.rerun()

# =========================
# SESSION STATE
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = None

if "geselecteerd_project" not in st.session_state:
    st.session_state.geselecteerd_project = None

# =========================
# LOGOUT PARAM
# =========================
if st.query_params.get("logout") == "true":
    st.session_state.clear()
    try:
        cookie_manager.delete("auth_token")
    except:
        pass
    st.query_params.clear()
    st.rerun()

# =========================
# AUTO LOGIN COOKIE
# =========================
if not st.session_state.logged_in:
    try:
        token = cookie_manager.get("auth_token")
        if token:
            st.session_state.logged_in = True
            st.session_state.username = token
            st.rerun()
    except:
        pass

# =========================
# LOGIN SCHERM
# =========================
if not st.session_state.logged_in:
    st.title("🔐 Inloggen")

    with st.form("login_form"):
        username = st.text_input("Gebruikersnaam")
        password = st.text_input("Wachtwoord", type="password")
        if st.form_submit_button("Inloggen"):
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                cookie_manager.set(
                    "auth_token",
                    username,
                    expires_at=datetime.datetime.now()
                    + datetime.timedelta(days=30)
                )
                st.success("Inloggen gelukt")
                st.rerun()
            else:
                st.error("Onjuiste gegevens")

    st.stop()

# =========================
# SIDEBAR
# =========================
menu = st.sidebar.radio(
    "Navigatie",
    ["📊 Dashboard", "➕ Nieuw Project", "⚙️ Updaten", "👤 Gebruikers"]
)

if st.sidebar.button("🚪 Uitloggen"):
    logout()

# =========================
# HULPFUNCTIES
# =========================
def score_map(status):
    return {
        "Nog niet gestart": 0,
        "Start": 10,
        "Bezig": 50,
        "Voltooid": 100
    }.get(status, 0)

def export_excel(df):
    output = BytesIO()
    pivot = df.pivot(index="naam", columns="fase", values="status")

    scores = (
        df.assign(score=df["status"].apply(score_map))
        .groupby("naam")["score"]
        .mean()
        .round(0)
        .astype(int)
    )

    pivot["Voortgang %"] = scores

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pivot.to_excel(writer, sheet_name="Overzicht")
    return output.getvalue()

# =========================
# DASHBOARD
# =========================
if menu == "📊 Dashboard":
    st.title("📊 Project Portfolio")

    data = get_data("SELECT * FROM projecten")
    if data.empty:
        st.info("Geen projecten gevonden")
    else:
        data["score"] = data["status"].apply(score_map)

        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        col1.metric("Projecten", data["naam"].nunique())
        col2.metric("Gem. voortgang", f"{int(data['score'].mean())}%")
        col3.metric("Gebruiker", st.session_state.username)
        col4.download_button(
            "📥 Excel Export",
            export_excel(data),
            "portfolio.xlsx"
        )

        st.divider()

        summary = data.groupby("naam")["score"].mean().reset_index()
        cols = st.columns(3)

        for i, row in summary.iterrows():
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(row["naam"])
                    st.progress(int(row["score"]) / 100)
                    if st.button("Details", key=row["naam"]):
                        st.session_state.geselecteerd_project = row["naam"]
                        st.rerun()
@st.cache_data
def get_project_details(conn, project_naam):
    query = text("""
        SELECT
            p.naam AS project,
            f.fase,
            f.status,
            f.score
        FROM projecten p
        JOIN project_fases f ON f.project_id = p.id
        WHERE p.naam = :project_naam
        ORDER BY f.volgorde
    """)
    return pd.read_sql(query, conn, params={"project_naam": project_naam})


# =========================
# PROJECT DETAILS
# =========================
if menu == "📊 Dashboard" and st.session_state.geselecteerd_project:
    project = st.session_state.geselecteerd_project
    st.header(f"📋 {project}")
    if st.button("⬅ Terug"):
        st.session_state.geselecteerd_project = None
        st.rerun()

    df = get_data(
        "SELECT * FROM projecten WHERE naam = :n",
        {"n": project}
    ).assign(score=lambda x: x["status"].apply(score_map))

    volgorde = [
        "Inventarisatie",
        "Configuratie",
        "Acceptatietest (UAT)",
        "Training",
        "Go-Live"
    ]

    df["fase"] = pd.Categorical(df["fase"], volgorde, ordered=True)
    df = df.sort_values("fase")    

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Voortgang per fase")
        fig = px.bar(
            df, x="fase", y="score",
            range_y=[0, 100],
            color_discrete_sequence=['#00FF00'] # Gebruik hier een HEX-code voor bijv. groen
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Status verdeling")
        status_kleuren = {
            "Voltooid": "green",
            "Bezig": "orange",
            "Nog niet gestart": "red"
        }
        
        # Alles moet binnen de haakjes van px.pie staan
        fig = px.pie(
            df, 
            names="status",
            color="status", 
            color_discrete_map=status_kleuren,
            category_orders={"status": ["Voltooid", "Bezig", "Nog niet gestart"]}
        ) 
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Matrix")
    matrix = df.pivot(index="naam", columns="fase", values="status")
    st.dataframe(matrix, use_container_width=True)

# =========================
# NIEUW PROJECT
# =========================
if menu == "➕ Nieuw Project":
    st.title("➕ Nieuw Project")

    fases = [
        "Inventarisatie",
        "Configuratie",
        "Acceptatietest (UAT)",
        "Training",
        "Go-Live"
    ]

    with st.form("nieuw_project"):
        naam = st.text_input("Projectnaam")
        statussen = {
            f: st.selectbox(f, ["Nog niet gestart", "Start", "Bezig", "Voltooid"])
            for f in fases
        }

        if st.form_submit_button("Opslaan"):
            with engine.begin() as conn:
                for fase, status in statussen.items():
                    conn.execute(
                        text("""
                            INSERT INTO projecten (naam, fase, status)
                            VALUES (:n, :f, :s)
                        """),
                        {"n": naam, "f": fase, "s": status}
                    )
            st.cache_data.clear()
            st.success("Project toegevoegd")
            st.rerun()

# =========================
# UPDATEN
# =========================
if menu == "⚙️ Updaten":
    st.title("⚙️ Project bijwerken")

    data = get_data("SELECT * FROM projecten")
    project = st.selectbox(
        "Selecteer project",
        [""] + sorted(data["naam"].unique())
    )

    if project:
        fases = data[data["naam"] == project]

        updates = {}
        for _, row in fases.iterrows():
            updates[row["fase"]] = st.selectbox(
                row["fase"],
                ["Nog niet gestart", "Start", "Bezig", "Voltooid"],
                index=[
                    "Nog niet gestart",
                    "Start",
                    "Bezig",
                    "Voltooid"
                ].index(row["status"]),
                key=row["fase"]
            )

        if st.button("💾 Bijwerken"):
            with engine.begin() as conn:
                for fase, status in updates.items():
                    conn.execute(
                        text("""
                            UPDATE projecten
                            SET status = :s
                            WHERE naam = :n AND fase = :f
                        """),
                        {"s": status, "n": project, "f": fase}
                    )
            st.cache_data.clear()
            st.success("Bijgewerkt")
            st.rerun()

        st.divider()
        nieuwe_naam = st.text_input("Project hernoemen", value=project)

        if st.button("Naam wijzigen"):
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE projecten
                        SET naam = :nieuw
                        WHERE naam = :oud
                    """),
                    {"nieuw": nieuwe_naam, "oud": project}
                )
            st.cache_data.clear()
            st.success("Naam aangepast")
            st.rerun()

        st.divider()
        if st.button("🗑 Verwijderen"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM projecten WHERE naam = :n"),
                    {"n": project}
                )
            st.cache_data.clear()
            st.warning("Project verwijderd")
            st.rerun()

# =========================
# GEBRUIKERS
# =========================
if menu == "👤 Gebruikers":
    st.title("👤 Gebruikers")

    col1, col2 = st.columns(2)

    with col1:
        with st.form("nieuwe_gebruiker"):
            u = st.text_input("Gebruikersnaam")
            p = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Toevoegen"):
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO gebruikers (username, password)
                            VALUES (:u, :p)
                        """),
                        {"u": u, "p": p}
                    )
                st.success("Gebruiker toegevoegd")

    with col2:
        users = get_data("SELECT username FROM gebruikers")
        st.dataframe(users, use_container_width=True)
