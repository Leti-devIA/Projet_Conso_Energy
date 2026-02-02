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

# Configuration de la page
st.set_page_config(
    page_title="Dashboard Prédictions 3 ans",
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

# Titre principal
st.title("📊 Dashboard de Prédictions Long Terme")
st.markdown("Visualisation des prédictions de consommation énergétique basées sur des moyennes climatiques")

# Sidebar
st.sidebar.header("⚙️ Configuration")

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
def load_model_metrics():
    """Charge les métriques du modèle depuis le fichier config sauvegardé"""
    try:
        config_path = Path("models/saved/config_latest.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Erreur lors du chargement des métriques : {e}")
        return None

# Sélection du fichier
predictions_dir = Path("data/predictions")
if predictions_dir.exists():
    csv_files = list(predictions_dir.glob("predictions_longterm_*.csv"))
    if csv_files:
        selected_file = st.sidebar.selectbox(
            "📂 Fichier de prédictions",
            csv_files,
            format_func=lambda x: x.name
        )
    else:
        st.error("❌ Aucun fichier de prédictions trouvé dans data/predictions/")
        st.info("💡 Lancez d'abord : `python main.py predict-longterm --historique dataFE_prm_30000250086126.csv --years 3`")
        st.stop()
else:
    st.error("❌ Le dossier data/predictions/ n'existe pas")
    st.stop()

# Option pour charger l'historique
st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 Données Historiques")
load_hist = st.sidebar.checkbox("Charger les données historiques", value=True)

historique = None
if load_hist:
    hist_file = st.sidebar.text_input(
        "Fichier historique",
        value="dataFE_prm_30000250086126.csv"
    )
    if Path(hist_file).exists():
        historique = load_historique(hist_file)
        if historique is not None:
            st.sidebar.success(f"✅ {len(historique):,} lignes historiques chargées")
    else:
        st.sidebar.error(f"❌ Fichier introuvable : {hist_file}")

# Charger les données
df_predictions = load_predictions(selected_file)

if df_predictions is None or len(df_predictions) == 0:
    st.error("❌ Impossible de charger les données ou fichier vide")
    st.stop()

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

# Charger les métriques du modèle
model_metrics = load_model_metrics()

# Informations générales
st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 Statistiques générales")

# Stats prédictions
st.sidebar.markdown("**🔮 Prédictions**")
st.sidebar.metric("📅 Période", f"{df_predictions['datetime'].min().strftime('%Y-%m-%d')} → {df_predictions['datetime'].max().strftime('%Y-%m-%d')}")
st.sidebar.metric("⏱️ Nombre d'heures", f"{len(df_predictions):,}")
st.sidebar.metric("📆 Nombre de jours", f"{len(df_predictions)//24:,}")

# Stats historique si disponible
if historique is not None:
    st.sidebar.markdown("**📚 Historique**")
    st.sidebar.metric("📅 Période", f"{historique['datetime'].min().strftime('%Y-%m-%d')} → {historique['datetime'].max().strftime('%Y-%m-%d')}")
    st.sidebar.metric("⏱️ Nombre d'heures", f"{len(historique):,}")
    
# Stats globales
st.sidebar.markdown("**🌍 Global**")
st.sidebar.metric("📊 Années couvertes", f"{df_all['annee'].nunique()}")

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
    st.warning("⚠️ Sélectionnez au moins une année")
    st.stop()

# Filtrer les données
df_filtered = df_all[df_all['annee'].isin(annees_selectionnees)].copy()



# ============================================================================
# SECTION 1 : MÉTRIQUES CLÉS
# ============================================================================
st.header("📊 Métriques Clés")

col1, col2, col3, col4 = st.columns(4)

with col1:
    avg_consumption = df_filtered['puissance_kw_pred'].mean()
    st.metric(
        label="📈 Consommation moyenne",
        value=f"{avg_consumption:.1f} kW",
        delta=None
    )

with col2:
    max_consumption = df_filtered['puissance_kw_pred'].max()
    max_date = df_filtered.loc[df_filtered['puissance_kw_pred'].idxmax(), 'datetime']
    st.metric(
        label="🔺 Pic maximum",
        value=f"{max_consumption:.1f} kW",
        delta=f"{max_date.strftime('%d/%m/%Y %Hh')}"
    )

with col3:
    min_consumption = df_filtered['puissance_kw_pred'].min()
    min_date = df_filtered.loc[df_filtered['puissance_kw_pred'].idxmin(), 'datetime']
    st.metric(
        label="🔻 Minimum",
        value=f"{min_consumption:.1f} kW",
        delta=f"{min_date.strftime('%d/%m/%Y %Hh')}"
    )

with col4:
    total_energy = (df_filtered['puissance_kw_pred'].sum() / 1000)  # MWh
    st.metric(
        label="⚡ Énergie totale",
        value=f"{total_energy:,.0f} MWh",
        delta=f"{len(df_filtered)//24} jours"
    )

st.markdown("---")

# ============================================================================
# SECTION 2 : COMPARAISON HISTORIQUE VS PRÉDICTIONS
# ============================================================================
if historique is not None:
    st.header("📊 Comparaison Historique vs Prédictions")
    
    st.markdown("""
    Cette section compare les données historiques réelles avec les prédictions du modèle pour évaluer
    la cohérence et identifier les tendances d'évolution.
    """)
    
    # Onglets de comparaison
    tab1, tab2, tab3 = st.tabs(["📊 Statistiques Détaillées", "📅 Comparaison Mensuelle", "⏱️ Profils Horaires"])
    
    with tab1:
        # Statistiques par année avec distinction historique/prédiction
        stats_annee = df_filtered.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].agg([
            ('Moyenne (kW)', 'mean'),
            ('Maximum (kW)', 'max'),
            ('Minimum (kW)', 'min'),
            ('Écart-type (kW)', 'std'),
            ('Énergie totale (MWh)', lambda x: x.sum() / 1000)
        ]).round(2).reset_index()
        
        # Afficher séparément historique et prédictions
        st.markdown("**📚 Données Historiques**")
        hist_stats = stats_annee[stats_annee['type_donnee'] == 'Historique'].drop('type_donnee', axis=1)
        if len(hist_stats) > 0:
            st.dataframe(hist_stats.set_index('annee'), use_container_width=True)
        else:
            st.info("Aucune donnée historique disponible")
        
        st.markdown("**🔮 Prédictions**")
        pred_stats = stats_annee[stats_annee['type_donnee'] == 'Prédiction'].drop('type_donnee', axis=1)
        if len(pred_stats) > 0:
            st.dataframe(pred_stats.set_index('annee'), use_container_width=True)
        else:
            st.info("Aucune prédiction disponible")
    
    with tab2:
        st.subheader("Comparaison des profils mensuels")
        
        # Profil mensuel moyen par année
        monthly_profile = df_filtered.groupby(['mois', 'annee', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()
        
        # S'assurer que les mois sont dans l'ordre (1-12)
        monthly_profile = monthly_profile.sort_values(['annee', 'mois'])
        
        fig_monthly_compare = go.Figure()
        
        mois_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 
                       'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
        
        # Palettes de couleurs : tons verts pour historique, tons orange pour prédictions
        colors_hist = ["#072707", "#047a04", "#5fff5f", "#76a076", ]  # Nuances de vert
        colors_pred = ["#5f2802", "#C05407", "#eea978", "#a5755f"]  # Nuances d'orange
        
        # Séparer les années historiques et prédictions
        annees_hist = []
        annees_pred = []
        
        for annee in sorted(monthly_profile['annee'].unique()):
            data_annee = monthly_profile[monthly_profile['annee'] == annee]
            if 'Historique' in data_annee['type_donnee'].values:
                annees_hist.append(annee)
            else:
                annees_pred.append(annee)
        
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
            title="Profil de consommation mensuel par année (🟢 Historique | 🟠 Prédictions)",
            xaxis_title="Mois",
            yaxis_title="Puissance moyenne (kW)",
            height=500,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(categoryorder='array', categoryarray=mois_labels)
        )
        
        st.plotly_chart(fig_monthly_compare, use_container_width=True)
        
        st.info("💡 Comparez les patterns saisonniers entre les différentes années pour identifier les évolutions.")
    
    with tab3:
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
# SECTION 3 : ÉVOLUTION TEMPORELLE
# ============================================================================
st.header("📈 Évolution de la Consommation")

# Tabs pour différentes vues
tab1, tab2, tab3 = st.tabs(["📅 Vue Mensuelle", "📆 Vue Hebdomadaire", "⏱️ Vue Horaire"])

with tab1:
    # Agrégation mensuelle
    df_monthly = df_filtered.set_index('datetime').resample('M')['puissance_kw_pred'].agg(['mean', 'max', 'min']).reset_index()
    
    # Ajouter le type de données basé sur la date
    if historique is not None:
        date_limite = historique['datetime'].max()
        df_monthly['type_donnee'] = df_monthly['datetime'].apply(
            lambda x: 'Historique' if x <= date_limite else 'Prédiction'
        )
    else:
        df_monthly['type_donnee'] = 'Prédiction'
    
    fig_monthly = go.Figure()
    
    # Séparer historique et prédictions
    for type_data in df_monthly['type_donnee'].unique():
        data = df_monthly[df_monthly['type_donnee'] == type_data]
        color = '#2ca02c' if type_data == 'Historique' else '#ff7f0e'
        dash = 'solid' if type_data == 'Historique' else 'dot'
        
        fig_monthly.add_trace(go.Scatter(
            x=data['datetime'],
            y=data['mean'],
            mode='lines+markers',
            name=f'{type_data} - Moyenne',
            line=dict(color=color, width=3, dash=dash),
            marker=dict(size=8),
            hovertemplate='%{x|%B %Y}<br>Moyenne: %{y:.1f} kW<extra></extra>'
        ))
        
        fig_monthly.add_trace(go.Scatter(
            x=data['datetime'],
            y=data['max'],
            mode='lines',
            name=f'{type_data} - Max',
            line=dict(color=color, width=2, dash='dash'),
            opacity=0.5,
            hovertemplate='%{x|%B %Y}<br>Maximum: %{y:.1f} kW<extra></extra>'
        ))
        
        fig_monthly.add_trace(go.Scatter(
            x=data['datetime'],
            y=data['min'],
            mode='lines',
            name=f'{type_data} - Min',
            line=dict(color=color, width=2, dash='dash'),
            opacity=0.5,
            hovertemplate='%{x|%B %Y}<br>Minimum: %{y:.1f} kW<extra></extra>'
        ))
    
    fig_monthly.update_layout(
        title="Consommation moyenne mensuelle avec min/max (🟢 Historique | 🟠 Prédictions)",
        xaxis_title="Date",
        yaxis_title="Puissance (kW)",
        height=500,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_monthly, use_container_width=True)

with tab2:
    # Agrégation hebdomadaire
    df_weekly = df_filtered.set_index('datetime').resample('W')['puissance_kw_pred'].mean().reset_index()
    
    # Ajouter le type de données
    if historique is not None:
        date_limite = historique['datetime'].max()
        df_weekly['type_donnee'] = df_weekly['datetime'].apply(
            lambda x: 'Historique' if x <= date_limite else 'Prédiction'
        )
    else:
        df_weekly['type_donnee'] = 'Prédiction'
    
    fig_weekly = go.Figure()
    
    for type_data in df_weekly['type_donnee'].unique():
        data = df_weekly[df_weekly['type_donnee'] == type_data]
        color = '#2ca02c' if type_data == 'Historique' else '#ff7f0e'
        fillcolor = 'rgba(44, 160, 44, 0.2)' if type_data == 'Historique' else 'rgba(255, 127, 14, 0.2)'
        
        fig_weekly.add_trace(go.Scatter(
            x=data['datetime'],
            y=data['puissance_kw_pred'],
            mode='lines',
            name=type_data,
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=fillcolor,
            hovertemplate='Semaine du %{x|%d/%m/%Y}<br>Moyenne: %{y:.1f} kW<extra></extra>'
        ))
    
    fig_weekly.update_layout(
        title="Consommation moyenne hebdomadaire (🟢 Historique | 🟠 Prédictions)",
        xaxis_title="Date",
        yaxis_title="Puissance (kW)",
        height=500,
        hovermode='x'
    )
    
    st.plotly_chart(fig_weekly, use_container_width=True)

with tab3:
    # Profil horaire moyen par année et type
    df_hourly = df_filtered.groupby(['annee', 'heure', 'type_donnee'])['puissance_kw_pred'].mean().reset_index()
    
    fig_hourly = go.Figure()
    
    # Grouper par type de données
    for type_data in df_hourly['type_donnee'].unique():
        data_type = df_hourly[df_hourly['type_donnee'] == type_data]
        color_base = '#2ca02c' if type_data == 'Historique' else '#ff7f0e'
        
        for annee in sorted(data_type['annee'].unique()):
            df_annee = data_type[data_type['annee'] == annee]
            dash = 'solid' if type_data == 'Historique' else 'dot'
            
            fig_hourly.add_trace(go.Scatter(
                x=df_annee['heure'],
                y=df_annee['puissance_kw_pred'],
                mode='lines+markers',
                name=f'{annee} ({type_data})',
                line=dict(width=2, dash=dash),
                marker=dict(size=6),
                hovertemplate='Heure: %{x}h<br>Moyenne: %{y:.1f} kW<extra></extra>'
            ))
    
    fig_hourly.update_layout(
        title="Profil de consommation moyen par heure de la journée",
        xaxis_title="Heure de la journée",
        yaxis_title="Puissance moyenne (kW)",
        height=500,
        xaxis=dict(tickmode='linear', tick0=0, dtick=2),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_hourly, use_container_width=True)

st.markdown("---")

# ============================================================================
# SECTION 4 : COMPARAISON PAR ANNÉE
# ============================================================================
st.header("📊 Comparaison par Année")

col1, col2 = st.columns(2)

with col1:
    # Statistiques par année avec distinction historique/prédiction
    stats_annee = df_filtered.groupby(['annee', 'type_donnee'])['puissance_kw_pred'].agg([
        ('Moyenne (kW)', 'mean'),
        ('Maximum (kW)', 'max'),
        ('Minimum (kW)', 'min'),
        ('Écart-type (kW)', 'std'),
        ('Énergie totale (MWh)', lambda x: x.sum() / 1000)
    ]).round(2).reset_index()
    
    st.subheader("📋 Statistiques détaillées")
    
    # Afficher séparément historique et prédictions
    if historique is not None:
        st.markdown("**📚 Données Historiques**")
        hist_stats = stats_annee[stats_annee['type_donnee'] == 'Historique'].drop('type_donnee', axis=1)
        if len(hist_stats) > 0:
            st.dataframe(hist_stats.set_index('annee'), use_container_width=True)
        
        st.markdown("**🔮 Prédictions**")
        pred_stats = stats_annee[stats_annee['type_donnee'] == 'Prédiction'].drop('type_donnee', axis=1)
        if len(pred_stats) > 0:
            st.dataframe(pred_stats.set_index('annee'), use_container_width=True)
    else:
        st.dataframe(stats_annee.drop('type_donnee', axis=1).set_index('annee'), use_container_width=True)
    
    # Calcul de la croissance
    annees_uniques = sorted(df_filtered['annee'].unique())
    if len(annees_uniques) > 1:
        st.subheader("📈 Croissance annuelle")
        for i in range(1, len(annees_uniques)):
            annee_prev = annees_uniques[i-1]
            annee_curr = annees_uniques[i]
            
            avg_prev = df_filtered[df_filtered['annee'] == annee_prev]['puissance_kw_pred'].mean()
            avg_curr = df_filtered[df_filtered['annee'] == annee_curr]['puissance_kw_pred'].mean()
            
            croissance = ((avg_curr / avg_prev) - 1) * 100
            st.metric(
                f"{annee_prev} → {annee_curr}",
                f"{croissance:+.2f}%",
                delta=f"{avg_curr - avg_prev:.1f} kW"
            )

with col2:
    # Graphique de comparaison
    fig_compare = go.Figure()
    
    # Séparer par type de données
    annees_hist = []
    moyennes_hist = []
    annees_pred = []
    moyennes_pred = []
    
    for annee in sorted(df_filtered['annee'].unique()):
        df_annee = df_filtered[df_filtered['annee'] == annee]
        
        # Vérifier le type de données pour cette année
        if 'Historique' in df_annee['type_donnee'].values:
            annees_hist.append(str(annee))
            moyennes_hist.append(df_annee[df_annee['type_donnee'] == 'Historique']['puissance_kw_pred'].mean())
        
        if 'Prédiction' in df_annee['type_donnee'].values:
            annees_pred.append(str(annee))
            moyennes_pred.append(df_annee[df_annee['type_donnee'] == 'Prédiction']['puissance_kw_pred'].mean())
    
    # Historique
    if annees_hist:
        fig_compare.add_trace(go.Bar(
            x=annees_hist,
            y=moyennes_hist,
            name='Historique',
            marker_color='#2ca02c',
            text=[f"{m:.1f} kW" for m in moyennes_hist],
            textposition='outside',
            hovertemplate='Année %{x}<br>Moyenne: %{y:.1f} kW<extra></extra>'
        ))
    
    # Prédictions
    if annees_pred:
        fig_compare.add_trace(go.Bar(
            x=annees_pred,
            y=moyennes_pred,
            name='Prédictions',
            marker_color='#ff7f0e',
            text=[f"{m:.1f} kW" for m in moyennes_pred],
            textposition='outside',
            hovertemplate='Année %{x}<br>Moyenne: %{y:.1f} kW<extra></extra>'
        ))
    
    fig_compare.update_layout(
        title="Consommation moyenne par année",
        xaxis_title="Année",
        yaxis_title="Puissance moyenne (kW)",
        height=400,
        barmode='group'
    )
    
    st.plotly_chart(fig_compare, use_container_width=True)

st.markdown("---")

# ============================================================================
# SECTION 5 : HEATMAP & DISTRIBUTIONS
# ============================================================================
st.header("🔥 Analyses Avancées")

tab1, tab2, tab3 = st.tabs(["🌡️ Heatmap Mois/Heure", "📊 Distributions", "📅 Patterns Hebdomadaires"])

with tab1:
    # Heatmap mois x heure
    pivot_data = df_filtered.groupby(['mois', 'heure'])['puissance_kw_pred'].mean().reset_index()
    pivot_table = pivot_data.pivot(index='mois', columns='heure', values='puissance_kw_pred')
    
    mois_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 
                   'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=pivot_table.values,
        x=pivot_table.columns,
        y=[mois_labels[i-1] for i in pivot_table.index],
        colorscale='RdYlBu_r',
        hovertemplate='Mois: %{y}<br>Heure: %{x}h<br>Moyenne: %{z:.1f} kW<extra></extra>',
        colorbar=dict(title="kW")
    ))
    
    fig_heatmap.update_layout(
        title="Consommation moyenne par mois et heure de la journée",
        xaxis_title="Heure de la journée",
        yaxis_title="Mois",
        height=500,
        xaxis=dict(tickmode='linear', dtick=2)
    )
    
    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    st.info("💡 Les zones rouges indiquent les périodes de forte consommation, les zones bleues les périodes de faible consommation.")

with tab2:
    # Distribution de la consommation
    fig_dist = go.Figure()
    
    for annee in sorted(df_filtered['annee'].unique()):
        df_annee = df_filtered[df_filtered['annee'] == annee]
        fig_dist.add_trace(go.Histogram(
            x=df_annee['puissance_kw_pred'],
            name=f'Année {annee}',
            opacity=0.7,
            nbinsx=50,
            histnorm='probability'
        ))
    
    fig_dist.update_layout(
        title="Distribution de la consommation par année",
        xaxis_title="Puissance (kW)",
        yaxis_title="Fréquence",
        height=500,
        barmode='overlay',
        hovermode='x'
    )
    
    st.plotly_chart(fig_dist, use_container_width=True)
    
    # Box plot
    fig_box = go.Figure()
    
    for annee in sorted(df_filtered['annee'].unique()):
        df_annee = df_filtered[df_filtered['annee'] == annee]
        fig_box.add_trace(go.Box(
            y=df_annee['puissance_kw_pred'],
            name=f'Année {annee}',
            boxmean='sd'
        ))
    
    fig_box.update_layout(
        title="Dispersion de la consommation (Box plot)",
        yaxis_title="Puissance (kW)",
        height=400
    )
    
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    # Pattern jour de la semaine
    jours_semaine = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    df_dow = df_filtered.groupby('jour_semaine')['puissance_kw_pred'].mean().reset_index()
    df_dow['jour_nom'] = df_dow['jour_semaine'].apply(lambda x: jours_semaine[x])
    
    fig_dow = go.Figure()
    
    fig_dow.add_trace(go.Bar(
        x=df_dow['jour_nom'],
        y=df_dow['puissance_kw_pred'],
        marker_color=['#1f77b4']*5 + ['#ff7f0e']*2,  # Bleu semaine, orange weekend
        text=[f"{v:.1f} kW" for v in df_dow['puissance_kw_pred']],
        textposition='outside',
        hovertemplate='%{x}<br>Moyenne: %{y:.1f} kW<extra></extra>'
    ))
    
    fig_dow.update_layout(
        title="Consommation moyenne par jour de la semaine",
        xaxis_title="Jour",
        yaxis_title="Puissance moyenne (kW)",
        height=400
    )
    
    st.plotly_chart(fig_dow, use_container_width=True)
    
    # Heatmap jour x heure
    pivot_dow = df_filtered.groupby(['jour_semaine', 'heure'])['puissance_kw_pred'].mean().reset_index()
    pivot_dow_table = pivot_dow.pivot(index='jour_semaine', columns='heure', values='puissance_kw_pred')
    
    fig_dow_heatmap = go.Figure(data=go.Heatmap(
        z=pivot_dow_table.values,
        x=pivot_dow_table.columns,
        y=[jours_semaine[i] for i in pivot_dow_table.index],
        colorscale='Viridis',
        hovertemplate='%{y}<br>Heure: %{x}h<br>Moyenne: %{z:.1f} kW<extra></extra>',
        colorbar=dict(title="kW")
    ))
    
    fig_dow_heatmap.update_layout(
        title="Pattern hebdomadaire : Jour x Heure",
        xaxis_title="Heure de la journée",
        yaxis_title="Jour de la semaine",
        height=400,
        xaxis=dict(tickmode='linear', dtick=2)
    )
    
    st.plotly_chart(fig_dow_heatmap, use_container_width=True)

st.markdown("---")

# ============================================================================
# SECTION 0 : INFORMATIONS SUR LE MODÈLE
# ============================================================================
if model_metrics:
    st.header("Qualité du Modèle de Prédiction")
    
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
        
    st.markdown("---")

# ============================================================================
# SECTION 6 : EXPORT & TÉLÉCHARGEMENT
# ============================================================================
st.header("💾 Export des Données")

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
    if historique is not None:
        stats_export = stats_annee.to_csv(index=False)
    else:
        stats_export = df_filtered.groupby('annee')['puissance_kw_pred'].describe().to_csv()
    
    st.download_button(
        label="📥 Télécharger les statistiques (CSV)",
        data=stats_export,
        file_name=f"statistiques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


# Informations sur les données
info_text = "💡 <b>Note importante</b> : Ces prédictions sont basées sur des <b>moyennes climatiques</b>."

if historique is not None:
    nb_annees_hist = historique['annee'].nunique()
    nb_annees_pred = df_predictions['annee'].nunique()
    info_text += f"<br>📚 <b>{nb_annees_hist} années d'historique</b> réel disponibles pour comparaison."
    info_text += f"<br>🔮 <b>{nb_annees_pred} années de prédictions</b> générées."

info_text += "<br>Elles sont <b>indicatives</b> et moins précises que des prévisions à court terme avec de vraies données météo."

if model_metrics:
    r2 = model_metrics.get('metrics', {}).get('r2', 0)
    mae = model_metrics.get('metrics', {}).get('mae', 0)
    info_text += f"<br>📊 Modèle LSTM - R² = {r2:.4f} | MAE = {mae:.2f} kW"

info_text += f"<br>⚡ Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"

st.markdown(f"""
    <div style='text-align: center; color: #666; padding: 20px; background-color: #f0f2f6; border-radius: 10px;'>
        <p>{info_text}</p>
    </div>
    """, unsafe_allow_html=True)
