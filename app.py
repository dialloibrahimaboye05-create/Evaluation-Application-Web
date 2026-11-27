"""Projet Data Collection - application Streamlit
Sources : Books to Scrape, Gaaraas (véhicules), Dakar-Auto (motos), bulletins météo ANACIM.
Menu : Scraper | Télécharger (brut) | Dashboard (nettoyé) | Base SQL | Évaluer l'application
"""
import os, re, time, sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
 
# ---------- LIENS DES FORMULAIRES ----------
KOBO_URL = "https://ee.kobotoolbox.org/5JoTzj60"
GFORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScd5gfeETaTnMoeny6c_Xi6WV_JX3Nn8dVi1G-hINuQVdUxHw/viewform"
# -------------------------------------------
 
DB = "data/collecte.db"
SOURCES = {"Books to Scrape": "books", "Gaaraas": "gaaraas", "Dakar-Auto Motos": "motos", "Bulletins météo": "meteo"}
 
st.set_page_config(page_title="Data Collection App", page_icon="📊", layout="wide")
 
# ======================= STYLE =======================
st.markdown("""
<style>
.stApp {background: linear-gradient(135deg, #0a5f6b 0%, #0f8f9e 60%, #17a5b3 100%);}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li, .stApp label p,
.stApp [data-testid="stMarkdownContainer"] > p {color: #f4fbfc;}
.stApp a {color: #d8f1ff;}
h1 {text-align: center;}
[data-testid="stSidebar"] {background-color: #7bb3e3;}
[data-testid="stSidebar"] * {color: #10253a !important;}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] * {color: #f4fbfc !important;}
.stButton button, .stDownloadButton button, .stLinkButton a {background-color: #e8eef2; border: none; font-weight: 600;}
.stButton button *, .stDownloadButton button *, .stLinkButton a * {color: #10253a !important;}
[data-baseweb="select"] *, textarea {color: #10253a !important;}
[data-testid="stAlert"] * {color: #10253a !important;}
</style>
""", unsafe_allow_html=True)
 
 
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
        cartes = driver.find_elements(By.CSS_SELECTOR, "article.product_pod")
        for c in cartes:
            try:
                note = c.find_element(By.CSS_SELECTOR, "p.star-rating").get_attribute("class").split()[-1]
                data.append({
                    "titre": c.find_element(By.CSS_SELECTOR, "h3 a").get_attribute("title"),
                    "prix": c.find_element(By.CSS_SELECTOR, "p.price_color").text,
                    "disponibilite": c.find_element(By.CSS_SELECTOR, "p.availability").text.strip(),
                    "note": RATING.get(note),
                    "nb_produits_page": len(cartes),
                    "page": i,
                })
            except Exception:
                pass
    return pd.DataFrame(data)
 
 
MARQUES_AUTO = ["Land Rover", "Range Rover", "Alfa Romeo", "Aston Martin", "Great Wall", "Rolls Royce"]
 
 
def scrape_gaaraas(driver, n_pages):
    data = []
    for i in range(1, n_pages + 1):
        driver.get(f"https://www.gaaraas.com/fr/users/dakar-auto?page={i}")
        time.sleep(3)
        containers = driver.find_elements(By.CSS_SELECTOR, ".common-ad-card")
        if not containers:
            break
        for c in containers:
            try:
                lignes = [l.strip() for l in c.text.split("\n") if l.strip()]
                titre = next((l for l in lignes if re.match(r"^(19|20)\d{2}\s", l)), None)
                annee = marque = modele = region = None
                if titre:
                    annee = titre[:4]
                    reste = titre[5:].strip()
                    marque = next((m for m in MARQUES_AUTO if reste.startswith(m)), reste.split(" ")[0])
                    modele = reste[len(marque):].strip()
                    k = lignes.index(titre)
                    region = lignes[k + 1] if k + 1 < len(lignes) else None
                data.append({
                    "marque": marque, "modele": modele, "annee": annee,
                    "prix": lignes[lignes.index("PRIX") + 1] if "PRIX" in lignes else None,
                    "kilometrage": lignes[lignes.index("KILOMÉTRAGE") + 1] if "KILOMÉTRAGE" in lignes else None,
                    "boite": next((l for l in lignes if l != titre and ("manuel" in l.lower() or "automat" in l.lower())), None),
                    "region": region, "url": c.get_attribute("href"), "page": i})
            except Exception:
                pass
    return pd.DataFrame(data)
 
 
MARQUES_MOTOS = ["Royal Enfield", "Harley Davidson", "Moto Guzzi", "Can-Am", "Super Soco"]
 
 
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
                marque = next((x for x in MARQUES_MOTOS if reste.startswith(x)), reste.split(" ")[0] if reste else None)
                prix = next((l for l in lignes if "CFA" in l), None)
                region = lignes[lignes.index(prix) + 1] if prix and lignes.index(prix) + 1 < len(lignes) else None
                data.append({"marque": marque, "modele": reste[len(marque):].strip() if marque else None,
                             "annee": m.group(0) if m else None, "prix": prix, "region": region,
                             "url": lien.get_attribute("href"), "page": i})
            except Exception:
                pass
    return pd.DataFrame(data)
 
 
SCRAPERS = {"Books to Scrape": ("books_scrape", scrape_books),
            "Gaaraas (véhicules)": ("gaaraas_scrape", scrape_gaaraas),
            "Dakar-Auto (motos)": ("motos_scrape", scrape_motos)}
 
 
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
 
 
# ======================= SECTIONS =======================
def section_scraper(n_pages):
    st.subheader("🕷️ Scraper des données (Selenium)")
    st.write(f"Choisis une source : le scraping porte sur **{n_pages} page(s)**.")
    cols = st.columns(len(SCRAPERS))
    for col, nom in zip(cols, SCRAPERS):
        if col.button(nom):
            with st.spinner(f"Scraping de {nom} en cours..."):
                try:
                    driver = get_driver()
                    try:
                        df = SCRAPERS[nom][1](driver, n_pages)
                    finally:
                        driver.quit()
                    st.session_state["scrape_df"], st.session_state["scrape_nom"] = df, nom
                except Exception as e:
                    st.error(f"Erreur pendant le scraping : {e}")
    if "scrape_df" in st.session_state:
        df, nom = st.session_state["scrape_df"], st.session_state["scrape_nom"]
        st.markdown(f"### Dimension des données : {nom}")
        st.write(f"**{df.shape[0]} lignes et {df.shape[1]} colonnes.**")
        st.dataframe(df)
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ Télécharger en CSV", df.to_csv(index=False).encode("utf-8"), "scraping.csv", "text/csv")
        if c2.button("💾 Enregistrer dans la base SQL"):
            table = SCRAPERS[nom][0]
            sauver_table(df, table)
            st.success(f"Données ajoutées à la table {table}")
 
 
def section_telecharger():
    st.subheader("⬇️ Télécharger les données brutes (Web Scraper, non nettoyées)")
    dossier = "data/raw"
    fichiers = sorted(f for f in os.listdir(dossier) if f.endswith(".csv")) if os.path.isdir(dossier) else []
    if not fichiers:
        st.warning("Aucun fichier dans data/raw.")
    for f in fichiers:
        df = pd.read_csv(os.path.join(dossier, f))
        with st.expander(f"{f} — {df.shape[0]} lignes, {df.shape[1]} colonnes"):
            st.dataframe(df.head(50))
            with open(os.path.join(dossier, f), "rb") as fh:
                st.download_button("Télécharger", fh.read(), f, "text/csv", key=f)
 
 
def dashboard_source(df, cle):
    num = df.select_dtypes("number").columns.tolist()
    cat = [c for c in df.columns if c not in num and 1 < df[c].nunique() <= 60]
    k = st.columns(3)
    k[0].metric("Lignes", f"{len(df):,}".replace(",", " "))
    k[1].metric("Colonnes", df.shape[1])
    k[2].metric("Valeurs manquantes", int(df.isna().sum().sum()))
    c1, c2 = st.columns(2)
    if cat:
        i = next((j for j, c in enumerate(cat) if "marque" in c.lower() or "station" in c.lower() or "categorie" in c.lower()), 0)
        col = c1.selectbox("Variable catégorielle", cat, index=i, key=cle + "c")
        top = df[col].value_counts().head(12).reset_index()
        top.columns = [col, "effectif"]
        c1.plotly_chart(px.bar(top, x=col, y="effectif", title=f"Top {col}", template="plotly_white"))
    if num:
        j = next((k2 for k2, c in enumerate(num) if "prix" in c.lower() or "tmax" in c.lower()), 0)
        col = c2.selectbox("Variable numérique", num, index=j, key=cle + "n")
        c2.plotly_chart(px.histogram(df, x=col, nbins=30, title=f"Distribution de {col}", template="plotly_white"))
    if num and cat:
        a, b = st.columns(2)
        cc = a.selectbox("Grouper par", cat, key=cle + "g")
        nn = b.selectbox("Moyenne de", num, key=cle + "m")
        m = df.groupby(cc)[nn].mean().sort_values(ascending=False).head(15).reset_index()
        st.plotly_chart(px.bar(m, x=cc, y=nn, title=f"Moyenne de {nn} par {cc}", template="plotly_white"))
    with st.expander("Voir les données nettoyées"):
        st.dataframe(df)
 
 
def section_dashboard():
    st.subheader("📈 Dashboard des données nettoyées (Selenium)")
    tabs = st.tabs(list(SOURCES.keys()))
    for tab, (nom, cle) in zip(tabs, SOURCES.items()):
        with tab:
            df = lire_table(f"{cle}_nettoye")
            if df is None:
                st.warning(f"Table {cle}_nettoye introuvable dans {DB}.")
            else:
                dashboard_source(df, cle)
 
 
def section_sql():
    st.subheader("🗄️ Base de données SQL (SQLite)")
    if not os.path.exists(DB):
        st.warning("Base introuvable.")
        return
    with sqlite3.connect(DB) as conn:
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)["name"].tolist()
        t = st.selectbox("Table", tables)
        st.dataframe(pd.read_sql_query(f"SELECT * FROM {t} LIMIT 200", conn))
        req = st.text_area("Requête SQL (lecture seule)", f"SELECT COUNT(*) AS nb FROM {t}")
        if st.button("Exécuter la requête"):
            if req.strip().lower().startswith("select"):
                try:
                    st.dataframe(pd.read_sql_query(req, conn))
                except Exception as e:
                    st.error(e)
            else:
                st.error("Seules les requêtes SELECT sont autorisées.")
 
 
def section_evaluation():
    st.subheader("📝 Évaluer l'application")
    st.write("Deux versions du formulaire d'évaluation sont disponibles :")
    c1, c2 = st.columns(2)
    c1.link_button("Formulaire Kobo", KOBO_URL)
    c2.link_button("Formulaire Google Forms", GFORM_URL)
 
 
# ======================= PAGE =======================
OPTIONS = ["Scraper les données", "Télécharger les données brutes", "Dashboard des données",
           "Base de données SQL", "Évaluer l'application"]
 
st.sidebar.header("Paramètres")
n_pages = st.sidebar.selectbox("Nombre de pages à scraper", list(range(1, 11)), index=1)
option = st.sidebar.selectbox("Options", OPTIONS)
 
st.title("📊 DATA COLLECTION APP")
st.write("Cette application collecte des données par web scraping sur plusieurs pages, permet de télécharger "
         "les données brutes (non nettoyées) et affiche un dashboard des données nettoyées.")
st.markdown("- **Bibliothèques Python** : pandas, streamlit, selenium, plotly, sqlite3\n"
            "- **Sources** : [Books to Scrape](https://books.toscrape.com) · "
            "[Gaaraas](https://www.gaaraas.com/fr/users/dakar-auto) · "
            "[Dakar-Auto motos](https://dakar-auto.com/senegal/motos-and-scooters-3) · "
            "bulletins climatologiques de l'ANACIM")
st.divider()
 
if option == OPTIONS[0]:
    section_scraper(n_pages)
elif option == OPTIONS[1]:
    section_telecharger()
elif option == OPTIONS[2]:
    section_dashboard()
elif option == OPTIONS[3]:
    section_sql()
else:
    section_evaluation()
 
