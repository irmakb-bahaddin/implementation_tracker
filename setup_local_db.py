from sqlalchemy import create_engine, text

# --- CONFIGURATIE VOOR JE LOKALE POSTGRES ---
USER = "postgres"
PASSWORD = "welkom01"  # <<< HIER INVOEREN
HOST = "localhost"
PORT = "5432"
DB = "project_db"

DB_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"


def setup_database():
    """Maakt de verbinding en richt de tabellen in op je laptop."""
    try:
        print(f"Verbinding maken met lokale database: {DB}...")
        engine = create_engine(DB_URL)

        with engine.connect() as connection:
            # Tabel projecten
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS projecten (
                    id SERIAL PRIMARY KEY,
                    naam TEXT NOT NULL,
                    fase TEXT NOT NULL,
                    status TEXT DEFAULT 'Start'
                )
            """))

            # Tabel gebruikers
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS gebruikers (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """))

            # Admin-gebruiker
            connection.execute(text("""
                INSERT INTO gebruikers (username, password)
                VALUES ('admin', 'admin')
                ON CONFLICT (username) DO NOTHING
            """))

            connection.commit()
            print("SUCCES: Tabellen 'projecten' en 'gebruikers' zijn aangemaakt!")
    except Exception as e:
        print(f"FOUT: Kon geen verbinding maken: {e}")


if __name__ == "__main__":
    setup_database()
