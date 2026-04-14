import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import requests
from pyproj import Transformer
from pathlib import Path
import folium
from streamlit_folium import st_folium
import os

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

st.set_page_config(page_title="PrevSanté", layout="wide")

st.markdown("""
    <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PARAMÈTRES
# ─────────────────────────────────────────────

st.title("PrevSanté - Bilan santé prévention")

REGIONS = {
    1: "Guadeloupe",
    2: "Martinique",
    3: "Guyane",
    4: "La Réunion",
    6: "Mayotte",
    11: "Île-de-France",
    24: "Centre-Val de Loire",
    27: "Bourgogne-Franche-Comté",
    28: "Normandie",
    32: "Hauts-de-France",
    44: "Grand Est",
    52: "Pays de la Loire",
    53: "Bretagne",
    75: "Nouvelle-Aquitaine",
    76: "Occitanie",
    84: "Auvergne-Rhône-Alpes",
    93: "Provence-Alpes-Côte d’Azur",
    94: "Corse",
    99: "France entière"
}

col_params1, col_params2, col_params3 = st.columns([2, 2, 4])

with col_params1:
    annee = st.selectbox("Année", [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023])

with col_params2:
    region_label = st.selectbox(
        "Région",
        options=list(REGIONS.values())
    )

# récupération du code région
region = [k for k, v in REGIONS.items() if v == region_label][0]

file_path = f"data_{region}_{annee}.csv"

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────

@st.cache_data
def load_depenses(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, sep=';')


df = load_depenses(file_path)

if df.empty:
    st.warning(f"Aucune donnée disponible pour {file_path}")
    st.stop()

# ─────────────────────────────────────────────
# SPLIT BLOCS
# ─────────────────────────────────────────────

df_serie = df[df["bloc"] == "serie_temporelle_yoy"]
df_top = df[df["bloc"] == "top_pathologies"]
df_age = df[df["bloc"] == "depenses_par_age"]
df_sexe = df[df["bloc"] == "depenses_par_sexe"]

# ─────────────────────────────────────────────
# KPI
# ─────────────────────────────────────────────

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if not df_serie.empty:
        last = df_serie.sort_values("annee").iloc[-1]

        st.metric(
            label=f"Dépenses {annee}",
            value=f"{int(last['depense_totale']):,} €",
            delta=f"{last['yoy_pct']}%"
        )

# ─────────────────────────────────────────────
# SERIE TEMPORELLE
# ─────────────────────────────────────────────

with col2:
    if not df_serie.empty:
        fig = px.line(
            df_serie,
            x="annee",
            y="depense_totale"
        )

        fig.update_xaxes(showgrid=False, visible=False)
        fig.update_yaxes(showgrid=False, visible=False)

        fig.update_layout(
            height=120,  # clé pour aligner avec le texte
            margin=dict(l=0, r=0, t=10, b=10),
            showlegend=False
        )

        fig.update_traces(
        hovertemplate="<b>Année %{x}</b><br>Dépense %{y:,.0f}€",
        )

        st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False}
        )
    else:
        st.info("Aucune donnée disponible")

col1, col2 = st.columns(2)

# ─────────────────────────────────────────────
# MAP MORTALITE
# ─────────────────────────────────────────────
with col2:
    def format_region_title(label):
        return f"Indice de Mortalité Prématurée ({label})"

    st.markdown(f"**{format_region_title(region_label)}**")
    st.markdown("sur l'année 2023, pour les décès survenus avant 65 ans")

    # état global
    if "selected_region" not in st.session_state:
        st.session_state.selected_region = None

    @st.cache_data
    def load_mortalite():
        df = pd.read_csv("./datasets/Taux_de_mortalite.csv", sep=",", encoding="utf-8")
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

    df = load_mortalite()

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

    if region_label == "France entière":
        st.session_state.selected_region = None
    else:
        st.session_state.selected_region = region_label

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
            title=None,
        )

        fig.update_geos(fitbounds="locations", visible=False)

        st.plotly_chart(fig, width="stretch")

    else:
        region = st.session_state.selected_region

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

# ─────────────────────────────────────────────
# BILAN
# ─────────────────────────────────────────────

with col1:
    # st.set_page_config(page_title="Priorités de prévention", layout="centered")

    priorities = [
        {"num": "01", "title": "Dépistage Cancer du Côlon",          "target": "Hommes/Femmes 50–74 ans",         "active": True},
        {"num": "02", "title": "Vaccination Grippe/Covid",            "target": "Personnes 65+ ans & fragiles",    "active": False},
        {"num": "03", "title": "Suivi HTA & Risque Cardiovasculaire", "target": "Patients ALD 45+ ans",            "active": False},
        {"num": "04", "title": "Bilan de Santé Jeunes",               "target": "Étudiants & précaires 18–25 ans", "active": False},
    ]

    items_html = ""
    for i, p in enumerate(priorities):
        badge_bg    = "#4f46e5" if p["active"] else "#2d3748"
        badge_color = "#ffffff" if p["active"] else "#a0aec0"
        border_top  = "border-top:1px solid #2d3748;" if i > 0 else ""

        items_html += f"""
        <div style="display:flex;align-items:center;gap:16px;padding:16px 0;{border_top}">
        <div style="min-width:44px;height:44px;border-radius:8px;
                    background:{badge_bg};color:{badge_color};
                    display:flex;align-items:center;justify-content:center;
                    font-size:14px;font-weight:700;letter-spacing:0.5px;flex-shrink:0;">
            {p['num']}
        </div>
        <div>
            <div style="color:#f0f4f8;font-size:16px;font-weight:600;margin-bottom:2px;">
            {p['title']}
            </div>
            <div style="color:#8899aa;font-size:13px;">
            Cible : {p['target']}
            </div>
        </div>
        </div>"""

    html = f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: transparent; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    </style>
    </head>
    <body>
    <div style="background:#141c2b;border-radius:16px;padding:24px 28px;">

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
        <div style="display:flex;align-items:center;gap:10px;">
        <span style="color:#4f46e5;font-size:22px;font-weight:900;line-height:1;">!</span>
        <span style="color:#f0f4f8;font-size:18px;font-weight:700;">Priorités de prévention 2024</span>
        </div>
        <div style="background:#1e2a3a;color:#a0b4c8;font-size:12px;font-weight:600;
                    letter-spacing:1px;padding:5px 12px;border-radius:8px;
                    border:1px solid #2d3d50;white-space:nowrap;">TOP 5</div>
    </div>

    {items_html}

    </div>
    </body>
    </html>"""

    components.html(html, height=370)

# ─────────────────────────────────────────────
# TOP PATHOLOGIES
# ─────────────────────────────────────────────
with col1:
    st.markdown("**Top 5 des groupes de pathologies les plus coûteux**")

    if not df_top.empty:
        top = df_top.sort_values("depense", ascending=True)

        fig = px.bar(
            top,
            x="depense",
            y="patho",
            orientation="h",
            text="patho",
            color="depense",
            color_continuous_scale="teal"
        )

        fig.update_layout(
            coloraxis_showscale=False,
            showlegend=False,
            height=300,
            margin=dict(l=0, r=0, t=10, b=10),
        )

        fig.update_traces(
            hovertemplate="<b>%{y}</b><br>Dépense : %{x}€",
            textposition="inside",
            insidetextanchor="start",
            marker=dict(cornerradius=10)
        )

        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)

        st.plotly_chart(
            fig,
            width="stretch",
            config={"displayModeBar": False}
        )


# ─────────────────────────────────────────────
# AGE
# ─────────────────────────────────────────────

with col2:
    st.markdown("**Dépenses par âge**")

    if not df_age.empty:
        options = ["Total"] + list(df_age["patho"].unique())

        selected = st.selectbox("Pathologie", options)

        df_age_work = df_age.copy()

        if selected != "Total":
            df_age_work = df_age_work[df_age_work["patho"] == selected]

        df_age_grouped = df_age_work.groupby("age", as_index=False)["depense"].sum()

        fig = px.pie(
            df_age_grouped,
            names="age",
            values="depense",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Teal
        )

        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=10, r=10, t=40, b=40)
        )

        st.plotly_chart(
            fig,
            width="stretch",
            config={"displayModeBar": False}
        )


# ─────────────────────────────────────────────
# SEXE
# ─────────────────────────────────────────────

st.markdown("**Dépenses par sexe**")

def smart_wrap(text, width=12):
    words = text.split()
    lines = []
    line = ""

    for w in words:
        if len(line + " " + w) <= width:
            line += " " + w
        else:
            lines.append(line.strip())
            line = w

    lines.append(line.strip())
    return "<br>".join(lines)

df_sexe["patho_wrapped"] = df_sexe["patho"].apply(
    lambda x: smart_wrap(x, 12)
)

if not df_sexe.empty:
    fig = px.bar(
        df_sexe,
        x="patho_wrapped",
        y="depense",
        color="sexe",
        barmode="group",
        color_discrete_sequence=px.colors.sequential.Teal
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        tickangle=0,
    )

    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        visible=False
    )

    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        legend_title_text=None,
         showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.15,
            xanchor="center",
            x=0.5
        ),
        yaxis_tickformat=",.0f",
        margin=dict(l=20, r=20, t=40, b=20),
    )

    fig.update_traces(
        marker=dict(cornerradius=10),
        hovertemplate=
            "%{fullData.name}<br>" +
            "Dépense : %{y:,.0f} €" +
            "<extra></extra>"
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False}
    )

# ─────────────────────────────────────────────
# MAP MEDECINS GENERALISTES
# ─────────────────────────────────────────────
col1, col2 = st.columns(2, vertical_alignment="center")

with col1:
    st.markdown("**Localisation des médecins généralistes**")

    # ─── Chargement des données ─────────────────────────────────────
    BASE_DIR = Path(__file__).resolve().parent.parent
    CSV_PATH = BASE_DIR / "datasets" / "annuaire-des-entreprises-etablissements.csv"

    @st.cache_data(show_spinner="Chargement des données...")
    def load_medecins(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, sep=None, engine="python")

        df = df[
            (df["activitePrincipaleEtablissement"] == "86.21Z") &
            (df["etatAdministratifEtablissement"] == "A")
        ].copy()

        for col in [
            "coordonneeLambertAbscisseEtablissement",
            "coordonneeLambertOrdonneeEtablissement"
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=[
            "coordonneeLambertAbscisseEtablissement",
            "coordonneeLambertOrdonneeEtablissement"
        ])

        transformer = Transformer.from_crs(
            "EPSG:2154", "EPSG:4326", always_xy=True
        )
        lons, lats = transformer.transform(
            df["coordonneeLambertAbscisseEtablissement"].values,
            df["coordonneeLambertOrdonneeEtablissement"].values,
        )
        df["longitude"] = lons
        df["latitude"] = lats

        df = df[
            df["latitude"].between(-25, 52) &
            df["longitude"].between(-65, 56)
        ]

        def build_name(row):
            prenom = row.get("prenomUsuelUniteLegale", "")
            nom = row.get("nomUniteLegale", "")
            denom = row.get("denominationUniteLegale", "")
            if pd.notna(prenom) and pd.notna(nom) and str(prenom) not in ("[ND]", "nan"):
                return f"Dr {str(prenom).capitalize()} {str(nom).upper()}"
            if pd.notna(denom) and str(denom) not in ("[ND]", "nan"):
                return str(denom)
            return "Médecin généraliste"

        df["nom_affiche"] = df.apply(build_name, axis=1)

        def build_adresse(row):
            parts = []
            for col in [
                "numeroVoieEtablissement",
                "typeVoieEtablissement",
                "libelleVoieEtablissement"
            ]:
                val = str(row.get(col, ""))
                if val not in ("nan", "[ND]", ""):
                    parts.append(val)
            if pd.notna(row.get("codePostalEtablissement")):
                parts.append(str(row["codePostalEtablissement"]))
            if pd.notna(row.get("libelleCommuneEtablissement")):
                parts.append(str(row["libelleCommuneEtablissement"]))
            return " ".join(parts)

        df["adresse"] = df.apply(build_adresse, axis=1)
        df["departement"] = df["codePostalEtablissement"].astype(str).str[:2]

        return df.reset_index(drop=True)

    df = load_medecins(CSV_PATH)

    # ─── Référentiel régions → départements ──────────────────────────
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

    # ─── Reset département si la région change ───────────────────────
    if "prev_region" not in st.session_state:
        st.session_state.prev_region = region_label

    if region_label != st.session_state.prev_region:
        st.session_state.dept_filter = "Tous"
        st.session_state.prev_region = region_label

    # ─── Filtre région (base) ────────────────────────────────────────
    if region_label == "France entière":
        df_region = df.copy()
    else:
        df_region = df[df["departement"].isin(regions.get(region_label, []))]

    # ─── Sélecteur département (logique AVANT carte) ─────────────────
    if "dept_filter" not in st.session_state:
        st.session_state.dept_filter = "Tous"

    with st.expander("Affiner par département", expanded=False):
        deps = sorted(df_region["departement"].dropna().unique())
        selected_dept = st.selectbox(
            "Département",
            ["Tous"] + deps,
            key="dept_filter"
        )

    # ─── Filtre final ────────────────────────────────────────────────
    if selected_dept == "Tous":
        df_filtered = df_region
    else:
        df_filtered = df_region[df_region["departement"] == selected_dept]

    st.caption(f"📍 {len(df_filtered):,} médecins affichés".replace(",", " "))

    # ─── Carte Folium ────────────────────────────────────────────────
    MAX_POINTS = 5000
    display_df = (
        df_filtered.head(MAX_POINTS)
        if len(df_filtered) > MAX_POINTS
        else df_filtered
    )

    if not display_df.empty:
        center_lat = display_df["latitude"].median()
        center_lon = display_df["longitude"].median()
    else:
        center_lat, center_lon = 46.603354, 1.888334

    lat_range = display_df["latitude"].max() - display_df["latitude"].min()
    lon_range = display_df["longitude"].max() - display_df["longitude"].min()
    extent = max(lat_range, lon_range)

    if extent > 10:
        zoom = 5
    elif extent > 5:
        zoom = 6
    elif extent > 2:
        zoom = 7
    elif extent > 1:
        zoom = 8
    else:
        zoom = 10

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
    )

    from folium.plugins import MarkerCluster
    cluster = MarkerCluster(
        options={
            "maxClusterRadius": 40,
            "disableClusteringAtZoom": 14,
        }
    ).add_to(m)

    for _, row in display_df.iterrows():
        folium.Marker(
            [row["latitude"], row["longitude"]],
            tooltip=row["nom_affiche"],
            popup=folium.Popup(
                f"""
                <b>{row['nom_affiche']}</b><br>
                📍 {row['adresse']}<br>
                <small>SIRET : {row['siret']}</small>
                """,
                max_width=260
            ),
            icon=folium.Icon(
                color="red",
                icon="plus-sign",
                prefix="glyphicon"
            ),
        ).add_to(cluster)

    st_folium(m, use_container_width=True, height=600)

    # ─── Export CSV ────────────────────────────────────────────────
    cols_export = [
        "nom_affiche",
        "adresse",
        "libelleCommuneEtablissement",
        "codePostalEtablissement",
        "siret"
    ]

    st.download_button(
        "⬇️ Télécharger les données filtrées (CSV)",
        df_filtered[cols_export]
        .to_csv(index=False)
        .encode("utf-8"),
        file_name="medecins_generalistes.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────
# RÉSEAU PARTENAIRES
# ─────────────────────────────────────────────

with col2:
    partenaires = [
        {"icon": "🏢", "nom": "CPAM Lille-Douai",       "desc": "Accompagnement ALD"},
        {"icon": "🏥", "nom": "CHU Amiens-Picardie",     "desc": "Plateau de dépistage"},
        {"icon": "👥", "nom": "Association Préva",        "desc": "Actions de terrain"},
        {"icon": "💊", "nom": "Réseau Pharmacies 59",     "desc": "Dépistage de proximité"},
    ]

    items_html = ""
    for p in partenaires:
        items_html += f"""
        <div style="background:#f8f9fb;border-radius:12px;padding:32px 20px;
                    display:flex;flex-direction:column;align-items:center;justify-content:center;
                    text-align:center;gap:12px;">
        <div style="width:56px;height:56px;border-radius:50%;background:#e8eaed;
                    display:flex;align-items:center;justify-content:center;font-size:22px;">
            {p['icon']}
        </div>
        <div style="font-size:15px;font-weight:700;color:#1a1a2e;">{p['nom']}</div>
        <div style="font-size:13px;color:#6b7280;">{p['desc']}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <style>
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:transparent; }}
    </style>
    </head><body>
    <div style="background:#ffffff;border-radius:16px;padding:28px 32px;
                border:1px solid #e5e7eb;">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:24px;">
        <div>
        <div style="font-size:16px;font-weight:700;color:#1a1a2e;">
            Réseau de partenaires de prévention
        </div>
        <div style="font-size:13px;color:#6b7280;margin-top:4px;">
            Organismes locaux certifiés
        </div>
        </div>
        <a style="font-size:13px;font-weight:600;color:#4f46e5;
                        text-decoration:none;white-space:nowrap;margin-top:4px;">
        Voir tout l'annuaire →
        </a>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        {items_html}
    </div>
    </div>
    </body></html>"""

    components.html(html, height=700)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────

st.markdown("---")
st.caption("PREVSANTE - PLATEFORME DE PILOTAGE SANITAIRE - 2026")
