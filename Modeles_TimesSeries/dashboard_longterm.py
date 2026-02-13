"""
Dashboard interactif pour visualiser les prédictions long terme (3 ans) et comparer avec l'historique.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
from dashboard_budget_extension import section_budget_simulator
from budget_helper import charger_prix_spot

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from data_loader import get_data_loader

# Configuration de la page
st.set_page_config(
    page_title="Dashboard Prédictions Énergétiques",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    h1 {
        color: #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialiser le DataLoader
@st.cache_resource
def get_loader():
    """Charge et cache le DataLoader."""
    return get_data_loader('csv', 'config/config.yaml')

# Charger les sites disponibles
@st.cache_data
def load_sites_info():
    """Charge la table des sites avec leurs informations."""
    loader = get_loader()
    sites_df = loader.load_sites_table()
    return sites_df

# Charger tous les sites et leurs données
@st.cache_data
def load_all_sites_data():
    """Charge les prédictions et historiques de tous les sites disponibles"""
    predictions_dir = Path("data/predictions")
    processed_dir = Path("data/processed")

    if not predictions_dir.exists():
        return None, None

    csv_files = list(predictions_dir.glob("predictions_longterm_*.csv"))
    if not csv_files:
        return None, None

    all_predictions = []
    all_historiques = []
    site_info_list = []

    import re
    for pred_file in csv_files:
        # Extraire le PRM
        prm_match = re.search(r'_(\d{14})\.csv$', pred_file.name)
        if not prm_match:
            continue
        prm = prm_match.group(1)

        # Charger prédictions
        try:
            df_pred = pd.read_csv(pred_file)
            df_pred['datetime'] = pd.to_datetime(df_pred['datetime'])
            df_pred['prm'] = prm
            df_pred['type_donnee'] = 'Prédiction'
            all_predictions.append(df_pred)
        except:
            continue

        # Charger historique correspondant
        hist_file = processed_dir / f"data_preprocessed_{prm}.csv"
        if hist_file.exists():
            try:
                df_hist = pd.read_csv(hist_file)
                df_hist['datetime'] = pd.to_datetime(df_hist['datetime'])
                df_hist['prm'] = prm
                df_hist['type_donnee'] = 'Historique'
                all_historiques.append(df_hist)
            except:
                pass

        site_info_list.append(prm)

    df_all_pred = pd.concat(all_predictions, ignore_index=True) if all_predictions else None
    df_all_hist = pd.concat(all_historiques, ignore_index=True) if all_historiques else None

    return df_all_pred, df_all_hist

# Charger toutes les données
df_all_predictions, df_all_historique = load_all_sites_data()

if df_all_predictions is None:
    st.error("Aucun fichier de prédictions trouvé dans data/predictions/")
    st.info("Générez d'abord les prédictions :")
    st.code("python main.py predict-longterm --prm 30000540191777 --years 3")
    st.info("Ou pour tous les sites :")
    st.code("python generate_all_predictions.py")
    st.stop()

# Récupérer la liste des sites
available_prms = sorted(df_all_predictions['prm'].unique().tolist())
sites_df = load_sites_info()

# Créer mapping PRM -> Ville
prm_to_city = {}
if not sites_df.empty:
    for _, row in sites_df.iterrows():
        prm_to_city[str(row['prm'])] = row['ville']

# Sidebar pour sélectionner le site
st.sidebar.header("⚙️ Configuration")
st.sidebar.markdown("### 🏢 Sélection du périmètre")

# Option "Tous les sites" + sites individuels
site_options = ["🏢 Tous les sites (Vue Entreprise)"]
for prm in available_prms:
    ville = prm_to_city.get(prm, f"Site {prm}")
    site_options.append(f"{ville} (PRM: {prm})")

selected_display = st.sidebar.selectbox(
    "Périmètre d'analyse",
    options=site_options,
    index=0
)

# Déterminer le mode (tous sites ou site spécifique)
if selected_display.startswith("🏢 Tous les sites"):
    selected_prm = None
    st.title("🏢 Dashboard Entreprise - Vue Consolidée")
    st.markdown("**Analyse des consommations de tous les sites**")
else:
    selected_prm = selected_display.split("PRM: ")[1].rstrip(")")
    ville = prm_to_city.get(selected_prm, f"Site {selected_prm}")
    st.title(f"📊 Dashboard - {ville}")
    st.markdown(f"**PRM:** {selected_prm}")

st.markdown("---")

# Fonction de chargement des données
@st.cache_data
def load_predictions(filepath):
    """Charge les prédictions depuis un fichier CSV"""
    try:
        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Ajouter des colonnes utiles si elles n'existent pas
        if 'annee' not in df.columns:
            df['annee'] = df['datetime'].dt.year
        if 'mois' not in df.columns:
            df['mois'] = df['datetime'].dt.month
        if 'jour_semaine' not in df.columns:
            df['jour_semaine'] = df['datetime'].dt.dayofweek
        if 'heure' not in df.columns:
            df['heure'] = df['datetime'].dt.hour

        # Ajouter une colonne type de données
        df['type_donnee'] = 'Prédiction'

        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        return None

@st.cache_data
def load_historique(filepath):
    """Charge les données historiques depuis un fichier CSV"""
    try:
        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Renommer la colonne de puissance pour uniformiser
        if 'puissance_moy_heure' in df.columns:
            df['puissance_kw_pred'] = df['puissance_moy_heure']
        elif 'puissance' in df.columns:
            df['puissance_kw_pred'] = df['puissance']

        # IMPORTANT : Convertir de W en kW (les données historiques sont en Watt)
        # Les prédictions sont déjà en kW, il faut donc uniformiser
        df['puissance_kw_pred'] = df['puissance_kw_pred'] / 1000

        # Ajouter des colonnes utiles
        df['annee'] = df['datetime'].dt.year
        df['mois'] = df['datetime'].dt.month
        df['jour_semaine'] = df['datetime'].dt.dayofweek
        df['heure'] = df['datetime'].dt.hour
        df['type_donnee'] = 'Historique'

        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'historique : {e}")
        return None

@st.cache_data
def load_model_metrics(prm=None):
    """Charge les métriques du modèle depuis le fichier config sauvegardé"""
    try:
        if prm:
            # Charger les métriques pour un site spécifique
            config_path = Path(f"models/saved/config_latest_lstm_energy_forecast_{prm}.json")
        else:
            # Mode consolidé : charger les métriques du premier site disponible
            config_files = list(Path("models/saved").glob("config_latest_lstm_energy_forecast_*.json"))
            if config_files:
                config_path = config_files[0]
            else:
                return None

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Erreur lors du chargement des métriques : {e}")
        return None

# Fonction de chargement des prix
@st.cache_data
def load_prix_spot(filepath):
    """Charge les prix spot depuis un fichier CSV"""
    try:
        df_prix = charger_prix_spot(filepath)
        return df_prix
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Erreur lors du chargement des prix : {e}")
        return None


# Filtrer les données selon le périmètre sélectionné
if selected_prm:
    # Site spécifique
    df_predictions = df_all_predictions[df_all_predictions['prm'] == selected_prm].copy()
    historique = df_all_historique[df_all_historique['prm'] == selected_prm].copy() if df_all_historique is not None else None
else:
    # Tous les sites - Agréger les consommations
    # Identifier la colonne de consommation (puissance_kw_pred pour prédictions, puissance_moy_heure pour historique)
    df_predictions = df_all_predictions.groupby('datetime').agg({
        'puissance_kw_pred': 'sum'
    }).reset_index()
    df_predictions['type_donnee'] = 'Prédiction'

    if df_all_historique is not None:
        historique = df_all_historique.groupby('datetime').agg({
            'puissance_moy_heure': 'sum'
        }).reset_index()
        # Renommer pour uniformiser
        historique.rename(columns={'puissance_moy_heure': 'puissance_kw_pred'}, inplace=True)
        historique['type_donnee'] = 'Historique'
    else:
        historique = None

# Uniformiser les noms de colonnes
if 'puissance_moy_heure' in df_predictions.columns and 'puissance_kw_pred' not in df_predictions.columns:
    df_predictions.rename(columns={'puissance_moy_heure': 'puissance_kw_pred'}, inplace=True)

if historique is not None:
    if 'puissance_moy_heure' in historique.columns and 'puissance_kw_pred' not in historique.columns:
        historique.rename(columns={'puissance_moy_heure': 'puissance_kw_pred'}, inplace=True)

# Créer une colonne unifiée 'conso_reelle_kw' pour la compatibilité
df_predictions['conso_reelle_kw'] = df_predictions['puissance_kw_pred']
if historique is not None:
    historique['conso_reelle_kw'] = historique['puissance_kw_pred']

# Ajouter les colonnes temporelles
for df in [df_predictions, historique]:
    if df is not None and len(df) > 0:
        if 'annee' not in df.columns:
            df['annee'] = df['datetime'].dt.year
        if 'mois' not in df.columns:
            df['mois'] = df['datetime'].dt.month
        if 'jour_semaine' not in df.columns:
            df['jour_semaine'] = df['datetime'].dt.dayofweek
        if 'heure' not in df.columns:
            df['heure'] = df['datetime'].dt.hour

if df_predictions is None or len(df_predictions) == 0:
    st.error("Impossible de charger les données ou fichier vide")
    st.stop()

# Afficher infos de chargement dans sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Données chargées")
if selected_prm:
    st.sidebar.info(f"📈 **{len(df_predictions):,}** points de prédiction")
    if historique is not None:
        st.sidebar.info(f"📚 **{len(historique):,}** points historiques")
else:
    nb_sites = len(available_prms)
    st.sidebar.success(f"🏢 **{nb_sites}** sites consolidés")
    st.sidebar.info(f"📈 **{len(df_predictions):,}** points de prédiction")
    if historique is not None:
        st.sidebar.info(f"📚 **{len(historique):,}** points historiques")


# Interface dans la sidebar - Module Budgétaire toujours actif
st.sidebar.markdown("---")
st.sidebar.markdown("### 💰 Module Budgétaire")

# Charger automatiquement les prix spot
prix_file = "data/raw/prix/prix_spot.csv"
prix_spot = None

if Path(prix_file).exists():
    prix_spot = load_prix_spot(prix_file)
    if prix_spot is not None and isinstance(prix_spot, pd.DataFrame):
        st.sidebar.success(f"✅ {len(prix_spot)} périodes de prix chargées")
    else:
        st.sidebar.error(f"⚠️ Erreur: prix_spot n'est pas un DataFrame (type={type(prix_spot)})")
        prix_spot = None
else:
    st.sidebar.warning(f"⚠️ Fichier prix spot introuvable : {prix_file}")
    st.sidebar.info("Le module budgétaire sera désactivé sans fichier de prix")

# Configuration volumes et prix (toujours affichés)
st.sidebar.markdown("#### 📦 Volumes achetés")
col1, col2 = st.sidebar.columns(2)
with col1:
    st.markdown("**Base**")
    volume_base = st.number_input("kW", value=250.0, step=10.0, key="vb")
    prix_base = st.number_input("€/MWh", value=42.0, step=1.0, key="pb")

with col2:
    st.markdown("**Peak**")
    volume_peak = st.number_input("kW", value=100.0, step=10.0, key="vp")
    prix_peak = st.number_input("€/MWh", value=55.0, step=1.0, key="pp")

st.sidebar.info("Peak = 8h-20h semaine")

turpe = st.sidebar.number_input("TURPE (€/kWh)", value=0.05, step=0.001, format="%.3f")
taxes = st.sidebar.number_input("Taxes (%)", value=20.0, step=1.0)

# Fusionner historique et prédictions si disponible
if historique is not None:
    # Garder seulement les colonnes communes
    cols_communes = ['datetime', 'puissance_kw_pred', 'annee', 'mois', 'jour_semaine', 'heure', 'type_donnee']
    df_all = pd.concat([
        historique[cols_communes],
        df_predictions[cols_communes]
    ], ignore_index=True).sort_values('datetime')
else:
    df_all = df_predictions.copy()

# Charger les métriques du modèle (avec PRM si site spécifique)
model_metrics = load_model_metrics(prm=selected_prm)

# Informations générales
st.sidebar.markdown("---")
st.sidebar.markdown("### Statistiques générales")

# Stats prédictions
st.sidebar.markdown("**Prédictions**")
st.sidebar.metric("Période", f"{df_predictions['datetime'].min().strftime('%Y-%m-%d')} → {df_predictions['datetime'].max().strftime('%Y-%m-%d')}")
st.sidebar.metric("Nombre d'heures", f"{len(df_predictions):,}")
st.sidebar.metric("Nombre de jours", f"{len(df_predictions)//24:,}")

# Stats historique si disponible
if historique is not None:
    st.sidebar.markdown("**Historique**")
    st.sidebar.metric("Période", f"{historique['datetime'].min().strftime('%Y-%m-%d')} → {historique['datetime'].max().strftime('%Y-%m-%d')}")
    st.sidebar.metric("Nombre d'heures", f"{len(historique):,}")

# Stats globales
st.sidebar.markdown("**Global**")
st.sidebar.metric("Années couvertes", f"{df_all['annee'].nunique()}")
# Filtres
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filtres")

annees_disponibles = sorted(df_all['annee'].unique())
annees_selectionnees = st.sidebar.multiselect(
    "Années à afficher",
    annees_disponibles,
    default=annees_disponibles
)

if not annees_selectionnees:
    st.warning("Sélectionnez au moins une année")
    st.stop()

# Filtrer les données
df_filtered = df_all[df_all['annee'].isin(annees_selectionnees)].copy()

st.markdown("---")

# ============================================================================
# PARTIE 1 : ÉVOLUTION TEMPORELLE
# ============================================================================
st.header("Évolution Temporelle de la Consommation")

st.markdown("""
Ce graphique montre l'évolution de la consommation dans le temps.
La ligne verticale sépare les **données historiques** (à gauche) des **prédictions** (à droite).
""")

# Créer le graphique d'évolution
fig_evolution = go.Figure()

# Ajouter les données historiques
if historique is not None:
    hist_data = df_filtered[df_filtered['type_donnee'] == 'Historique']
    if len(hist_data) > 0:
        fig_evolution.add_trace(go.Scatter(
            x=hist_data['datetime'],
            y=hist_data['puissance_kw_pred'],
            mode='lines',
            name='Historique',
            line=dict(color='#2ca02c', width=2),
            hovertemplate='%{x|%d/%m/%Y %Hh}<br>Puissance: %{y:.1f} kW<extra></extra>'
        ))

        # Ligne verticale à la fin de l'historique
        date_limite = hist_data['datetime'].max()

        # Utiliser add_shape pour la ligne verticale
        fig_evolution.add_shape(
            type="line",
            x0=date_limite,
            x1=date_limite,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="red", width=2, dash="dash")
        )

        # Ajouter une annotation
        fig_evolution.add_annotation(
            x=date_limite,
            y=1,
            yref="paper",
            text="Fin de l'historique",
            showarrow=True,
            arrowhead=2,
            arrowcolor="red",
            ax=0,
            ay=-30,
            bordercolor="red"
        )

# Ajouter les prédictions
pred_data = df_filtered[df_filtered['type_donnee'] == 'Prédiction']
if len(pred_data) > 0:
    fig_evolution.add_trace(go.Scatter(
        x=pred_data['datetime'],
        y=pred_data['puissance_kw_pred'],
        mode='lines',
        name='Prédictions',
        line=dict(color='#ff7f0e', width=2, dash='dot'),
        hovertemplate='%{x|%d/%m/%Y %Hh}<br>Puissance: %{y:.1f} kW<extra></extra>'
    ))

fig_evolution.update_layout(
    title="Évolution temporelle de la consommation",
    xaxis_title="Date",
    yaxis_title="Puissance (kW)",
    height=500,
    hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig_evolution, use_container_width=True)

st.markdown("---")

# ============================================================================
# PARTIE 2 : ANALYSES STATISTIQUES
# ============================================================================
st.header("Analyses Statistiques")

st.markdown("""
Cette section présente des analyses statistiques détaillées avec différentes granularités temporelles.
""")

# Onglets pour les différentes analyses
tab_annuel, tab_mensuel, tab_detaille = st.tabs(["📊 Annuel", "📆 Mensuel", "📋 Détaillé"])

with tab_annuel:
    st.subheader("Analyse annuelle")

    # Filtre par année
    col1, col2 = st.columns([3, 1])
    with col1:
        annee_filtre = st.multiselect(
            "Sélectionner les années à afficher",
            sorted(df_filtered['annee'].unique()),
            default=sorted(df_filtered['annee'].unique())
        )

    if annee_filtre:
        df_annuel_filtre = df_filtered[df_filtered['annee'].isin(annee_filtre)]

        # Calculer les moyennes annuelles
        annual_avg = df_annuel_filtre.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

        # Pivoter pour avoir historique et prédiction côte à côte
        annual_pivot = annual_avg.pivot_table(index='annee', columns='type_donnee', values='puissance_kw_pred').reset_index()

        # Créer une colonne combinée en moyennant les deux types si les deux existent
        if 'Historique' in annual_pivot.columns and 'Prédiction' in annual_pivot.columns:
            annual_pivot['moyenne'] = annual_pivot[['Historique', 'Prédiction']].mean(axis=1, skipna=True)
        elif 'Historique' in annual_pivot.columns:
            annual_pivot['moyenne'] = annual_pivot['Historique']
        else:
            annual_pivot['moyenne'] = annual_pivot['Prédiction']

        # Déterminer la couleur pour chaque année
        def get_year_color(row):
            if 'Historique' in annual_pivot.columns and 'Prédiction' in annual_pivot.columns:
                has_hist = pd.notna(row.get('Historique'))
                has_pred = pd.notna(row.get('Prédiction'))
                if has_hist and has_pred:
                    return '#F2C94C'  # Jaune pour mixte
                elif has_hist:
                    return '#2ca02c'  # Vert pour historique
                else:
                    return '#ff7f0e'  # Orange pour prédiction
            elif 'Historique' in annual_pivot.columns:
                return '#2ca02c'
            else:
                return '#ff7f0e'

        annual_pivot['couleur'] = annual_pivot.apply(get_year_color, axis=1)

        # Créer le graphique en barres
        fig_annuel = go.Figure()

        for idx, row in annual_pivot.iterrows():
            fig_annuel.add_trace(go.Bar(
                x=[str(int(row['annee']))],
                y=[row['moyenne']],
                marker_color=row['couleur'],
                text=[f"{row['moyenne']:.1f} kW"],
                textposition='outside',
                name=str(int(row['annee'])),
                showlegend=False,
                hovertemplate=f"Année {int(row['annee'])}<br>Moyenne: {row['moyenne']:.1f} kW<extra></extra>"
            ))

        # Ajouter une légende personnalisée
        fig_annuel.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color='#2ca02c',
            showlegend=True,
            name='Année historique'
        ))

        fig_annuel.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color='#ff7f0e',
            showlegend=True,
            name='Année prédite'
        ))

        fig_annuel.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color='#F2C94C',
            showlegend=True,
            name='Année mixte'
        ))

        fig_annuel.update_layout(
            title="Consommation moyenne annuelle",
            xaxis_title="Année",
            yaxis_title="Puissance moyenne (kW)",
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(255, 255, 255, 0)"
            )
        )

        st.plotly_chart(fig_annuel, use_container_width=True)


with tab_mensuel:
    st.subheader("Analyse mensuelle")

    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        annees_mensuel = st.multiselect(
            "Sélectionner les années",
            sorted(df_filtered['annee'].unique()),
            default=sorted(df_filtered['annee'].unique()),
            key='annees_mensuel'
        )
    with col2:
        mois_filtre = st.multiselect(
            "Sélectionner les mois",
            list(range(1, 13)),
            default=list(range(1, 13)),
            format_func=lambda x: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'][x-1]
        )

    if annees_mensuel and mois_filtre:
        df_mensuel_filtre = df_filtered[(df_filtered['annee'].isin(annees_mensuel)) & (df_filtered['mois'].isin(mois_filtre))]

        # Calculer les moyennes mensuelles par année et type de donnée
        monthly_avg = df_mensuel_filtre.groupby(['annee', 'mois', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

        # Labels des mois
        mois_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

        # Créer le graphique
        fig_mensuel = go.Figure()

        # Couleurs pour différentes années
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

        # Tracer pour chaque année
        for idx, annee in enumerate(sorted(annees_mensuel)):
            for type_data in ['Historique', 'Prédiction']:
                data = monthly_avg[(monthly_avg['annee'] == annee) & (monthly_avg['type_donnee'] == type_data)]
                if len(data) > 0:
                    data = data.sort_values('mois')
                    color = colors[idx % len(colors)]
                    dash = 'solid' if type_data == 'Historique' else 'dot'

                    fig_mensuel.add_trace(go.Scatter(
                        x=[mois_labels[m-1] for m in data['mois']],
                        y=data['puissance_kw_pred'],
                        mode='lines+markers',
                        name=f'{annee} ({type_data})',
                        line=dict(color=color, width=2.5, dash=dash),
                        marker=dict(size=7),
                        hovertemplate=f'Année {annee}<br>Mois: %{{x}}<br>Moyenne: %{{y:.1f}} kW<extra></extra>'
                    ))

        annees_str = ', '.join([str(int(a)) for a in sorted(annees_mensuel)])
        fig_mensuel.update_layout(
            title=f"Consommation moyenne mensuelle - Années {annees_str}",
            xaxis_title="Mois",
            yaxis_title="Puissance moyenne (kW)",
            height=500,
            hovermode='x unified',
            xaxis=dict(categoryorder='array', categoryarray=mois_labels)
        )

        st.plotly_chart(fig_mensuel, use_container_width=True)

with tab_detaille:
    st.subheader("Tableau des statistiques détaillées")

    # Calculer les statistiques par année et type de donnée
    stats_annee = df_filtered.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].agg([
        ('Moyenne (kW)', 'mean'),
        ('Maximum (kW)', 'max'),
        ('Minimum (kW)', 'min'),
        ('Écart-type (kW)', 'std'),
        ('Énergie totale (MWh)', lambda x: x.sum() / 1000)
    ]).round(2).reset_index()

    # Fusionner les données : pour chaque année, faire la moyenne entre historique et prédiction si les deux existent
    stats_merged = {}
    for annee in sorted(stats_annee['annee'].unique()):
        stats_merged[str(int(annee))] = {}
        data_annee = stats_annee[stats_annee['annee'] == annee]

        for stat in ['Moyenne (kW)', 'Maximum (kW)', 'Minimum (kW)', 'Écart-type (kW)', 'Énergie totale (MWh)']:
            # Récupérer les valeurs pour historique et prédiction
            valeurs = data_annee[stat].values

            if len(valeurs) > 0:
                # Si on a plusieurs valeurs (historique ET prédiction), on fait la moyenne
                stats_merged[str(int(annee))][stat] = round(valeurs.mean(), 2)

    # Créer le DataFrame final avec statistiques en lignes et années en colonnes
    stats_restructured = []
    for stat in ['Moyenne (kW)', 'Maximum (kW)', 'Minimum (kW)', 'Écart-type (kW)', 'Énergie totale (MWh)']:
        row_data = {'Statistique': stat}
        for annee in sorted(stats_annee['annee'].unique()):
            annee_str = str(int(annee))
            if annee_str in stats_merged and stat in stats_merged[annee_str]:
                row_data[annee_str] = stats_merged[annee_str][stat]
            else:
                row_data[annee_str] = None
        stats_restructured.append(row_data)

    df_stats_display = pd.DataFrame(stats_restructured)

    st.dataframe(df_stats_display.set_index('Statistique'), use_container_width=True)

    st.info("💡 Ce tableau présente les statistiques moyennées par année. Quand une année contient à la fois des données historiques et prédites, la moyenne des deux est affichée.")
# ============================================================================
# PARTIE 3 : COMPARAISON DES PROFILS
# ============================================================================
st.header("Comparaison des Profils de Consommation")

st.markdown("""
Cette section permet de comparer les profils de consommation à différentes échelles temporelles.
""")

# Tabs pour différentes granularités - ORDRE CORRECT
tab_annuel, tab_mensuel, tab_hebdo, tab_horaire = st.tabs(["📊 Annuel", "📆 Mensuel", "📅 Hebdomadaire", "⏱️ Horaire"])

with tab_annuel:
    st.subheader("Comparaison annuelle")

    # Calculer les moyennes annuelles
    annual_avg = df_filtered.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

    # Pivoter pour avoir historique et prédiction côte à côte
    annual_pivot = annual_avg.pivot_table(index='annee', columns='type_donnee', values='puissance_kw_pred').reset_index()

    # Créer une colonne combinée en moyennant les deux types si les deux existent
    if 'Historique' in annual_pivot.columns and 'Prédiction' in annual_pivot.columns:
        annual_pivot['moyenne'] = annual_pivot[['Historique', 'Prédiction']].mean(axis=1, skipna=True)
    elif 'Historique' in annual_pivot.columns:
        annual_pivot['moyenne'] = annual_pivot['Historique']
    else:
        annual_pivot['moyenne'] = annual_pivot['Prédiction']

    # Déterminer la couleur pour chaque année
    def get_year_color(row):
        if 'Historique' in annual_pivot.columns and 'Prédiction' in annual_pivot.columns:
            has_hist = pd.notna(row.get('Historique'))
            has_pred = pd.notna(row.get('Prédiction'))
            if has_hist and has_pred:
                return '#F2C94C'  # Jaune pour mixte
            elif has_hist:
                return '#2ca02c'  # Vert pour historique
            else:
                return '#ff7f0e'  # Orange pour prédiction
        elif 'Historique' in annual_pivot.columns:
            return '#2ca02c'
        else:
            return '#ff7f0e'

    annual_pivot['couleur'] = annual_pivot.apply(get_year_color, axis=1)

    # Créer le graphique
    fig_annual_compare = go.Figure()

    # Ajouter la ligne reliant tous les points
    fig_annual_compare.add_trace(go.Scatter(
        x=annual_pivot['annee'],
        y=annual_pivot['moyenne'],
        mode='lines+markers',
        name='Évolution',
        line=dict(color='#555555', width=2),
        marker=dict(
            size=18,
            color=annual_pivot['couleur'],
            line=dict(color='white', width=2)
        ),
        hovertemplate='Année %{x}<br>Moyenne: %{y:.1f} kW<extra></extra>'
    ))

    # Ajouter une légende personnalisée
    fig_annual_compare.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=10, color='#2ca02c'),
        showlegend=True,
        name='Année historique'
    ))

    fig_annual_compare.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=10, color='#ff7f0e'),
        showlegend=True,
        name='Année prédite'
    ))

    fig_annual_compare.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=10, color='#F2C94C'),
        showlegend=True,
        name='Année mixte'
    ))

    fig_annual_compare.update_layout(
        title="Consommation moyenne annuelle",
        xaxis_title="Année",
        yaxis_title="Puissance moyenne (kW)",
        height=500,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255, 255, 255, 0)"
        )
    )

    st.plotly_chart(fig_annual_compare, use_container_width=True)


with tab_mensuel:
    st.subheader("Comparaison des profils mensuels par année")

    # Profil mensuel moyen par année
    monthly_profile = df_filtered.groupby(['annee', 'mois', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

    # Séparer les années historiques et prédites
    annees_hist = sorted(monthly_profile[monthly_profile['type_donnee'] == 'Historique']['annee'].unique())
    annees_pred = sorted(monthly_profile[monthly_profile['type_donnee'] == 'Prédiction']['annee'].unique())

    fig_monthly_compare = go.Figure()

    # Couleurs distinctes
    colors_hist = ['#2ca02c', '#17becf', '#98df8a']
    colors_pred = ['#ff7f0e', '#ff9896', '#ffbb78']

    # Labels des mois en français
    mois_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

    # Tracer les années historiques
    for idx, annee in enumerate(annees_hist):
        data = monthly_profile[monthly_profile['annee'] == annee]
        if len(data) > 0:
            # Trier par mois pour s'assurer de l'ordre Jan -> Déc
            data = data.sort_values('mois')
            fig_monthly_compare.add_trace(go.Scatter(
                x=[mois_labels[m-1] for m in data['mois']],
                y=data['puissance_kw_pred'],
                mode='lines+markers',
                name=f'{annee} (Historique)',
                line=dict(color=colors_hist[idx % len(colors_hist)], width=2.5),
                marker=dict(size=7),
                hovertemplate=f'Année {annee}<br>Mois: %{{x}}<br>Moyenne: %{{y:.1f}} kW<extra></extra>'
            ))

    # Tracer les années prédites
    for idx, annee in enumerate(annees_pred):
        data = monthly_profile[monthly_profile['annee'] == annee]
        if len(data) > 0:
            # Trier par mois pour s'assurer de l'ordre Jan -> Déc
            data = data.sort_values('mois')
            fig_monthly_compare.add_trace(go.Scatter(
                x=[mois_labels[m-1] for m in data['mois']],
                y=data['puissance_kw_pred'],
                mode='lines+markers',
                name=f'{annee} (Prédiction)',
                line=dict(color=colors_pred[idx % len(colors_pred)], width=2.5, dash='dot'),
                marker=dict(size=7),
                hovertemplate=f'Année {annee}<br>Mois: %{{x}}<br>Moyenne: %{{y:.1f}} kW<extra></extra>'
            ))

    fig_monthly_compare.update_layout(
        title="Profil de consommation mensuel par année",
        xaxis_title="Mois",
        yaxis_title="Puissance moyenne (kW)",
        height=500,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(categoryorder='array', categoryarray=mois_labels)
    )

    st.plotly_chart(fig_monthly_compare, use_container_width=True)

    st.info("💡 Comparez les patterns saisonniers entre les différentes années pour identifier les évolutions.")

with tab_hebdo:
    st.subheader("Comparaison des profils hebdomadaires")

    # Profil hebdomadaire (jour de la semaine)
    df_filtered['jour_semaine'] = df_filtered['datetime'].dt.dayofweek
    weekly_profile = df_filtered.groupby(['annee', 'jour_semaine', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

    # Labels des jours
    jours_labels = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    # Créer le graphique en barres
    fig_hebdo = go.Figure()

    # Couleurs pour différentes années
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

    # Tracer pour chaque année
    for idx, annee in enumerate(sorted(weekly_profile['annee'].unique())):
        for type_data in ['Historique', 'Prédiction']:
            data = weekly_profile[(weekly_profile['annee'] == annee) & (weekly_profile['type_donnee'] == type_data)]
            if len(data) > 0:
                data = data.sort_values('jour_semaine')
                color = colors[idx % len(colors)]
                opacity = 1.0 if type_data == 'Historique' else 0.6
                pattern = None if type_data == 'Historique' else dict(shape="/", solidity=0.3)

                fig_hebdo.add_trace(go.Bar(
                    x=[jours_labels[j] for j in data['jour_semaine']],
                    y=data['puissance_kw_pred'],
                    name=f'{int(annee)} ({type_data})',
                    marker=dict(
                        color=color,
                        opacity=opacity,
                        pattern=pattern
                    ),
                    hovertemplate=f'Année {int(annee)} ({type_data})<br>Jour: %{{x}}<br>Moyenne: %{{y:.1f}} kW<extra></extra>'
                ))

    fig_hebdo.update_layout(
        title="Profil de consommation hebdomadaire par année",
        xaxis_title="Jour de la semaine",
        yaxis_title="Puissance moyenne (kW)",
        height=500,
        barmode='group',
        hovermode='x unified',
        xaxis=dict(categoryorder='array', categoryarray=jours_labels),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_hebdo, use_container_width=True)

    st.info("💡 Ce graphique montre les variations de consommation selon les jours de la semaine. Les barres pleines représentent l'historique, les barres hachurées les prédictions.")

with tab_horaire:
    st.subheader("Comparaison des profils horaires moyens")

    # Profil horaire moyen
    hourly_profile = df_filtered.groupby(['heure', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()

    fig_hourly_compare = go.Figure()

    for type_data in ['Historique', 'Prédiction']:
        data = hourly_profile[hourly_profile['type_donnee'] == type_data]
        if len(data) > 0:
            color = '#2ca02c' if type_data == 'Historique' else '#ff7f0e'
            dash = 'solid' if type_data == 'Historique' else 'dot'
            fig_hourly_compare.add_trace(go.Scatter(
                x=data['heure'],
                y=data['puissance_kw_pred'],
                mode='lines+markers',
                name=type_data,
                line=dict(color=color, width=3, dash=dash),
                marker=dict(size=6),
                hovertemplate='Heure: %{x}h<br>Moyenne: %{y:.1f} kW<extra></extra>'
            ))

    fig_hourly_compare.update_layout(
        title="Profil de consommation horaire moyen",
        xaxis_title="Heure de la journée",
        yaxis_title="Puissance moyenne (kW)",
        height=500,
        xaxis=dict(tickmode='linear', tick0=0, dtick=2),
        hovermode='x unified'
    )

    st.plotly_chart(fig_hourly_compare, use_container_width=True)

    st.info("💡 Le profil horaire montre si le modèle capte bien les variations journalières typiques (pics le matin/soir).")

st.markdown("---")

# ============================================================================
# PARTIE 3.5 : MODULE BUDGÉTAIRE (PILOTAGE)
# ============================================================================
if prix_spot is not None and not prix_spot.empty:
    st.header("💰 Pilotage Budgétaire")

    st.markdown("""
    Cette section vous permet d'analyser les coûts d'achat d'électricité en fonction de votre couverture contractuelle.
    """)

    # Import du calculateur
    from budget_helper import BudgetCalculator

    # Créer le calculateur
    calculator = BudgetCalculator(prix_spot)
    df_enrichi = calculator.enrichir_predictions(df_predictions)

    # Définir Peak/Base
    df_enrichi['heure'] = df_enrichi['datetime'].dt.hour
    df_enrichi['jour_semaine'] = df_enrichi['datetime'].dt.dayofweek
    df_enrichi['is_peak'] = (
        (df_enrichi['heure'] >= 8) &
        (df_enrichi['heure'] < 20) &
        (df_enrichi['jour_semaine'] < 5)
    )

    df_enrichi['volume_achete_kw'] = np.where(
        df_enrichi['is_peak'],
        volume_base + volume_peak,
        volume_base
    )

    df_enrichi['prix_achete_eur_mwh'] = np.where(
        df_enrichi['is_peak'],
        (volume_base * prix_base + volume_peak * prix_peak) / (volume_base + volume_peak),
        prix_base
    )

    # Calculer les coûts
    df_calc = calculator.calculer_cout_avec_parametres(
        df_enrichi,
        tarif_acheminement_eur_kwh=turpe,
        taux_taxe_pct=taxes,
        volumes_achetes_kw=df_enrichi['volume_achete_kw'],
        prix_achetes_eur_mwh=df_enrichi['prix_achete_eur_mwh']
    )

    # Préparer données
    df_calc['mois'] = df_calc['datetime'].dt.to_period('M').astype(str)
    df_calc['vol_base_mwh'] = volume_base / 1000
    df_calc['vol_peak_mwh'] = np.where(df_calc['is_peak'], volume_peak / 1000, 0)
    df_calc['cout_base_eur'] = volume_base * prix_base / 1000
    df_calc['cout_peak_eur'] = np.where(df_calc['is_peak'], volume_peak * prix_peak / 1000, 0)
    df_calc['vol_achat_spot_mwh'] = np.where(df_calc['ecart_kw'] > 0, df_calc['ecart_kw'] / 1000, 0)
    df_calc['vol_vente_spot_mwh'] = np.where(df_calc['ecart_kw'] < 0, -df_calc['ecart_kw'] / 1000, 0)
    df_calc['cout_achat_spot'] = np.where(df_calc['ecart_kw'] > 0, df_calc['cout_ecart_spot_eur'], 0)
    df_calc['credit_vente_spot'] = np.where(df_calc['ecart_kw'] < 0, -df_calc['cout_ecart_spot_eur'], 0)

    # Agrégation mensuelle
    rapport = df_calc.groupby('mois').agg({
        'conso_reelle_kw': lambda x: x.sum() / 1000,
        'cout_total_eur': 'sum',
        'vol_base_mwh': 'sum',
        'vol_peak_mwh': 'sum',
        'cout_base_eur': 'sum',
        'cout_peak_eur': 'sum',
        'vol_achat_spot_mwh': 'sum',
        'vol_vente_spot_mwh': 'sum',
        'cout_achat_spot': 'sum',
        'credit_vente_spot': 'sum',
        'prix_spot_eur_mwh': 'mean'
    }).reset_index()

    rapport['prix_moyen'] = rapport['cout_total_eur'] / rapport['conso_reelle_kw']
    rapport['vol_couverture'] = rapport['vol_base_mwh'] + rapport['vol_peak_mwh']
    rapport['cout_couverture'] = rapport['cout_base_eur'] + rapport['cout_peak_eur']
    rapport['taux_couverture'] = rapport['vol_couverture'] / rapport['conso_reelle_kw'] * 100

    # KPIs GLOBAUX
    st.subheader("📊 Vue d'ensemble budgétaire")

    col1, col2, col3, col4, col5 = st.columns(5)

    total_volume = rapport['conso_reelle_kw'].sum()
    total_cout = rapport['cout_total_eur'].sum()
    prix_moyen_global = total_cout / total_volume if total_volume > 0 else 0
    taux_cov_moyen = rapport['taux_couverture'].mean()
    total_achat_spot = rapport['vol_achat_spot_mwh'].sum()

    with col1:
        st.metric("Volume total", f"{total_volume:,.0f} MWh")

    with col2:
        st.metric("Coût total", f"{total_cout:,.0f} €")

    with col3:
        st.metric("Prix moyen", f"{prix_moyen_global:.2f} €/MWh")

    with col4:
        st.metric("Taux couverture", f"{taux_cov_moyen:.1f}%")

    with col5:
        exposition_spot = (total_achat_spot / total_volume * 100) if total_volume > 0 else 0
        st.metric("Exposition spot", f"{exposition_spot:.1f}%")

    # Onglets budgétaires
    tab_vol, tab_cout, tab_prix = st.tabs(["📦 Volumes", "💰 Coûts", "📈 Prix"])

    with tab_vol:
        st.subheader("Répartition des volumes")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Graphique empilé volumes mensuels
            fig_vol = go.Figure()

            fig_vol.add_trace(go.Bar(
                name='Base',
                x=rapport['mois'],
                y=rapport['vol_base_mwh'],
                marker_color='#2E86AB'
            ))

            fig_vol.add_trace(go.Bar(
                name='Peak',
                x=rapport['mois'],
                y=rapport['vol_peak_mwh'],
                marker_color='#A23B72'
            ))

            fig_vol.add_trace(go.Bar(
                name='Achat Spot',
                x=rapport['mois'],
                y=rapport['vol_achat_spot_mwh'],
                marker_color='#F18F01'
            ))

            fig_vol.add_trace(go.Bar(
                name='Vente Spot',
                x=rapport['mois'],
                y=-rapport['vol_vente_spot_mwh'],
                marker_color='#C73E1D'
            ))

            fig_vol.update_layout(
                barmode='relative',
                title='Volumes mensuels par type',
                xaxis_title='Mois',
                yaxis_title='Volume (MWh)',
                height=400,
                hovermode='x unified'
            )

            st.plotly_chart(fig_vol, use_container_width=True)

        with col2:
            # Répartition globale
            total_base = rapport['vol_base_mwh'].sum()
            total_peak = rapport['vol_peak_mwh'].sum()
            total_achat = rapport['vol_achat_spot_mwh'].sum()
            total_vente = rapport['vol_vente_spot_mwh'].sum()

            fig_pie = go.Figure(data=[go.Pie(
                labels=['Base', 'Peak', 'Achat Spot', 'Vente Spot'],
                values=[total_base, total_peak, total_achat, total_vente],
                hole=0.4,
                marker=dict(colors=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D'])
            )])

            fig_pie.update_layout(
                title='Répartition globale',
                height=400
            )

            st.plotly_chart(fig_pie, use_container_width=True)

    with tab_cout:
        st.subheader("Répartition des coûts")

        # Graphique empilé coûts mensuels
        fig_cout = go.Figure()

        fig_cout.add_trace(go.Bar(
            name='Couverture (Base+Peak)',
            x=rapport['mois'],
            y=rapport['cout_couverture'],
            marker_color='#2E86AB'
        ))

        fig_cout.add_trace(go.Bar(
            name='Achat Spot',
            x=rapport['mois'],
            y=rapport['cout_achat_spot'],
            marker_color='#F18F01'
        ))

        fig_cout.add_trace(go.Bar(
            name='Crédit Vente Spot',
            x=rapport['mois'],
            y=-rapport['credit_vente_spot'],
            marker_color='#27AE60'
        ))

        fig_cout.update_layout(
            barmode='relative',
            title='Coûts mensuels par composante',
            xaxis_title='Mois',
            yaxis_title='Coût (€)',
            height=400,
            hovermode='x unified'
        )

        st.plotly_chart(fig_cout, use_container_width=True)

        # KPIs coûts
        col1, col2, col3 = st.columns(3)

        total_cout_couv = rapport['cout_couverture'].sum()
        total_cout_achat = rapport['cout_achat_spot'].sum()
        total_credit_vente = rapport['credit_vente_spot'].sum()

        with col1:
            pct_couv = (total_cout_couv/total_cout*100) if total_cout > 0 else 0
            st.metric("Couverture", f"{total_cout_couv:,.0f} €",
                      delta=f"{pct_couv:.1f}%")

        with col2:
            pct_achat = (total_cout_achat/total_cout*100) if total_cout > 0 else 0
            st.metric("Achat Spot", f"{total_cout_achat:,.0f} €",
                      delta=f"{pct_achat:.1f}%")

        with col3:
            pct_vente = (total_credit_vente/total_cout*100) if total_cout > 0 else 0
            st.metric("Crédit Vente", f"{total_credit_vente:,.0f} €",
                      delta=f"-{pct_vente:.1f}%",
                      delta_color="normal")

    with tab_prix:
        st.subheader("Analyse des prix")

        # Prix moyens mensuels
        fig_prix = go.Figure()

        fig_prix.add_trace(go.Scatter(
            x=rapport['mois'],
            y=rapport['prix_moyen'],
            name='Prix moyen global',
            line=dict(color='#2E86AB', width=3),
            mode='lines+markers'
        ))

        fig_prix.add_trace(go.Scatter(
            x=rapport['mois'],
            y=[prix_base] * len(rapport),
            name='Prix Base (contractuel)',
            line=dict(color='#27AE60', width=2, dash='dash')
        ))

        fig_prix.add_trace(go.Scatter(
            x=rapport['mois'],
            y=[prix_peak] * len(rapport),
            name='Prix Peak (contractuel)',
            line=dict(color='#A23B72', width=2, dash='dash')
        ))

        fig_prix.add_trace(go.Scatter(
            x=rapport['mois'],
            y=rapport['prix_spot_eur_mwh'],
            name='Prix spot moyen',
            line=dict(color='#F18F01', width=2),
            mode='lines+markers'
        ))

        fig_prix.update_layout(
            title='Évolution des prix moyens',
            xaxis_title='Mois',
            yaxis_title='Prix (€/MWh)',
            height=400,
            hovermode='x unified'
        )

        st.plotly_chart(fig_prix, use_container_width=True)

        # Taux de couverture
        fig_taux = go.Figure()

        fig_taux.add_trace(go.Scatter(
            x=rapport['mois'],
            y=rapport['taux_couverture'],
            fill='tozeroy',
            fillcolor='rgba(46, 134, 171, 0.3)',
            line=dict(color='#2E86AB', width=3),
            mode='lines+markers'
        ))

        fig_taux.add_hline(
            y=100,
            line_dash="dash",
            line_color="gray",
            annotation_text="Couverture 100%"
        )

        fig_taux.update_layout(
            title='Taux de couverture mensuel',
            xaxis_title='Mois',
            yaxis_title='Taux de couverture (%)',
            height=400
        )

        st.plotly_chart(fig_taux, use_container_width=True)

    # Export rapport
    st.subheader("📥 Export rapport budgétaire")

    csv_rapport = rapport.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Télécharger le rapport mensuel (CSV)",
        data=csv_rapport,
        file_name=f"rapport_budgetaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    st.markdown("---")

# ============================================================================
# PARTIE 4 : INFORMATIONS SUR LE MODÈLE
# ============================================================================
st.header("Informations sur le Modèle")

if model_metrics:
    st.markdown("""
    Ce dashboard utilise un modèle **LSTM (Long Short-Term Memory)** pour prédire la consommation énergétique.
    Voici les performances du modèle pour vous aider à évaluer la fiabilité des prédictions.
    """)

    # Métriques en colonnes
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mae = model_metrics.get('metrics', {}).get('mae', 0)
        st.metric(
            label="MAE (Erreur Moyenne)",
            value=f"{mae:.2f} kW",
            delta="Excellent" if mae < 40 else "Bon" if mae < 60 else "Moyen"
        )
        st.caption("Plus c'est bas, mieux c'est ✅")

    with col2:
        rmse = model_metrics.get('metrics', {}).get('rmse', 0)
        st.metric(
            label="RMSE (Écart-type)",
            value=f"{rmse:.2f} kW",
            delta="Excellent" if rmse < 50 else "Bon" if rmse < 80 else "Moyen"
        )
        st.caption("Pénalise les grosses erreurs 📊")

    with col3:
        r2 = model_metrics.get('metrics', {}).get('r2', 0)
        st.metric(
            label="R² (Coefficient)",
            value=f"{r2:.4f}",
            delta="Excellent" if r2 > 0.90 else "Bon" if r2 > 0.80 else "Moyen"
        )
        st.caption("Plus proche de 1 = mieux 🎯")

    with col4:
        mape = model_metrics.get('metrics', {}).get('mape', 0)
        st.metric(
            label="MAPE (% Erreur)",
            value=f"{mape:.2f}%",
            delta="Excellent" if mape < 15 else "Bon" if mape < 30 else "Moyen"
        )
        st.caption("Erreur en pourcentage 📈")

    # Explications pour les non-initiés
    with st.expander("📚 Comprendre ces métriques (cliquez pour en savoir plus)"):
        st.markdown("""
        ### 🎯 Comment interpréter la qualité du modèle ?

        **MAE (Mean Absolute Error) - Erreur Moyenne Absolue**
        - Représente l'écart moyen entre les prédictions et la réalité
        - **Exemple** : MAE de 32 kW signifie qu'en moyenne, le modèle se trompe de ±32 kW
        - ✅ **Excellent** : < 40 kW | 🟢 **Bon** : 40-60 kW | 🟡 **Moyen** : > 60 kW

        **RMSE (Root Mean Squared Error) - Écart-type**
        - Similaire à MAE mais pénalise plus fortement les grosses erreurs
        - Plus sensible aux pics d'erreur
        - ✅ **Excellent** : < 50 kW | 🟢 **Bon** : 50-80 kW | 🟡 **Moyen** : > 80 kW

        **R² (Coefficient de Détermination)**
        - Mesure la capacité du modèle à expliquer les variations de consommation
        - **0.94** signifie que le modèle explique **94% des variations**
        - ✅ **Excellent** : > 0.90 | 🟢 **Bon** : 0.80-0.90 | 🟡 **Moyen** : < 0.80

        **MAPE (Mean Absolute Percentage Error) - Erreur en %**
        - Exprime l'erreur en pourcentage de la valeur réelle
        - Plus intuitif pour les non-techniciens
        - ✅ **Excellent** : < 15% | 🟢 **Bon** : 15-30% | 🟡 **Moyen** : > 30%

        ---

        ### 🔮 Fiabilité des prédictions long terme

        ⚠️ **IMPORTANT** : Ces métriques ont été calculées sur des **données de test avec vraie météo**.

        Les prédictions long terme (3 ans) utilisent des **moyennes climatiques** et sont donc :
        - ✅ **Fiables pour les tendances globales** (consommation mensuelle, saisonnière)
        - ✅ **Utiles pour la planification à long terme**
        - ⚠️ **Moins précises au jour le jour** (pas de vraies prévisions météo)
        - ⚠️ **Ne capturent pas les événements exceptionnels** (canicules, vagues de froid)

        ### 💡 Recommandations

        - **Court terme (< 15 jours)** : Utilisez le modèle avec vraies prévisions météo → Précision maximale
        - **Moyen terme (1-3 mois)** : Prédictions indicatives, tendances fiables
        - **Long terme (1-3 ans)** : Planification stratégique, budget prévisionnel
        """)
else:
    st.info("ℹ️ Les métriques du modèle ne sont pas disponibles. Lancez l'entraînement du modèle pour voir les performances.")

st.markdown("---")

# ============================================================================
# FOOTER : INFORMATIONS ET EXPORT
# ============================================================================
st.header("Export des Données")

col1, col2 = st.columns(2)

with col1:
    # Export CSV filtré
    csv_filtered = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Télécharger les données filtrées (CSV)",
        data=csv_filtered,
        file_name=f"predictions_filtrees_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

with col2:
    # Export statistiques
    stats_export = df_filtered.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].describe().to_csv()
    st.download_button(
        label="📥 Télécharger les statistiques (CSV)",
        data=stats_export,
        file_name=f"statistiques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
