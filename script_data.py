import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(layout="wide")
st.title("Carte de France")

# état global
if "selected_region" not in st.session_state:
    st.session_state.selected_region = None

@st.cache_data
def load_data():
    df = pd.read_csv("datasets/Taux_de_mortalite.csv", sep=",", encoding="utf-8")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "Unnamed: 0": "code_dep",
        "Département": "departement",
        "Taux de mortalité standard. des 0-64 ans en 2024 (prématuré) (en ‰)": "taux_premature"
    })

    df["code_dep"] = df["code_dep"].astype(str)

    df["taux_premature"] = (
        df["taux_premature"].astype(str)
        .str.replace(",", ".", regex=False)
    )
    df["taux_premature"] = pd.to_numeric(df["taux_premature"], errors="coerce")

    return df

df = load_data()

regions = {
    "Île-de-France": ["75","77","78","91","92","93","94","95"],
    "Normandie": ["14","27","50","61","76"],
    "Bretagne": ["22","29","35","56"],
    "Grand Est": ["08","10","51","52","54","55","57","67","68","88"],
    "Occitanie": ["09","11","12","30","31","32","34","46","48","65","66","81","82"],
    "Auvergne-Rhône-Alpes": ["01","03","07","15","26","38","42","43","63","69","73","74"],
    "Provence-Alpes-Côte d'Azur": ["04","05","06","13","83","84"],
    "Nouvelle-Aquitaine": ["16","17","19","23","24","33","40","47","64","79","86","87"],
    "Pays de la Loire": ["44","49","53","72","85"],
    "Centre-Val de Loire": ["18","28","36","37","41","45"],
    "Bourgogne-Franche-Comté": ["21","25","39","58","70","71","89","90"],
    "Hauts-de-France": ["02","59","60","62","80"],
    "Corse": ["2A","2B"]
}

mapping_region = {
    dep: reg for reg, deps in regions.items() for dep in deps
}

df["region"] = df["code_dep"].map(mapping_region)

df = df.copy()

@st.cache_data
def load_geojson_dep():
    url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
    return requests.get(url).json()

@st.cache_data
def load_geojson_regions():
    url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson"
    return requests.get(url).json()

geojson_dep = load_geojson_dep()
geojson_reg = load_geojson_regions()

region_choice = st.sidebar.selectbox(
    " Choisir une région",
    ["France entière"] + sorted(df["region"].dropna().unique())
)

if region_choice != "France entière":
    st.session_state.selected_region = region_choice
else:
    st.session_state.selected_region = None

if st.session_state.selected_region is None:

    df_regions = df.groupby("region", as_index=False).agg({
        "taux_premature": "mean"
    })

    fig = px.choropleth(
        df_regions,
        geojson=geojson_reg,
        locations="region",
        featureidkey="properties.nom",
        color="taux_premature",
        color_continuous_scale="Teal",
    #     range_color=(
    #         df["taux_premature"].min(),
    #         df["taux_premature"].max()
    # ),
        # hover_name="region",
        title="Vue régionale"
    )

    fig.update_geos(fitbounds="locations", visible=False)

    st.plotly_chart(fig, width="stretch")

else:
    region = st.session_state.selected_region

    st.subheader(f"{region}")

    df_region = df[df["region"] == region]

    fig = px.choropleth(
        df_region,
        geojson=geojson_dep,
        locations="code_dep",
        featureidkey="properties.code",
        color="taux_premature",
        color_continuous_scale="Teal",
        range_color=(
        df["taux_premature"].min(),
        df["taux_premature"].max()
    ),
        hover_name="departement",
        # title=f"{region}"
    )

    fig.update_geos(fitbounds="locations", visible=False)

    st.plotly_chart(fig, width="stretch")



import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import os
 
# ─── Configuration page ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Carte des médecins généralistes",
    layout="wide",
)
 
st.title("Carte des médecins généralistes")
 
# ─── Chargement et traitement des données ─────────────────────────────────────
CSV_PATH = os.path.join(os.path.dirname(__file__), "datasets/annuaire-des-entreprises-etablissements.csv")
 
@st.cache_data(show_spinner="Chargement des données...")
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=None, engine="python")
 
    # Garder uniquement les médecins généralistes actifs (NAF 86.21Z)
    df = df[
        (df["activitePrincipaleEtablissement"] == "86.21Z") &
        (df["etatAdministratifEtablissement"] == "A")
    ].copy()
 
    # Nettoyage coordonnées Lambert 93
    for col in ["coordonneeLambertAbscisseEtablissement", "coordonneeLambertOrdonneeEtablissement"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
 
    df = df.dropna(subset=["coordonneeLambertAbscisseEtablissement", "coordonneeLambertOrdonneeEtablissement"])
 
    # Conversion Lambert 93 (EPSG:2154) → WGS84 (EPSG:4326)
    transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    lons, lats = transformer.transform(
        df["coordonneeLambertAbscisseEtablissement"].values,
        df["coordonneeLambertOrdonneeEtablissement"].values,
    )
    df["longitude"] = lons
    df["latitude"] = lats
 
    # Filtrer les coordonnées aberrantes (hors France métropolitaine + DOM-TOM)
    df = df[
        (df["latitude"].between(-25, 52)) &
        (df["longitude"].between(-65, 56))
    ]
 
    # Construire le nom affiché
    def build_name(row):
        prenom = row.get("prenomUsuelUniteLegale", "")
        nom = row.get("nomUniteLegale", "")
        denom = row.get("denominationUniteLegale", "")
        if pd.notna(prenom) and pd.notna(nom) and str(prenom) not in ("[ND]", "nan") and str(nom) not in ("[ND]", "nan"):
            return f"Dr {str(prenom).capitalize()} {str(nom).upper()}"
        elif pd.notna(denom) and str(denom) not in ("[ND]", "nan"):
            return str(denom)
        return "Médecin généraliste"
 
    df["nom_affiche"] = df.apply(build_name, axis=1)
 
    # Adresse
    def build_adresse(row):
        parts = []
        for col in ["numeroVoieEtablissement", "typeVoieEtablissement", "libelleVoieEtablissement"]:
            val = str(row.get(col, ""))
            if val not in ("nan", "[ND]", "None", ""):
                parts.append(val)
        code_postal = str(row.get("codePostalEtablissement", ""))
        commune = str(row.get("libelleCommuneEtablissement", ""))
        if code_postal not in ("nan", "[ND]", "None", ""):
            parts.append(code_postal)
        if commune not in ("nan", "[ND]", "None", ""):
            parts.append(commune)
        return " ".join(parts) if parts else "Adresse non disponible"
 
    df["adresse"] = df.apply(build_adresse, axis=1)
    df["departement"] = df["codePostalEtablissement"].astype(str).str[:2]
 
    return df.reset_index(drop=True)
 
df = load_data(CSV_PATH)
 
# ─── Métriques ────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("Départements", f"{df['codePostalEtablissement'].astype(str).str[:2].nunique()}")
col2.metric("Communes couvertes", f"{df['libelleCommuneEtablissement'].nunique():,}".replace(",", " "))
col3.metric("Total établissements", f"{len(df):,}".replace(",", " "))
 
st.divider()
 
# ─── Référentiel régions → départements ──────────────────────────────────────
regions = {
    "Île-de-France": ["75","77","78","91","92","93","94","95"],
    "Normandie": ["14","27","50","61","76"],
    "Bretagne": ["22","29","35","56"],
    "Grand Est": ["08","10","51","52","54","55","57","67","68","88"],
    "Occitanie": ["09","11","12","30","31","32","34","46","48","65","66","81","82"],
    "Auvergne-Rhône-Alpes": ["01","03","07","15","26","38","42","43","63","69","73","74"],
    "Provence-Alpes-Côte d'Azur": ["04","05","06","13","83","84"],
    "Nouvelle-Aquitaine": ["16","17","19","23","24","33","40","47","64","79","86","87"],
    "Pays de la Loire": ["44","49","53","72","85"],
    "Centre-Val de Loire": ["18","28","36","37","41","45"],
    "Bourgogne-Franche-Comté": ["21","25","39","58","70","71","89","90"],
    "Hauts-de-France": ["02","59","60","62","80"],
    "Corse": ["2A","2B"],
}
 
with st.expander("Filtrer par région et/ou département", expanded=False):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_region = st.selectbox("Région", ["Toutes"] + sorted(regions.keys()))
    with col_f2:
        depts_disponibles = sorted(regions[selected_region]) if selected_region != "Toutes" else sorted(df["departement"].dropna().unique().tolist())
        selected_dept = st.selectbox("Département", ["Tous"] + depts_disponibles)

df_filtered = df.copy()
if selected_region != "Toutes":
    df_filtered = df_filtered[df_filtered["departement"].isin(regions[selected_region])]
if selected_dept != "Tous":
    df_filtered = df_filtered[df_filtered["departement"] == selected_dept]
 
st.caption(f"📍 {len(df_filtered):,} médecins affichés".replace(",", " "))
 
# ─── Carte Folium ─────────────────────────────────────────────────────────────
# Limiter à 5000 points pour les performances si aucun filtre actif
MAX_POINTS = 5000
display_df = df_filtered
if len(df_filtered) > MAX_POINTS:
    st.warning(
        f"⚠️ {len(df_filtered):,} résultats — affichage limité aux {MAX_POINTS} premiers pour les performances. "
        "Utilisez les filtres pour affiner.".replace(",", " ")
    )
    display_df = df_filtered.head(MAX_POINTS)
 
# Centre de la carte
if len(display_df) > 0:
    center_lat = display_df["latitude"].median()
    center_lon = display_df["longitude"].median()
else:
    center_lat, center_lon = 46.603354, 1.888334  # Centre France
 
zoom = 6 if selected_dept == "Tous" else (9 if selected_dept == "Toutes" else 11)
 
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=zoom,
    tiles="CartoDB positron",
)
 
# Ajout des marqueurs avec clustering
from folium.plugins import MarkerCluster
 
cluster = MarkerCluster(
    options={
        "maxClusterRadius": 40,
        "disableClusteringAtZoom": 14,
    }
).add_to(m)
 
for _, row in display_df.iterrows():
    popup_html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 180px;">
        <b style="font-size:14px;">{row['nom_affiche']}</b><br>
        <hr style="margin:4px 0;">
        <span style="color:#555;">📍 {row['adresse']}</span><br>
        <span style="color:#888; font-size:11px;">SIRET : {row['siret']}</span>
    </div>
    """
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=row["nom_affiche"],
        icon=folium.Icon(color="red", icon="plus-sign", prefix="glyphicon"),
    ).add_to(cluster)

# Affichage de la carte
st_folium(m, use_container_width=True, height=600, returned_objects=[])

# ─── Tableau de données ───────────────────────────────────────────────────────
cols_show = ["nom_affiche", "adresse", "libelleCommuneEtablissement", "codePostalEtablissement", "siret"]

st.download_button(
    "⬇️ Télécharger les données filtrées (CSV)",
    data=display_df[cols_show].to_csv(index=False).encode("utf-8"),
    file_name="medecins_generalistes.csv",
    mime="text/csv",
)
