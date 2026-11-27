"""Application Streamlit - Projet Data Collection
4 sources : Books to Scrape, Gaaraas (auto), Dakar-Auto (motos), Bulletins météo ANACIM.
Menu : Accueil | Scraper | Télécharger (brut) | Dashboard (nettoyé) | Base SQL | Évaluation
"""
import os, re, time, sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ---------- À REMPLIR AVEC TES LIENS ----------
KOBO_URL = "https://ee.kobotoolbox.org/5JoTzj60"
GFORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScd5gfeETaTnMoeny6c_Xi6WV_JX3Nn8dVi1G-hINuQVdUxHw/viewform"
# -----------------------------------------------

DB = "data/collecte.db"
SOURCES = {"Books to Scrape": "books", "Gaaraas": "gaaraas", "Dakar-Auto Motos": "motos", "Bulletins météo": "meteo"}

st.set_page_config(page_title="Data Collection", page_icon="📊", layout="wide")


# ======================= SELENIUM (headless) =======================
def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1000")
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if os.path.exists(p):
            opts.binary_location = p
    for d in ("/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver"):
        if os.path.exists(d):
            return webdriver.Chrome(service=Service(d), options=opts)
    return webdriver.Chrome(options=opts)        # en local : Selenium Manager


RATING = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def scrape_books(driver, n_pages):
    data = []
    for i in range(1, n_pages + 1):
        driver.get(f"https://books.toscrape.com/catalogue/page-{i}.html")
        for c in driver.find_elements(By.CSS_SELECTOR, "article.product_pod"):
            try:
                note = c.find_element(By.CSS_SELECTOR, "p.star-rating").get_attribute("class").split()[-1]
                data.append({
                    "titre": c.find_element(By.CSS_SELECTOR, "h3 a").get_attribute("title"),
                    "prix": c.find_element(By.CSS_SELECTOR, "p.price_color").text,
                    "disponibilite": c.find_element(By.CSS_SELECTOR, "p.availability").text.strip(),
                    "note": RATING.get(note),
                    "page": i,
                })
            except Exception:
                pass
    return pd.DataFrame(data)


MARQUES_2 = ["Royal Enfield", "Harley Davidson", "Moto Guzzi", "Can-Am", "Super Soco"]


def scrape_motos(driver, n_pages):
    data = []
    for i in range(1, n_pages + 1):
        driver.get(f"https://dakar-auto.com/senegal/motos-and-scooters-3?&page={i}")
        time.sleep(2)
        cartes = driver.find_elements(By.CSS_SELECTOR, "div.listings-cards__list-item")
        if not cartes:
            break
        for c in cartes:
            try:
                lignes = [l.strip() for l in c.text.split("\n") if l.strip()]
                lien = c.find_element(By.CSS_SELECTOR, "a.listing-card__aside__inner")
                titre = lien.get_attribute("title") or ""
                m = re.search(r"(19|20)\d{2}$", titre.strip())
                reste = titre.strip()[:-4].strip() if m else titre.strip()
                marque = next((x for x in MARQUES_2 if reste.startswith(x)), reste.split(" ")[0] if reste else None)
                prix = next((l for l in lignes if "CFA" in l), None)
                region = lignes[lignes.index(prix) + 1] if prix and lignes.index(prix) + 1 < len(lignes) else None
                data.append({"marque": marque, "modele": reste[len(marque):].strip() if marque else None,
                             "annee": m.group(0) if m else None, "prix": prix, "region": region,
                             "url": lien.get_attribute("href"), "page": i})
            except Exception:
                pass
    return pd.DataFrame(data)


# ======================= BASE SQL =======================
def lire_table(nom):
    if not os.path.exists(DB):
        return None
    try:
        with sqlite3.connect(DB) as conn:
            return pd.read_sql_query(f"SELECT * FROM {nom}", conn)
    except Exception:
        return None


def sauver_table(df, nom):
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB) as conn:
        df.to_sql(nom, conn, index=False, if_exists="append")


# ======================= PAGES =======================
def page_accueil():
    st.title("📊 Projet Data Collection")
    st.write("Application de **collecte (scraping)**, de **téléchargement** et de **visualisation** de données "
             "sur quatre sources : Books to Scrape, Gaaraas, Dakar-Auto (motos) et bulletins météo de l'ANACIM.")
    c = st.columns(4)
    for col, (nom, cle) in zip(c, SOURCES.items()):
        df = lire_table(f"{cle}_nettoye")
        col.metric(nom, "—" if df is None else f"{len(df):,} lignes".replace(",", " "))
    st.info("Utilise le menu à gauche : Scraper, Télécharger, Dashboard, Base SQL, Évaluation.")


def page_scraper():
    st.header("🕷️ Scraper des données (Selenium)")
    source = st.selectbox("Source", ["Books to Scrape", "Dakar-Auto Motos"])
    n = st.slider("Nombre de pages à scraper", 1, 10, 2)
    if st.button("Lancer le scraping", type="primary"):
        with st.spinner("Scraping en cours..."):
            driver = get_driver()
            try:
                df = scrape_books(driver, n) if source == "Books to Scrape" else scrape_motos(driver, n)
            finally:
                driver.quit()
        st.session_state["scrape_df"] = df
        st.session_state["scrape_source"] = source
    if "scrape_df" in st.session_state:
        df = st.session_state["scrape_df"]
        st.success(f"{len(df)} lignes collectées")
        st.dataframe(df, use_container_width=True)
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8"), "scraping.csv", "text/csv")
        if c2.button("💾 Enregistrer dans la base SQL"):
            table = "books_scrape" if st.session_state["scrape_source"] == "Books to Scrape" else "motos_scrape"
            sauver_table(df, table)
            st.success(f"Données ajoutées à la table {table}")


def page_telecharger():
    st.header("⬇️ Télécharger les données brutes (Web Scraper, non nettoyées)")
    st.caption("Fichiers exportés depuis l'extension Chrome Web Scraper (aucun nettoyage).")
    dossier = "data/raw"
    fichiers = sorted(f for f in os.listdir(dossier) if f.endswith(".csv")) if os.path.isdir(dossier) else []
    if not fichiers:
        st.warning("Aucun fichier dans data/raw. Ajoute tes exports Web Scraper dans ce dossier du dépôt GitHub.")
    for f in fichiers:
        df = pd.read_csv(os.path.join(dossier, f))
        with st.expander(f"{f} — {len(df)} lignes"):
            st.dataframe(df.head(50), use_container_width=True)
            with open(os.path.join(dossier, f), "rb") as fh:
                st.download_button("Télécharger", fh.read(), f, "text/csv", key=f)


def dashboard_generique(df, titre):
    num = df.select_dtypes("number").columns.tolist()
    cat = [c for c in df.columns if c not in num and df[c].nunique() <= 60 and df[c].nunique() > 1]
    k = st.columns(3)
    k[0].metric("Lignes", f"{len(df):,}".replace(",", " "))
    k[1].metric("Colonnes", df.shape[1])
    k[2].metric("Valeurs manquantes", int(df.isna().sum().sum()))
    c1, c2 = st.columns(2)
    if num:
        col = c1.selectbox("Variable numérique", num, key=titre + "n")
        c1.plotly_chart(px.histogram(df, x=col, nbins=30, title=f"Distribution de {col}"), use_container_width=True)
    if cat:
        col = c2.selectbox("Variable catégorielle", cat, key=titre + "c")
        top = df[col].value_counts().head(15).reset_index()
        top.columns = [col, "effectif"]
        c2.plotly_chart(px.bar(top, x=col, y="effectif", title=f"Top {col}"), use_container_width=True)
    if num and cat:
        a, b = st.columns(2)
        cc = a.selectbox("Grouper par", cat, key=titre + "g")
        nn = b.selectbox("Moyenne de", num, key=titre + "m")
        m = df.groupby(cc)[nn].mean().sort_values(ascending=False).head(15).reset_index()
        st.plotly_chart(px.bar(m, x=cc, y=nn, title=f"Moyenne de {nn} par {cc}"), use_container_width=True)
    with st.expander("Voir les données nettoyées"):
        st.dataframe(df, use_container_width=True)


def page_dashboard():
    st.header("📈 Dashboard des données nettoyées (Selenium)")
    tabs = st.tabs(list(SOURCES.keys()))
    for tab, (nom, cle) in zip(tabs, SOURCES.items()):
        with tab:
            df = lire_table(f"{cle}_nettoye")
            if df is None:
                st.warning(f"Table {cle}_nettoye introuvable dans {DB}.")
            else:
                dashboard_generique(df, cle)


def page_sql():
    st.header("🗄️ Base de données SQL (SQLite)")
    if not os.path.exists(DB):
        st.warning("Base introuvable.")
        return
    with sqlite3.connect(DB) as conn:
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)["name"].tolist()
        t = st.selectbox("Table", tables)
        st.dataframe(pd.read_sql_query(f"SELECT * FROM {t} LIMIT 200", conn), use_container_width=True)
        req = st.text_area("Requête SQL (lecture seule)", f"SELECT COUNT(*) AS nb FROM {t}")
        if st.button("Exécuter"):
            if req.strip().lower().startswith("select"):
                try:
                    st.dataframe(pd.read_sql_query(req, conn), use_container_width=True)
                except Exception as e:
                    st.error(e)
            else:
                st.error("Seules les requêtes SELECT sont autorisées.")


def page_evaluation():
    st.header("📝 Évaluer l'application")
    st.write("Deux versions du formulaire d'évaluation sont disponibles :")
    c1, c2 = st.columns(2)
    c1.link_button("Formulaire Kobo", KOBO_URL, use_container_width=True)
    c2.link_button("Formulaire Google Forms", GFORM_URL, use_container_width=True)


PAGES = {"🏠 Accueil": page_accueil, "🕷️ Scraper": page_scraper, "⬇️ Télécharger (brut)": page_telecharger,
         "📈 Dashboard (nettoyé)": page_dashboard, "🗄️ Base SQL": page_sql, "📝 Évaluation": page_evaluation}
choix = st.sidebar.radio("Menu", list(PAGES.keys()))
PAGES[choix]()
