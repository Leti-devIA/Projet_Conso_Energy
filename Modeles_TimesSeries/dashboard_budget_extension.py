"""
Extension budgétaire pour le dashboard de prédictions énergétiques.
À intégrer dans le dashboard principal.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from budget_helper import BudgetCalculator, charger_prix_spot, formater_montant


def section_budget_simulator(df_predictions, df_prix):
    """
    Section complète pour le simulateur budgétaire.

    Args:
        df_predictions: DataFrame des prédictions avec colonnes [datetime, puissance_kw_pred]
        df_prix: DataFrame des prix spot
    """
    st.header("💰 Simulateur Budgétaire")

    st.markdown("""
    Cette section vous permet de :
    - 📊 Visualiser l'évolution des coûts énergétiques
    - 🎯 Simuler l'impact de modifications (volumes, taxes, acheminement)
    - 📈 Comparer différents scénarios budgétaires
    - 🔍 Identifier les périodes les plus coûteuses
    """)

    # Initialiser le calculateur
    calculator = BudgetCalculator(df_prix)

    # Enrichir les prédictions avec les prix
    df_enrichi = calculator.enrichir_predictions(df_predictions)

    # Vérifier si on a des prix pour toutes les dates
    dates_sans_prix = df_enrichi[df_enrichi['prix_spot_eur_mwh'].isna()]
    if len(dates_sans_prix) > 0:
        st.warning(f"⚠️ {len(dates_sans_prix)} heures sans prix spot disponible ({len(dates_sans_prix)/len(df_enrichi)*100:.1f}%)")

        with st.expander("Voir les périodes sans prix"):
            st.write(f"Première date sans prix : {dates_sans_prix['datetime'].min()}")
            st.write(f"Dernière date sans prix : {dates_sans_prix['datetime'].max()}")

    # Créer des onglets pour les différentes vues
    tab_synthese, tab_simulateur, tab_analyse, tab_scenarios = st.tabs([
        "📊 Vue d'ensemble",
        "⚙️ Simulateur",
        "🔍 Analyse détaillée",
        "📋 Comparaison de scénarios"
    ])

    # ========================================================================
    # TAB 1 : VUE D'ENSEMBLE
    # ========================================================================
    with tab_synthese:
        render_vue_ensemble(df_enrichi, calculator)

    # ========================================================================
    # TAB 2 : SIMULATEUR
    # ========================================================================
    with tab_simulateur:
        render_simulateur(df_enrichi, calculator)

    # ========================================================================
    # TAB 3 : ANALYSE DÉTAILLÉE
    # ========================================================================
    with tab_analyse:
        render_analyse_detaillee(df_enrichi, calculator)

    # ========================================================================
    # TAB 4 : COMPARAISON DE SCÉNARIOS
    # ========================================================================
    with tab_scenarios:
        render_comparaison_scenarios(df_enrichi, calculator)


def render_vue_ensemble(df_enrichi, calculator):
    """Rendu de la vue d'ensemble budgétaire."""
    st.subheader("Vue d'ensemble du budget")

    # Calculer le budget de référence (sans ajustements)
    df_base = calculator.calculer_cout_avec_parametres(
        df_enrichi,
        tarif_acheminement_eur_kwh=0.05,  # Valeur par défaut TURPE
        taux_taxe_pct=20.0  # TVA + autres taxes
    )

    # KPIs principaux
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        energie_totale = df_base['puissance_ajustee_kw'].sum() / 1000  # MWh
        st.metric(
            "Énergie Totale",
            f"{energie_totale:,.0f} MWh".replace(',', ' ')
        )

    with col2:
        cout_total = df_base['cout_total_eur'].sum()
        st.metric(
            "Coût Total",
            formater_montant(cout_total)
        )

    with col3:
        prix_moyen = (df_base['cout_energie_eur'].sum() / energie_totale)
        st.metric(
            "Prix Moyen Pondéré",
            f"{prix_moyen:.2f} €/MWh"
        )

    with col4:
        prix_median = df_base['prix_spot_eur_mwh'].median()
        st.metric(
            "Prix Spot Médian",
            f"{prix_median:.2f} €/MWh"
        )

    st.markdown("---")

    # Répartition des coûts
    col1, col2 = st.columns([2, 1])

    with col1:
        # Graphique temporel combiné : Puissance + Prix
        fig_combined = go.Figure()

        # Agréger par jour pour plus de lisibilité
        df_daily = df_base.copy()
        df_daily['date'] = df_daily['datetime'].dt.date
        df_daily_agg = df_daily.groupby('date').agg({
            'puissance_ajustee_kw': 'mean',
            'prix_spot_eur_mwh': 'mean',
            'cout_total_eur': 'sum'
        }).reset_index()

        # Axe 1 : Puissance
        fig_combined.add_trace(go.Scatter(
            x=df_daily_agg['date'],
            y=df_daily_agg['puissance_ajustee_kw'],
            name='Puissance moyenne (kW)',
            yaxis='y1',
            line=dict(color='#1f77b4', width=2),
            fill='tonexty',
            fillcolor='rgba(31, 119, 180, 0.2)'
        ))

        # Axe 2 : Prix spot
        fig_combined.add_trace(go.Scatter(
            x=df_daily_agg['date'],
            y=df_daily_agg['prix_spot_eur_mwh'],
            name='Prix spot (€/MWh)',
            yaxis='y2',
            line=dict(color='#ff7f0e', width=2, dash='dot')
        ))

        fig_combined.update_layout(
            title='Évolution de la consommation et des prix',
            xaxis=dict(title='Date'),
            yaxis=dict(
                title='Puissance (kW)',
                side='left',
                showgrid=True
            ),
            yaxis2=dict(
                title='Prix (€/MWh)',
                side='right',
                overlaying='y',
                showgrid=False
            ),
            height=400,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig_combined, width='stretch')

    with col2:
        # Camembert de répartition des coûts
        repartition = {
            'Énergie': df_base['cout_energie_eur'].sum(),
            'Acheminement': df_base['cout_acheminement_eur'].sum(),
            'Taxes': df_base['cout_taxe_eur'].sum()
        }

        fig_pie = go.Figure(data=[go.Pie(
            labels=list(repartition.keys()),
            values=list(repartition.values()),
            hole=0.4,
            marker=dict(colors=['#1f77b4', '#ff7f0e', '#2ca02c'])
        )])

        fig_pie.update_layout(
            title='Répartition des coûts',
            height=400,
            showlegend=True
        )

        st.plotly_chart(fig_pie, width='stretch')

    # Tableau de synthèse annuelle
    st.markdown("### Synthèse annuelle")

    df_base['annee'] = df_base['datetime'].dt.year
    resume_annuel = calculator.resumer_budget(df_base, groupby='annee')

    # Formater pour l'affichage
    resume_display = resume_annuel.copy()
    resume_display.index.name = 'Année'

    # Colonnes à afficher avec renommage
    colonnes_affichage = {
        'energie_totale_mwh': 'Énergie (MWh)',
        'cout_energie_eur': 'Coût Énergie (€)',
        'cout_acheminement_eur': 'Coût Acheminement (€)',
        'cout_taxe_eur': 'Taxes (€)',
        'cout_total_eur': 'Coût Total (€)',
        'prix_moyen_pondere_eur_mwh': 'Prix Moyen (€/MWh)'
    }

    resume_display = resume_display[list(colonnes_affichage.keys())].rename(columns=colonnes_affichage)

    # Formater les nombres
    st.dataframe(
        resume_display.style.format({
            'Énergie (MWh)': '{:,.0f}',
            'Coût Énergie (€)': '{:,.0f}',
            'Coût Acheminement (€)': '{:,.0f}',
            'Taxes (€)': '{:,.0f}',
            'Coût Total (€)': '{:,.0f}',
            'Prix Moyen (€/MWh)': '{:.2f}'
        }),
        width='stretch'
    )


def render_simulateur(df_enrichi, calculator):
    """Rendu du simulateur interactif."""
    st.subheader("Simulateur d'impact budgétaire")

    st.markdown("""
    Ajustez les paramètres ci-dessous pour voir leur impact sur le budget total.
    Les résultats sont calculés en temps réel.
    """)

    # Paramètres de référence
    st.markdown("### 🎯 Paramètres de référence")
    col1, col2 = st.columns(2)

    with col1:
        tarif_acheminement_ref = st.number_input(
            "Tarif acheminement de référence (€/kWh)",
            min_value=0.0,
            max_value=0.2,
            value=0.05,
            step=0.001,
            format="%.3f",
            help="Tarif TURPE moyen"
        )

        taux_taxe_ref = st.number_input(
            "Taux de taxe de référence (%)",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=1.0,
            help="TVA + CSPE + autres taxes"
        )

    with col2:
        st.info("""
        💡 **Valeurs par défaut**
        - **TURPE** : ~0.05 €/kWh
        - **Taxes** : ~20% (TVA 20% + CSPE)
        """)

    # Calculer le budget de référence
    df_reference = calculator.calculer_cout_avec_parametres(
        df_enrichi,
        tarif_acheminement_eur_kwh=tarif_acheminement_ref,
        taux_taxe_pct=taux_taxe_ref
    )

    budget_reference = df_reference['cout_total_eur'].sum()

    st.markdown("---")
    st.markdown("### 📋 Contrats d'achat")

    utiliser_contrat = st.checkbox(
        "Utiliser des volumes d'achat contractuels",
        value=False,
        key="contrat_simulateur",  # Key unique
        help="Active la formule : Coût = volumes_achetés × prix_achetés + prix_spot × (conso_réelle - volumes_achetés)"
    )

    volumes_achetes_kw = None
    prix_achetes_eur_mwh = None

    if utiliser_contrat:
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            type_contrat = st.radio(
                "Type de contrat",
                ["Volume fixe", "% de la consommation"],
                index=0,
                key="type_contrat_simulateur",
                help="Définir comment sont spécifiés les volumes achetés"
            )

        with col_c2:
            if type_contrat == "Volume fixe":
                volumes_achetes_kw = st.number_input(
                    "Volume acheté constant (kW)",
                    min_value=0.0,
                    max_value=2000.0,
                    value=300.0,
                    step=10.0,
                    key="volume_fixe_simulateur",
                    help="Volume d'achat constant à chaque heure"
                )
            else:  # % de la consommation
                pct_achat = st.number_input(
                    "Pourcentage acheté (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=80.0,
                    step=5.0,
                    key="pct_achat_simulateur",
                    help="% de la consommation prédite"
                )
                # On utilisera ce % plus tard dans le calcul
                volumes_achetes_kw = None  # Sera calculé dynamiquement

        with col_c3:
            prix_achetes_eur_mwh = st.number_input(
                "Prix d'achat contractuel (€/MWh)",
                min_value=0.0,
                max_value=200.0,
                value=45.0,
                step=1.0,
                key="prix_achetes_simulateur",
                help="Prix fixe du contrat d'achat"
            )

        st.info("""
        📊 **Formule appliquée** :
        - **Partie contractuelle** : `volumes_achetés × prix_achetés`
        - **Écart au spot** : `(consommation_réelle - volumes_achetés) × prix_spot`
        - Si consommation > volumes achetés → achat complémentaire au spot
        - Si consommation < volumes achetés → revente au spot
        """)

        # Recalculer le budget de référence avec contrat
        if type_contrat == "% de la consommation":
            # Calculer les volumes basés sur le % de la consommation prédite
            volumes_ref = df_enrichi['puissance_kw_pred'] * pct_achat / 100
            df_reference = calculator.calculer_cout_avec_parametres(
                df_enrichi,
                tarif_acheminement_eur_kwh=tarif_acheminement_ref,
                taux_taxe_pct=taux_taxe_ref,
                volumes_achetes_kw=volumes_ref,
                prix_achetes_eur_mwh=prix_achetes_eur_mwh
            )
        else:
            df_reference = calculator.calculer_cout_avec_parametres(
                df_enrichi,
                tarif_acheminement_eur_kwh=tarif_acheminement_ref,
                taux_taxe_pct=taux_taxe_ref,
                volumes_achetes_kw=volumes_achetes_kw,
                prix_achetes_eur_mwh=prix_achetes_eur_mwh
            )

        budget_reference = df_reference['cout_total_eur'].sum()

    st.markdown("---")
    st.markdown("### 📋 Contrats d'achat")

    utiliser_contrat = st.checkbox(
        "Utiliser des volumes d'achat contractuels",
        value=False,
        help="Active la formule : Coût = volumes_achetés × prix_achetés + prix_spot × (conso_réelle - volumes_achetés)"
    )

    volumes_achetes_kw = None
    prix_achetes_eur_mwh = None

    if utiliser_contrat:
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            type_contrat = st.radio(
                "Type de contrat",
                ["Volume fixe", "Profil horaire", "% de la consommation"],
                index=0,
                help="Définir comment sont spécifiés les volumes achetés"
            )

        with col_c2:
            if type_contrat == "Volume fixe":
                volumes_achetes_kw = st.number_input(
                    "Volume acheté constant (kW)",
                    min_value=0.0,
                    max_value=2000.0,
                    value=300.0,
                    step=10.0,
                    help="Volume d'achat constant à chaque heure"
                )
            elif type_contrat == "% de la consommation":
                pct_achat = st.number_input(
                    "Pourcentage acheté (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=80.0,
                    step=5.0,
                    help="% de la consommation prédite"
                )
                # Calculer après ajustements
                volumes_achetes_kw = pct_achat  # Sera traité plus tard
            else:
                st.info("💡 Uploadez un fichier CSV avec colonnes : datetime, volume_achete_kw")
                # Pour simplifier, on garde None pour l'instant

        with col_c3:
            prix_achetes_eur_mwh = st.number_input(
                "Prix d'achat contractuel (€/MWh)",
                min_value=0.0,
                max_value=200.0,
                value=45.0,
                step=1.0,
                help="Prix fixe du contrat d'achat"
            )

        st.info("""
        📊 **Formule appliquée** :
        - **Partie contractuelle** : `volumes_achetés × prix_achetés`
        - **Écart au spot** : `(consommation_réelle - volumes_achetés) × prix_spot`
        - Si consommation > volumes achetés → achat complémentaire au spot
        - Si consommation < volumes achetés → revente au spot
        """)

    st.markdown("---")
    st.markdown("### 🔧 Simulations")

    # Créer 3 colonnes pour les différents types d'ajustements
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 📊 Volumes")
        ajustement_kw = st.number_input(
            "Ajustement fixe (kW)",
            min_value=-1000.0,
            max_value=1000.0,
            value=0.0,
            step=10.0,
            help="Ajouter/retirer une puissance constante"
        )

        ajustement_pct = st.number_input(
            "Ajustement proportionnel (%)",
            min_value=-50.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            help="Augmenter/réduire la consommation en %"
        )

    with col2:
        st.markdown("#### 💶 Prix et Acheminement")
        surcout_prix = st.number_input(
            "Surcoût prix spot (€/MWh)",
            min_value=-50.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            help="Ajouter un surcoût au prix de l'énergie"
        )

        ajustement_turpe = st.number_input(
            "Ajustement TURPE (€/kWh)",
            min_value=-0.05,
            max_value=0.1,
            value=0.0,
            step=0.001,
            format="%.3f",
            help="Modifier le tarif d'acheminement"
        )

    with col3:
        st.markdown("#### 📈 Fiscalité")
        ajustement_taxe = st.number_input(
            "Ajustement taxes (%)",
            min_value=-20.0,
            max_value=50.0,
            value=0.0,
            step=1.0,
            help="Modifier le taux de taxe"
        )

    # Calculer le budget simulé
    # Gérer le cas des volumes achetés en % de la consommation
    volumes_simule = None
    if utiliser_contrat:
        if type_contrat == "% de la consommation":
            # Calculer les volumes ajustés
            conso_ajustee = (df_enrichi['puissance_kw_pred'] + ajustement_kw) * (1 + ajustement_pct / 100)
            volumes_simule = conso_ajustee * pct_achat / 100
        else:
            volumes_simule = volumes_achetes_kw

    df_simule = calculator.calculer_cout_avec_parametres(
        df_enrichi,
        ajustement_volume_kw=ajustement_kw,
        ajustement_volume_pct=ajustement_pct,
        tarif_acheminement_eur_kwh=tarif_acheminement_ref + ajustement_turpe,
        taux_taxe_pct=taux_taxe_ref + ajustement_taxe,
        surcout_fixe_eur_mwh=surcout_prix,
        volumes_achetes_kw=volumes_simule,
        prix_achetes_eur_mwh=prix_achetes_eur_mwh if utiliser_contrat else None
    )

    budget_simule = df_simule['cout_total_eur'].sum()
    impact_absolu = budget_simule - budget_reference
    impact_pct = (impact_absolu / budget_reference * 100) if budget_reference > 0 else 0

    # Affichage des résultats
    st.markdown("---")
    st.markdown("### 📊 Résultats de la simulation")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Budget de référence",
            formater_montant(budget_reference)
        )

    with col2:
        st.metric(
            "Budget simulé",
            formater_montant(budget_simule),
            delta=formater_montant(impact_absolu),
            delta_color="inverse"
        )

    with col3:
        st.metric(
            "Impact relatif",
            f"{impact_pct:+.2f}%",
            delta=f"{impact_absolu:+,.0f} €".replace(',', ' '),
            delta_color="inverse"
        )

    # Graphique de comparaison détaillée
    st.markdown("#### Décomposition de l'impact")

    decomposition_ref = {
        'Énergie': df_reference['cout_energie_eur'].sum(),
        'Acheminement': df_reference['cout_acheminement_eur'].sum(),
        'Taxes': df_reference['cout_taxe_eur'].sum()
    }

    decomposition_sim = {
        'Énergie': df_simule['cout_energie_eur'].sum(),
        'Acheminement': df_simule['cout_acheminement_eur'].sum(),
        'Taxes': df_simule['cout_taxe_eur'].sum()
    }

    fig_comparison = go.Figure()

    categories = list(decomposition_ref.keys())

    fig_comparison.add_trace(go.Bar(
        name='Référence',
        x=categories,
        y=list(decomposition_ref.values()),
        marker_color='#1f77b4',
        text=[formater_montant(v) for v in decomposition_ref.values()],
        textposition='outside'
    ))

    fig_comparison.add_trace(go.Bar(
        name='Simulé',
        x=categories,
        y=list(decomposition_sim.values()),
        marker_color='#ff7f0e',
        text=[formater_montant(v) for v in decomposition_sim.values()],
        textposition='outside'
    ))

    fig_comparison.update_layout(
        title='Comparaison détaillée des coûts',
        xaxis_title='Composante',
        yaxis_title='Coût (€)',
        barmode='group',
        height=400
    )

    st.plotly_chart(fig_comparison, width='stretch')

    # Si on utilise des contrats, afficher l'analyse de l'écart
    if utiliser_contrat and 'ecart_kw' in df_simule.columns:
        st.markdown("#### Analyse de l'écart achat/consommation")

        col_e1, col_e2, col_e3 = st.columns(3)

        # Statistiques sur l'écart
        ecart_positif = df_simule[df_simule['ecart_kw'] > 0]
        ecart_negatif = df_simule[df_simule['ecart_kw'] < 0]

        with col_e1:
            nb_heures_achat = len(ecart_positif)
            pct_achat = nb_heures_achat / len(df_simule) * 100
            cout_achat_spot = ecart_positif['cout_ecart_spot_eur'].sum() if len(ecart_positif) > 0 else 0

            st.metric(
                "Heures d'achat spot",
                f"{nb_heures_achat} h ({pct_achat:.1f}%)",
                delta=f"Coût: {formater_montant(cout_achat_spot)}",
                delta_color="inverse"
            )

        with col_e2:
            nb_heures_vente = len(ecart_negatif)
            pct_vente = nb_heures_vente / len(df_simule) * 100
            gain_vente_spot = abs(ecart_negatif['cout_ecart_spot_eur'].sum()) if len(ecart_negatif) > 0 else 0

            st.metric(
                "Heures de revente spot",
                f"{nb_heures_vente} h ({pct_vente:.1f}%)",
                delta=f"Gain: {formater_montant(gain_vente_spot)}",
                delta_color="normal"
            )

        with col_e3:
            ecart_moyen = df_simule['ecart_kw'].mean()
            st.metric(
                "Écart moyen",
                f"{ecart_moyen:+.1f} kW",
                delta="Sur-consommation" if ecart_moyen > 0 else "Sous-consommation"
            )

        # Graphique de l'écart dans le temps (agrégé par jour)
        df_ecart_daily = df_simule.copy()
        df_ecart_daily['date'] = df_ecart_daily['datetime'].dt.date
        df_ecart_agg = df_ecart_daily.groupby('date').agg({
            'ecart_kw': 'mean',
            'volumes_achetes_kw': 'mean',
            'conso_reelle_kw': 'mean'
        }).reset_index()

        fig_ecart = go.Figure()

        # Zone d'écart
        fig_ecart.add_trace(go.Scatter(
            x=df_ecart_agg['date'],
            y=df_ecart_agg['ecart_kw'],
            fill='tozeroy',
            name='Écart (conso - achat)',
            fillcolor='rgba(255, 127, 14, 0.3)',
            line=dict(color='#ff7f0e', width=2),
            hovertemplate='%{x}<br>Écart: %{y:.1f} kW<extra></extra>'
        ))

        # Ligne zéro
        fig_ecart.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig_ecart.update_layout(
            title="Écart entre consommation réelle et volumes achetés (moyenne journalière)",
            xaxis_title="Date",
            yaxis_title="Écart (kW)",
            height=300,
            hovermode='x unified'
        )

        st.plotly_chart(fig_ecart, width='stretch')

        st.info("""
        💡 **Interprétation** :
        - **Écart positif (orange au-dessus de 0)** : Consommation > Achats → Achat complémentaire au prix spot
        - **Écart négatif (orange au-dessous de 0)** : Consommation < Achats → Revente au prix spot
        """)


def render_analyse_detaillee(df_enrichi, calculator):
    """Rendu de l'analyse détaillée."""
    st.subheader("Analyse détaillée")

    # Calculer avec paramètres par défaut
    df_analyse = calculator.calculer_cout_avec_parametres(
        df_enrichi,
        tarif_acheminement_eur_kwh=0.05,
        taux_taxe_pct=20.0
    )

    # Ajouter des colonnes temporelles
    df_analyse['annee'] = df_analyse['datetime'].dt.year
    df_analyse['mois'] = df_analyse['datetime'].dt.month
    df_analyse['heure'] = df_analyse['datetime'].dt.hour
    df_analyse['jour_semaine'] = df_analyse['datetime'].dt.dayofweek

    # Choix de la granularité
    granularite = st.selectbox(
        "Sélectionner la granularité d'analyse",
        ["Mensuelle", "Horaire", "Jour de la semaine"],
        index=0
    )

    if granularite == "Mensuelle":
        # Heat map mensuel : Mois x Année
        df_analyse['mois_nom'] = df_analyse['datetime'].dt.strftime('%b')

        pivot_data = df_analyse.groupby(['annee', 'mois_nom', 'mois'])['cout_total_eur'].sum().reset_index()
        pivot_table = pivot_data.pivot(index='mois_nom', columns='annee', values='cout_total_eur')

        # Ordonner les mois correctement
        mois_ordre = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        pivot_table = pivot_table.reindex(mois_ordre)

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=pivot_table.values,
            x=pivot_table.columns,
            y=pivot_table.index,
            colorscale='RdYlGn_r',
            text=pivot_table.values,
            texttemplate='%{text:,.0f}€',
            textfont={"size": 10},
            colorbar=dict(title="Coût (€)")
        ))

        fig_heatmap.update_layout(
            title='Heat Map des coûts mensuels',
            xaxis_title='Année',
            yaxis_title='Mois',
            height=500
        )

        st.plotly_chart(fig_heatmap, width='stretch')

    elif granularite == "Horaire":
        # Heat map horaire : Heure x Jour de la semaine
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

        pivot_horaire = df_analyse.groupby(['jour_semaine', 'heure'])['cout_total_eur'].mean().reset_index()
        pivot_table_horaire = pivot_horaire.pivot(index='heure', columns='jour_semaine', values='cout_total_eur')
        pivot_table_horaire.columns = [jours[i] for i in pivot_table_horaire.columns]

        fig_horaire = go.Figure(data=go.Heatmap(
            z=pivot_table_horaire.values,
            x=pivot_table_horaire.columns,
            y=pivot_table_horaire.index,
            colorscale='RdYlGn_r',
            text=pivot_table_horaire.values,
            texttemplate='%{text:.1f}€',
            textfont={"size": 8},
            colorbar=dict(title="Coût moyen (€/h)")
        ))

        fig_horaire.update_layout(
            title='Heat Map des coûts horaires moyens',
            xaxis_title='Jour de la semaine',
            yaxis_title='Heure',
            height=600
        )

        st.plotly_chart(fig_horaire, width='stretch')

    else:  # Jour de la semaine
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

        cout_par_jour = df_analyse.groupby('jour_semaine')['cout_total_eur'].sum().reset_index()
        cout_par_jour['jour_nom'] = cout_par_jour['jour_semaine'].apply(lambda x: jours[x])

        fig_jours = go.Figure(data=go.Bar(
            x=cout_par_jour['jour_nom'],
            y=cout_par_jour['cout_total_eur'],
            marker_color='#1f77b4',
            text=cout_par_jour['cout_total_eur'],
            texttemplate='%{text:,.0f}€',
            textposition='outside'
        ))

        fig_jours.update_layout(
            title='Coût total par jour de la semaine',
            xaxis_title='Jour',
            yaxis_title='Coût total (€)',
            height=400
        )

        st.plotly_chart(fig_jours, width='stretch')

    # Top heures les plus coûteuses
    st.markdown("### 🔝 Top 20 heures les plus coûteuses")

    top_heures = calculator.identifier_heures_couteuses(df_analyse, top_n=20)

    # Formater pour l'affichage
    top_heures_display = top_heures.copy()
    top_heures_display['datetime'] = top_heures_display['datetime'].dt.strftime('%Y-%m-%d %Hh')
    top_heures_display.columns = ['Date/Heure', 'Puissance (kW)', 'Prix spot (€/MWh)', 'Coût (€)', 'Contribution (%)']

    st.dataframe(
        top_heures_display.style.format({
            'Puissance (kW)': '{:.1f}',
            'Prix spot (€/MWh)': '{:.2f}',
            'Coût (€)': '{:,.2f}',
            'Contribution (%)': '{:.2f}'
        }),
        width='stretch',
        hide_index=True
    )

    contribution_top20 = top_heures['contribution_pct'].sum()
    st.info(f"💡 Ces 20 heures représentent **{contribution_top20:.2f}%** du coût total")


def render_comparaison_scenarios(df_enrichi, calculator):
    """Rendu de la comparaison de scénarios."""
    st.subheader("Comparaison de scénarios budgétaires")

    st.markdown("""
    Définissez plusieurs scénarios pour comparer leurs impacts financiers.
    """)

    # Scénarios prédéfinis
    scenarios_predefinis = {
        "Base": {
            'nom': 'Scénario de base',
            'ajustement_volume_kw': 0,
            'ajustement_volume_pct': 0,
            'tarif_acheminement_eur_kwh': 0.05,
            'taux_taxe_pct': 20.0,
            'surcout_fixe_eur_mwh': 0.0
        },
        "Optimiste": {
            'nom': 'Baisse des coûts',
            'ajustement_volume_kw': 0,
            'ajustement_volume_pct': -10,
            'tarif_acheminement_eur_kwh': 0.045,
            'taux_taxe_pct': 18.0,
            'surcout_fixe_eur_mwh': -5.0
        },
        "Pessimiste": {
            'nom': 'Hausse des coûts',
            'ajustement_volume_kw': 0,
            'ajustement_volume_pct': 10,
            'tarif_acheminement_eur_kwh': 0.055,
            'taux_taxe_pct': 22.0,
            'surcout_fixe_eur_mwh': 10.0
        },
        "Expansion": {
            'nom': 'Nouveau site +500kW',
            'ajustement_volume_kw': 500,
            'ajustement_volume_pct': 0,
            'tarif_acheminement_eur_kwh': 0.05,
            'taux_taxe_pct': 20.0,
            'surcout_fixe_eur_mwh': 0.0
        }
    }

    # Sélection des scénarios à comparer
    scenarios_selectionnes = st.multiselect(
        "Sélectionner les scénarios à comparer",
        list(scenarios_predefinis.keys()),
        default=["Base", "Optimiste", "Pessimiste"]
    )

    if scenarios_selectionnes:
        # Préparer la liste des scénarios
        scenarios_a_comparer = [scenarios_predefinis[s] for s in scenarios_selectionnes]

        # Calculer les résultats
        resultats = calculator.calculer_impact_scenarios(df_enrichi, scenarios_a_comparer)

        # Affichage en graphique
        fig_scenarios = go.Figure()

        scenarios_noms = resultats['scenario'].tolist()

        # Empiler les coûts
        fig_scenarios.add_trace(go.Bar(
            name='Énergie',
            x=scenarios_noms,
            y=resultats['cout_energie_eur'],
            marker_color='#1f77b4'
        ))

        fig_scenarios.add_trace(go.Bar(
            name='Acheminement',
            x=scenarios_noms,
            y=resultats['cout_acheminement_eur'],
            marker_color='#ff7f0e'
        ))

        fig_scenarios.add_trace(go.Bar(
            name='Taxes',
            x=scenarios_noms,
            y=resultats['cout_taxe_eur'],
            marker_color='#2ca02c'
        ))

        fig_scenarios.update_layout(
            title='Comparaison des coûts par scénario',
            xaxis_title='Scénario',
            yaxis_title='Coût (€)',
            barmode='stack',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig_scenarios, width='stretch')

        # Tableau comparatif
        st.markdown("### Tableau comparatif")

        resultats_display = resultats.copy()

        # Calculer les écarts par rapport au scénario de base
        if "Base" in scenarios_selectionnes:
            idx_base = scenarios_selectionnes.index("Base")
            cout_base = resultats.iloc[idx_base]['cout_total_eur']

            resultats_display['ecart_vs_base_eur'] = resultats_display['cout_total_eur'] - cout_base
            resultats_display['ecart_vs_base_pct'] = (
                (resultats_display['cout_total_eur'] - cout_base) / cout_base * 100
            )

        # Renommer les colonnes pour l'affichage
        colonnes_affichage = {
            'scenario': 'Scénario',
            'energie_totale_mwh': 'Énergie (MWh)',
            'cout_energie_eur': 'Coût Énergie (€)',
            'cout_acheminement_eur': 'Acheminement (€)',
            'cout_taxe_eur': 'Taxes (€)',
            'cout_total_eur': 'Coût Total (€)',
            'ecart_vs_base_eur': 'Écart vs Base (€)',
            'ecart_vs_base_pct': 'Écart vs Base (%)'
        }

        colonnes_a_afficher = [c for c in colonnes_affichage.keys() if c in resultats_display.columns]
        resultats_display = resultats_display[colonnes_a_afficher].rename(columns=colonnes_affichage)

        st.dataframe(
            resultats_display.style.format({
                'Énergie (MWh)': '{:,.0f}',
                'Coût Énergie (€)': '{:,.0f}',
                'Acheminement (€)': '{:,.0f}',
                'Taxes (€)': '{:,.0f}',
                'Coût Total (€)': '{:,.0f}',
                'Écart vs Base (€)': '{:+,.0f}',
                'Écart vs Base (%)': '{:+.2f}'
            }),
            width='stretch',
            hide_index=True
        )
    else:
        st.info("Sélectionnez au moins un scénario pour voir les résultats")

    # Option pour créer un scénario personnalisé
    with st.expander("➕ Créer un scénario personnalisé"):
        st.markdown("Définissez vos propres paramètres :")

        col1, col2 = st.columns(2)

        with col1:
            custom_nom = st.text_input("Nom du scénario", value="Mon scénario")
            custom_volume_kw = st.number_input("Ajustement volume (kW)", value=0.0, step=10.0)
            custom_volume_pct = st.number_input("Ajustement volume (%)", value=0.0, step=1.0)

        with col2:
            custom_turpe = st.number_input("TURPE (€/kWh)", value=0.05, step=0.001, format="%.3f")
            custom_taxe = st.number_input("Taxes (%)", value=20.0, step=1.0)
            custom_surcout = st.number_input("Surcoût prix (€/MWh)", value=0.0, step=1.0)

        if st.button("Calculer mon scénario"):
            scenario_custom = [{
                'nom': custom_nom,
                'ajustement_volume_kw': custom_volume_kw,
                'ajustement_volume_pct': custom_volume_pct,
                'tarif_acheminement_eur_kwh': custom_turpe,
                'taux_taxe_pct': custom_taxe,
                'surcout_fixe_eur_mwh': custom_surcout
            }]

            resultat_custom = calculator.calculer_impact_scenarios(df_enrichi, scenario_custom)

            st.success(f"✅ Coût total pour '{custom_nom}' : {formater_montant(resultat_custom.iloc[0]['cout_total_eur'])}")
            st.dataframe(resultat_custom, width='stretch', hide_index=True)
