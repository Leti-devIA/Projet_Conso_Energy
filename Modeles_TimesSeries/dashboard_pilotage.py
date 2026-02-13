"""
Dashboard de Pilotage des Achats d'Électricité
Interface visuelle inspirée du tableau de suivi mensuel
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from budget_helper import BudgetCalculator, charger_prix_spot

st.set_page_config(page_title="Pilotage Achats Électricité", page_icon="⚡", layout="wide")

st.title("⚡ Pilotage des Achats d'Électricité")

# ============================================================================
# SIDEBAR : CONFIGURATION
# ============================================================================
st.sidebar.header("⚙️ Configuration")

# Charger fichiers
pred_file = st.sidebar.file_uploader("📊 Prédictions consommation", type=['csv'])
prix_file = st.sidebar.file_uploader("💰 Prix spot", type=['csv'])

if not pred_file or not prix_file:
    st.info("👈 Chargez vos fichiers pour commencer")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📊 Analyse de couverture")
        st.markdown("- Volume Base vs Peak")
        st.markdown("- Taux de couverture")
        st.markdown("- Exposition au spot")
    
    with col2:
        st.markdown("### 💰 Répartition des coûts")
        st.markdown("- Coût contractuel")
        st.markdown("- Coût spot (achat/vente)")
        st.markdown("- Prix moyens")
    
    with col3:
        st.markdown("### 📈 Évolution mensuelle")
        st.markdown("- Volumes par type")
        st.markdown("- Coûts par composante")
        st.markdown("- Tendances prix")
    
    st.stop()

# Charger données
df_pred = pd.read_csv(pred_file)
df_pred['datetime'] = pd.to_datetime(df_pred['datetime'])

df_prix = pd.read_csv(prix_file)
df_prix['date_deb'] = pd.to_datetime(df_prix['date_deb'])
df_prix['date_fin'] = pd.to_datetime(df_prix['date_fin'])

st.sidebar.success(f"✅ {len(df_pred):,} heures")

# Configuration volumes
st.sidebar.markdown("---")
st.sidebar.subheader("📦 Volumes achetés")

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

# ============================================================================
# CALCUL
# ============================================================================

calculator = BudgetCalculator(df_prix)
df_enrichi = calculator.enrichir_predictions(df_pred)

# Peak/Base
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

# Calculer
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

# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================

# KPIs GLOBAUX
st.header("📊 Vue d'ensemble")

col1, col2, col3, col4, col5 = st.columns(5)

total_volume = rapport['conso_reelle_kw'].sum()
total_cout = rapport['cout_total_eur'].sum()
prix_moyen_global = total_cout / total_volume
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
    exposition_spot = (total_achat_spot / total_volume * 100)
    st.metric("Exposition spot", f"{exposition_spot:.1f}%")

st.markdown("---")

# ============================================================================
# SECTION 1 : RÉPARTITION DES VOLUMES
# ============================================================================
st.header("📦 Répartition des volumes")

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
        y=-rapport['vol_vente_spot_mwh'],  # Négatif pour vers le bas
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
    
    st.plotly_chart(fig_vol, width='stretch')

with col2:
    # Répartition globale en camembert
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
    
    st.plotly_chart(fig_pie, width='stretch')

st.markdown("---")

# ============================================================================
# SECTION 2 : RÉPARTITION DES COÛTS
# ============================================================================
st.header("💰 Répartition des coûts")

col1, col2 = st.columns([2, 1])

with col1:
    # Graphique empilé coûts mensuels
    fig_cout = go.Figure()
    
    fig_cout.add_trace(go.Bar(
        name='Couverture (Base+Peak)',
        x=rapport['mois'],
        y=rapport['cout_couverture'],
        marker_color='#2E86AB',
        text=rapport['cout_couverture'].apply(lambda x: f"{x/1000:.0f}k€"),
        textposition='inside'
    ))
    
    fig_cout.add_trace(go.Bar(
        name='Achat Spot',
        x=rapport['mois'],
        y=rapport['cout_achat_spot'],
        marker_color='#F18F01',
        text=rapport['cout_achat_spot'].apply(lambda x: f"{x/1000:.0f}k€" if x > 0 else ""),
        textposition='inside'
    ))
    
    fig_cout.add_trace(go.Bar(
        name='Crédit Vente Spot',
        x=rapport['mois'],
        y=-rapport['credit_vente_spot'],
        marker_color='#27AE60',
        text=rapport['credit_vente_spot'].apply(lambda x: f"-{x/1000:.0f}k€" if x > 0 else ""),
        textposition='inside'
    ))
    
    fig_cout.update_layout(
        barmode='relative',
        title='Coûts mensuels par composante',
        xaxis_title='Mois',
        yaxis_title='Coût (€)',
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_cout, width='stretch')

with col2:
    # KPIs coûts
    st.markdown("### Totaux")
    
    total_cout_couv = rapport['cout_couverture'].sum()
    total_cout_achat = rapport['cout_achat_spot'].sum()
    total_credit_vente = rapport['credit_vente_spot'].sum()
    
    st.metric("Couverture", f"{total_cout_couv:,.0f} €", 
              delta=f"{total_cout_couv/total_cout*100:.1f}%")
    
    st.metric("Achat Spot", f"{total_cout_achat:,.0f} €",
              delta=f"{total_cout_achat/total_cout*100:.1f}%")
    
    st.metric("Crédit Vente", f"{total_credit_vente:,.0f} €",
              delta=f"-{total_credit_vente/total_cout*100:.1f}%",
              delta_color="normal")

st.markdown("---")

# ============================================================================
# SECTION 3 : ANALYSE DES PRIX
# ============================================================================
st.header("📈 Analyse des prix")

col1, col2 = st.columns(2)

with col1:
    # Prix moyens mensuels
    rapport['prix_achat_spot_moy'] = np.where(
        rapport['vol_achat_spot_mwh'] > 0,
        rapport['cout_achat_spot'] / rapport['vol_achat_spot_mwh'],
        0
    )
    
    rapport['prix_vente_spot_moy'] = np.where(
        rapport['vol_vente_spot_mwh'] > 0,
        rapport['credit_vente_spot'] / rapport['vol_vente_spot_mwh'],
        0
    )
    
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
    
    st.plotly_chart(fig_prix, width='stretch')

with col2:
    # Taux de couverture mensuel
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
    
    st.plotly_chart(fig_taux, width='stretch')

st.markdown("---")

# ============================================================================
# SECTION 4 : TOP INSIGHTS
# ============================================================================
st.header("💡 Points d'attention")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🔴 Mois le plus coûteux")
    mois_max = rapport.loc[rapport['cout_total_eur'].idxmax()]
    st.markdown(f"**{mois_max['mois']}**")
    st.metric("Coût", f"{mois_max['cout_total_eur']:,.0f} €")
    st.metric("Prix moyen", f"{mois_max['prix_moyen']:.2f} €/MWh")

with col2:
    st.markdown("### 📊 Plus d'achats spot")
    mois_spot = rapport.loc[rapport['vol_achat_spot_mwh'].idxmax()]
    st.markdown(f"**{mois_spot['mois']}**")
    st.metric("Volume spot", f"{mois_spot['vol_achat_spot_mwh']:,.0f} MWh")
    pct_spot = mois_spot['vol_achat_spot_mwh'] / mois_spot['conso_reelle_kw'] * 100
    st.metric("% du total", f"{pct_spot:.1f}%")

with col3:
    st.markdown("### 💰 Meilleure couverture")
    mois_cov = rapport.loc[rapport['taux_couverture'].idxmax()]
    st.markdown(f"**{mois_cov['mois']}**")
    st.metric("Taux couverture", f"{mois_cov['taux_couverture']:.1f}%")
    st.metric("Exposition spot", f"{100-mois_cov['taux_couverture']:.1f}%")

st.markdown("---")

# Export
st.subheader("📥 Export des données")

csv = rapport.to_csv(index=False).encode('utf-8')
st.download_button(
    "Télécharger le rapport mensuel (CSV)",
    csv,
    "rapport_mensuel.csv",
    "text/csv",
    use_container_width=True
)
