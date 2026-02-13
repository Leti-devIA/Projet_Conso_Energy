"""
Module helper pour gérer les prix spot et les calculs budgétaires.
"""
import pandas as pd
import numpy as np
from datetime import datetime


class BudgetCalculator:
    """Classe pour gérer les calculs budgétaires avec les prix spot."""

    def __init__(self, df_prix):
        """
        Initialise le calculateur budgétaire.

        Args:
            df_prix: DataFrame avec les colonnes [periode, prix_base, type, date_deb, date_fin]
        """
        if not isinstance(df_prix, pd.DataFrame):
            raise TypeError(f"df_prix doit être un DataFrame, pas {type(df_prix)}")

        self.df_prix = df_prix.copy()
        # Convertir les dates en datetime
        self.df_prix['date_deb'] = pd.to_datetime(self.df_prix['date_deb'])
        self.df_prix['date_fin'] = pd.to_datetime(self.df_prix['date_fin'])

        # Hiérarchie de priorité pour les types de prix
        self.hierarchie = {'mensuel': 1, 'trimestriel': 2, 'annuel': 3}
        self.df_prix['priorite'] = self.df_prix['type'].map(self.hierarchie)

    def get_prix_pour_date(self, date):
        """
        Récupère le prix spot le plus pertinent pour une date donnée.
        Priorité : mensuel > trimestriel > annuel

        Args:
            date: datetime ou Timestamp

        Returns:
            float: Prix en €/MWh ou None si non trouvé
        """
        # Filtrer les prix valides pour cette date
        prix_valides = self.df_prix[
            (self.df_prix['date_deb'] <= date) &
            (self.df_prix['date_fin'] >= date)
        ]

        if len(prix_valides) > 0:
            # Prendre le plus précis (priorité la plus faible)
            meilleur_prix = prix_valides.sort_values('priorite').iloc[0]
            # Retourner le prix en tant que float
            return float(meilleur_prix['prix_base'])
        else:
            return None

    def enrichir_predictions(self, df_predictions):
        """
        Enrichit les prédictions avec les prix spot et calculs de coût.

        Args:
            df_predictions: DataFrame avec colonnes [datetime, puissance_kw_pred]

        Returns:
            DataFrame enrichi avec colonnes supplémentaires
        """
        df_enrichi = df_predictions.copy()

        # Ajouter le prix spot
        df_enrichi['prix_spot_eur_mwh'] = df_enrichi['datetime'].apply(self.get_prix_pour_date)

        # Calculer le coût énergie (puissance en kW * prix en €/MWh / 1000 pour convertir en MWh)
        df_enrichi['cout_energie_eur'] = (
            df_enrichi['puissance_kw_pred'] *
            df_enrichi['prix_spot_eur_mwh'] / 1000
        )

        return df_enrichi

    def calculer_cout_avec_parametres(self, df_enrichi,
                                      ajustement_volume_kw=0,
                                      ajustement_volume_pct=0,
                                      tarif_acheminement_eur_kwh=0.0,
                                      taux_taxe_pct=0.0,
                                      surcout_fixe_eur_mwh=0.0,
                                      volumes_achetes_kw=None,
                                      prix_achetes_eur_mwh=None):
        """
        Calcule le coût total avec différents paramètres de simulation.

        Formule appliquée :
        Coût_heure = volumes_achetés * prix_achetés + prix_spot * (consommation_réelle - volumes_achetés)

        Args:
            df_enrichi: DataFrame enrichi avec prix spot
            ajustement_volume_kw: Ajustement fixe du volume en kW
            ajustement_volume_pct: Ajustement en % du volume
            tarif_acheminement_eur_kwh: Tarif d'acheminement en €/kWh
            taux_taxe_pct: Taux de taxe en %
            surcout_fixe_eur_mwh: Surcoût fixe en €/MWh
            volumes_achetes_kw: Volume d'achat contractuel en kW (constant ou Series)
            prix_achetes_eur_mwh: Prix d'achat contractuel en €/MWh (constant ou Series)

        Returns:
            DataFrame avec colonnes de coût détaillées
        """
        df_calcul = df_enrichi.copy()

        # Ajuster le volume de consommation réelle
        df_calcul['conso_reelle_kw'] = (
            df_calcul['puissance_kw_pred'] + ajustement_volume_kw
        ) * (1 + ajustement_volume_pct / 100)

        # Appliquer la formule de coût selon qu'on a des volumes achetés ou non
        if volumes_achetes_kw is not None and prix_achetes_eur_mwh is not None:
            # FORMULE COMPLÈTE : volumes achetés + écart au spot
            # Coût_heure = volumes_achetés * prix_achetés + prix_spot * (conso_réelle - volumes_achetés)

            # Gérer le cas où volumes_achetes_kw est un scalaire ou une Series
            if np.isscalar(volumes_achetes_kw):
                df_calcul['volumes_achetes_kw'] = volumes_achetes_kw
            else:
                df_calcul['volumes_achetes_kw'] = volumes_achetes_kw

            if np.isscalar(prix_achetes_eur_mwh):
                df_calcul['prix_achetes_eur_mwh'] = prix_achetes_eur_mwh
            else:
                df_calcul['prix_achetes_eur_mwh'] = prix_achetes_eur_mwh

            # Calcul de l'écart entre consommation et achat
            df_calcul['ecart_kw'] = df_calcul['conso_reelle_kw'] - df_calcul['volumes_achetes_kw']

            # Coût de la partie achetée à prix fixe
            df_calcul['cout_achat_contractuel_eur'] = (
                df_calcul['volumes_achetes_kw'] * df_calcul['prix_achetes_eur_mwh'] / 1000
            )

            # Coût de l'écart au prix spot
            prix_spot_ajuste = df_calcul['prix_spot_eur_mwh'] + surcout_fixe_eur_mwh
            df_calcul['cout_ecart_spot_eur'] = (
                df_calcul['ecart_kw'] * prix_spot_ajuste / 1000
            )

            # Coût total énergie = achat contractuel + écart spot
            df_calcul['cout_energie_eur'] = (
                df_calcul['cout_achat_contractuel_eur'] +
                df_calcul['cout_ecart_spot_eur']
            )

        else:
            # FORMULE SIMPLIFIÉE : tout au prix spot (mode par défaut)
            prix_spot_ajuste = df_calcul['prix_spot_eur_mwh'] + surcout_fixe_eur_mwh
            df_calcul['cout_energie_eur'] = (
                df_calcul['conso_reelle_kw'] * prix_spot_ajuste / 1000
            )

            # Pour cohérence, initialiser les colonnes à None
            df_calcul['volumes_achetes_kw'] = None
            df_calcul['prix_achetes_eur_mwh'] = None
            df_calcul['ecart_kw'] = None
            df_calcul['cout_achat_contractuel_eur'] = None
            df_calcul['cout_ecart_spot_eur'] = None

        # Coût acheminement (TURPE) - basé sur la consommation réelle
        df_calcul['cout_acheminement_eur'] = (
            df_calcul['conso_reelle_kw'] * tarif_acheminement_eur_kwh
        )

        # Coût avant taxes
        df_calcul['cout_avant_taxe_eur'] = (
            df_calcul['cout_energie_eur'] + df_calcul['cout_acheminement_eur']
        )

        # Taxes
        df_calcul['cout_taxe_eur'] = (
            df_calcul['cout_avant_taxe_eur'] * taux_taxe_pct / 100
        )

        # Coût total
        df_calcul['cout_total_eur'] = (
            df_calcul['cout_avant_taxe_eur'] + df_calcul['cout_taxe_eur']
        )

        # Renommer pour compatibilité avec le reste du code
        df_calcul['puissance_ajustee_kw'] = df_calcul['conso_reelle_kw']

        return df_calcul

    def resumer_budget(self, df_calcul, groupby='annee'):
        """
        Résume le budget par période (année, mois, etc.).

        Args:
            df_calcul: DataFrame avec coûts calculés
            groupby: Colonne de regroupement ('annee', 'mois', etc.)

        Returns:
            DataFrame résumé
        """
        if groupby not in df_calcul.columns:
            if groupby == 'annee':
                df_calcul['annee'] = df_calcul['datetime'].dt.year
            elif groupby == 'mois':
                df_calcul['mois'] = df_calcul['datetime'].dt.to_period('M')
            elif groupby == 'trimestre':
                df_calcul['trimestre'] = df_calcul['datetime'].dt.to_period('Q')

        resume = df_calcul.groupby(groupby).agg({
            'puissance_ajustee_kw': 'sum',
            'cout_energie_eur': 'sum',
            'cout_acheminement_eur': 'sum',
            'cout_taxe_eur': 'sum',
            'cout_total_eur': 'sum',
            'prix_spot_eur_mwh': 'mean'
        }).round(2)

        # Calculer l'énergie totale en MWh
        resume['energie_totale_mwh'] = (resume['puissance_ajustee_kw'] / 1000).round(2)

        # Prix moyen pondéré
        resume['prix_moyen_pondere_eur_mwh'] = (
            resume['cout_energie_eur'] / resume['energie_totale_mwh']
        ).round(2)

        return resume

    def identifier_heures_couteuses(self, df_calcul, top_n=100):
        """
        Identifie les heures les plus coûteuses.

        Args:
            df_calcul: DataFrame avec coûts calculés
            top_n: Nombre d'heures à retourner

        Returns:
            DataFrame des heures les plus coûteuses
        """
        top_heures = df_calcul.nlargest(top_n, 'cout_total_eur')[
            ['datetime', 'puissance_ajustee_kw', 'prix_spot_eur_mwh', 'cout_total_eur']
        ].copy()

        top_heures['contribution_pct'] = (
            top_heures['cout_total_eur'] / df_calcul['cout_total_eur'].sum() * 100
        ).round(2)

        return top_heures

    def calculer_impact_scenarios(self, df_enrichi, scenarios):
        """
        Calcule l'impact de plusieurs scénarios.

        Args:
            df_enrichi: DataFrame enrichi avec prix spot
            scenarios: Liste de dictionnaires avec paramètres de scénario
                       Format: [{'nom': 'Scénario 1', 'ajustement_volume_kw': 100, ...}, ...]

        Returns:
            DataFrame comparatif des scénarios
        """
        resultats = []

        for scenario in scenarios:
            nom = scenario.pop('nom', 'Sans nom')
            df_scenario = self.calculer_cout_avec_parametres(df_enrichi, **scenario)

            total = {
                'scenario': nom,
                'energie_totale_mwh': (df_scenario['puissance_ajustee_kw'].sum() / 1000),
                'cout_energie_eur': df_scenario['cout_energie_eur'].sum(),
                'cout_acheminement_eur': df_scenario['cout_acheminement_eur'].sum(),
                'cout_taxe_eur': df_scenario['cout_taxe_eur'].sum(),
                'cout_total_eur': df_scenario['cout_total_eur'].sum(),
            }

            resultats.append(total)

            # Remettre le nom dans le scénario pour ne pas modifier l'original
            scenario['nom'] = nom

        return pd.DataFrame(resultats).round(2)


def charger_prix_spot(filepath):
    """
    Charge les prix spot depuis un fichier CSV.

    Args:
        filepath: Chemin vers le fichier CSV

    Returns:
        DataFrame avec les prix spot
    """
    df_prix = pd.read_csv(filepath)

    # Convertir les dates
    df_prix['date_maj'] = pd.to_datetime(df_prix['date_maj'])
    df_prix['date_deb'] = pd.to_datetime(df_prix['date_deb'])
    df_prix['date_fin'] = pd.to_datetime(df_prix['date_fin'])

    return df_prix


def formater_montant(montant, unite='€'):
    """
    Formate un montant en euros de manière lisible.

    Args:
        montant: Montant à formater
        unite: Unité monétaire

    Returns:
        str: Montant formaté (ex: "1 234 567 €")
    """
    if pd.isna(montant):
        return "N/A"

    # Formater avec espaces comme séparateur de milliers
    return f"{montant:,.0f} {unite}".replace(',', ' ')
