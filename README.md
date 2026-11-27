# Projet Data Collection

Application Streamlit de collecte, de téléchargement et de visualisation de données.

**Sources** : Books to Scrape, Gaaraas (annonces auto Dakar), Dakar-Auto (motos et scooters), bulletins climatologiques de l'ANACIM (PDF).

**Contenu**
- `app.py` : application (scraping Selenium, téléchargement des données brutes, dashboard des données nettoyées, base SQL, formulaires d'évaluation Kobo et Google Forms)
- `data/collecte.db` : base SQLite (une table brute et une table nettoyée par source)
- `data/raw/` : données brutes non nettoyées (Web Scraper)
- notebook Colab : scraping Selenium et nettoyage

**Lancer en local**
```
pip install -r requirements.txt
streamlit run app.py
```
