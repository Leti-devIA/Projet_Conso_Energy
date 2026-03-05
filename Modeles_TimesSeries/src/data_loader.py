"""
Module de chargement des données avec architecture flexible pour CSV et future base de données.

Ce module fournit une interface abstraite pour charger les données depuis différentes sources.
Il permet de faciliter la migration future depuis CSV vers une base de données.
"""
from abc import ABC, abstractmethod
import pandas as pd
import yaml
from pathlib import Path
from typing import List, Dict, Optional
import glob


class DataLoader(ABC):
    """
    Classe abstraite pour le chargement des données.

    Cette classe définit l'interface commune pour tous les loaders (CSV, Database, etc.)
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialise le DataLoader.

        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config = self._load_config(config_path)
        self.raw_path = Path(self.config['data']['raw'])
        self.processed_path = Path(self.config['data']['processed'])
        self.predictions_path = Path(self.config['data']['predictions'])

    def _load_config(self, config_path: str) -> dict:
        """Charge la configuration depuis le fichier YAML."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    @abstractmethod
    def load_dataclean(self, prm: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de consommation d'un ou plusieurs sites.

        Args:
            prm: Identifiant PRM du site (None = tous les sites)
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les données de consommation
        """
        pass

    @abstractmethod
    def load_meteo_data(self, prm: Optional[str] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données météo pour un site spécifique.

        Args:
            prm: Code PRM du site (obligatoire)
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            DataFrame avec les données météo
        """
        if prm is None:
            raise ValueError("Le paramètre 'prm' est obligatoire pour charger les données météo")

        # Chemin du fichier météo pour ce site
        meteo_path = self.raw_path / "meteo" / f"meteo_horaire_{prm}.csv"

        if not meteo_path.exists():
            raise FileNotFoundError(
                f"Fichier météo non trouvé pour le site {prm} : {meteo_path}\n"
                f"Générez-le d'abord avec : python generate_meteo_all.py --prm {prm}"
            )

        print(f"📂 Chargement météo pour PRM {prm}...")
        df = pd.read_csv(meteo_path)

        # Filtrer par dates si spécifiées
        if 'datetime' in df.columns and (start_date or end_date):
            df['datetime'] = pd.to_datetime(df['datetime'])
            if start_date:
                df = df[df['datetime'] >= start_date]
            if end_date:
                df = df[df['datetime'] <= end_date]

        print(f"   ✅ {len(df)} lignes météo chargées")
        return df

    @abstractmethod
    def load_prix_data(self, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de prix spot.

        Args:
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les prix spot
        """
        pass

    @abstractmethod
    def list_available_sites(self) -> List[str]:
        """
        Liste tous les sites (PRM) disponibles.

        Returns:
            Liste des identifiants PRM disponibles
        """
        pass

    @abstractmethod
    def load_sites_table(self) -> pd.DataFrame:
        """
        Charge la table de référence des sites.

        Returns:
            DataFrame avec les informations des sites (PRM, ville, coordonnées, etc.)
        """
        pass

    def get_site_info(self, prm: str) -> Dict:
        """
        Récupère les informations d'un site spécifique.

        Args:
            prm: Identifiant PRM du site

        Returns:
            Dictionnaire avec les infos du site (ville, code_postal, lat, lon, etc.)
        """
        sites_df = self.load_sites_table()
        site = sites_df[sites_df['prm'] == int(prm)]
        if site.empty:
            return {'prm': prm, 'ville': 'Inconnu', 'code_postal': '', 'lat': None, 'lon': None}
        return site.iloc[0].to_dict()




class CSVDataLoader(DataLoader):
    """
    Implémentation du DataLoader pour fichiers CSV.

    Cette classe charge les données depuis des fichiers CSV organisés dans data/raw.
    Structure attendue :
        data/raw/sites/dataclean_prm_XXXXX.csv
        data/raw/sites/table_sites.csv
        data/raw/meteo/previsions_meteo.csv
        data/raw/prix/prix_spot.csv
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialise le CSVDataLoader."""
        super().__init__(config_path)
        self.base_path = Path(self.config['data']['raw'])

    def load_sites_table(self) -> pd.DataFrame:
        """
        Charge la table de référence des sites.

        Returns:
            DataFrame avec les informations des sites
        """
        sites_table_path = self.base_path / "sites" / "table_sites.csv"
        if not sites_table_path.exists():
            print(f"⚠️ Table des sites non trouvée : {sites_table_path}")
            return pd.DataFrame(columns=['id_site', 'ville', 'code_postal', 'prm', 'lat', 'lon', 'prod_elec'])

        print(f"📂 Chargement de la table des sites...")
        df = pd.read_csv(sites_table_path)
        print(f"✅ {len(df)} sites chargés")
        return df

    def list_available_sites(self) -> List[str]:
        """
        Liste tous les sites disponibles depuis la table des sites.

        Returns:
            Liste des PRMs disponibles
        """
        sites_df = self.load_sites_table()
        if sites_df.empty:
            return []

        # Convertir les PRMs en string et les retourner
        prms = sites_df['prm'].astype(str).tolist()
        return sorted(prms)

    def list_available_sites_with_data(self) -> List[str]:
        """
        Liste les sites qui ont des fichiers de données disponibles.

        Returns:
            Liste des PRMs avec fichiers CSV disponibles
        """
        sites_path = self.base_path / "sites"
        if not sites_path.exists():
            print(f"⚠️ Le dossier {sites_path} n'existe pas")
            return []

        # Chercher tous les fichiers dataclean_prm_*.csv
        pattern = str(sites_path / "dataclean_prm_*.csv")
        files = glob.glob(pattern)

        # Extraire les PRMs des noms de fichiers
        prms = []
        for file in files:
            filename = Path(file).stem  # Nom sans extension
            # Format: dataclean_prm_XXXXX
            if filename.startswith("dataclean_prm_"):
                prm = filename.replace("dataclean_prm_", "")
                prms.append(prm)

        return sorted(prms)

    def load_dataclean(self, prm: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de consommation depuis les fichiers CSV.

        Args:
            prm: Identifiant PRM du site (None = tous les sites)
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les données de consommation
        """
        sites_path = self.base_path / "sites"

        if prm:
            # Charger un site spécifique
            filepath = sites_path / f"dataclean_prm_{prm}.csv"
            if not filepath.exists():
                raise FileNotFoundError(f"❌ Fichier non trouvé : {filepath}")

            print(f"📂 Chargement des données du site {prm}...")
            df = pd.read_csv(filepath, sep=",", decimal=".")
            df['prm'] = prm  # Ajouter l'identifiant PRM

        else:
            # Charger tous les sites
            prms = self.list_available_sites()
            if not prms:
                raise FileNotFoundError(f"❌ Aucun fichier de site trouvé dans {sites_path}")

            print(f"📂 Chargement des données de {len(prms)} sites...")
            dfs = []
            for prm_id in prms:
                filepath = sites_path / f"dataclean_prm_{prm_id}.csv"
                df_site = pd.read_csv(filepath, sep=",", decimal=".")
                df_site['prm'] = prm_id
                dfs.append(df_site)

            df = pd.concat(dfs, ignore_index=True)

        # Convertir les dates si elles sont présentes
        if 'datetime' in df.columns or 'date' in df.columns:
            date_col = 'datetime' if 'datetime' in df.columns else 'date'
            df[date_col] = pd.to_datetime(df[date_col])

            # Filtrer par dates si spécifiées
            if start_date:
                df = df[df[date_col] >= start_date]
            if end_date:
                df = df[df[date_col] <= end_date]

        print(f"✅ {len(df)} lignes chargées")
        return df


    def load_processed_site_data(
        self,
        prm: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Charge les données déjà preprocessées + feature engineering
        depuis data/processed.

        Args:
            prm: Identifiant PRM du site
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)

        Returns:
            DataFrame des données processed
        """

        filepath = self.processed_path / f"data_processed_{prm}.csv"

        if not filepath.exists():
            raise FileNotFoundError(
                f"❌ Fichier processed introuvable pour PRM {prm} : {filepath}"
            )

        df = pd.read_csv(filepath, sep=",", decimal=".")
        df["prm"] = str(prm)

        # Gestion dates
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])

            if start_date:
                start_date = pd.to_datetime(start_date)
                df = df[df["datetime"] >= start_date]

            if end_date:
                end_date = pd.to_datetime(end_date)
                df = df[df["datetime"] <= end_date]

        return df.sort_values("datetime").reset_index(drop=True)



    def load_predictions(
        self,
        model_name: str,
        prm: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Charge les prédictions sauvegardées d'un modèle donné.

        Structure attendue :
        data/predictions/{model_name}/predictions_prm_XXXXX.csv

        Args:
            model_name: Nom du modèle (ex: 'lstm_v1')
            prm: Identifiant PRM
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)

        Returns:
            DataFrame des prédictions
        """

        predictions_path = self.predictions_path / model_name
        filepath = predictions_path / f"predictions_prm_{prm}.csv"

        if not filepath.exists():
            raise FileNotFoundError(
                f"❌ Fichier de prédictions introuvable : {filepath}"
            )

        df = pd.read_csv(filepath, sep=",", decimal=".")
        df["prm"] = str(prm)

        # Gestion dates
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])

            if start_date:
                start_date = pd.to_datetime(start_date)
                df = df[df["datetime"] >= start_date]

            if end_date:
                end_date = pd.to_datetime(end_date)
                df = df[df["datetime"] <= end_date]

        return df.sort_values("datetime").reset_index(drop=True)



    def load_meteo_data(self, prm: Optional[str] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données météorologiques depuis le fichier CSV.

        Args:
            prm: Code PRM du site (obligatoire pour charger la météo spécifique)
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les données météo
        """
        meteo_path = self.base_path / "meteo"

        if prm:
            # Charger la météo spécifique au site
            filepath = meteo_path / f"meteo_horaire_{prm}.csv"

            if not filepath.exists():
                raise FileNotFoundError(
                    f"❌ Fichier météo non trouvé pour le site {prm} : {filepath}\n"
                    f"   Générez-le d'abord avec : python generate_meteo_all.py --prm {prm}"
                )

            print(f"📂 Chargement météo pour PRM {prm}...")
        else:
            # Chercher le fichier de météo générique (plusieurs noms possibles)
            possible_files = ["previsions_meteo.csv", "meteo.csv", f"meteo_horaire_{prm}.csv"]
            filepath = None

            for filename in possible_files:
                test_path = meteo_path / filename
                if test_path.exists():
                    filepath = test_path
                    break

            if not filepath:
                raise FileNotFoundError(f"❌ Aucun fichier météo trouvé dans {meteo_path}")

            print(f"📂 Chargement des données météo depuis {filepath.name}...")

        df = pd.read_csv(filepath, sep=",", decimal=".")

        # Convertir les dates si présentes
        if 'datetime' in df.columns or 'date' in df.columns:
            date_col = 'datetime' if 'datetime' in df.columns else 'date'
            df[date_col] = pd.to_datetime(df[date_col])

            # Filtrer par dates si spécifiées
            if start_date:
                df = df[df[date_col] >= start_date]
            if end_date:
                df = df[df[date_col] <= end_date]

        print(f"✅ {len(df)} lignes météo chargées")
        return df

    def load_prix_data(self, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de prix spot depuis le fichier CSV.

        Args:
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les prix spot
        """
        prix_path = self.base_path / "prix"

        # Chercher le fichier de prix
        possible_files = ["prix_spot.csv"]
        filepath = None

        for filename in possible_files:
            test_path = prix_path / filename
            if test_path.exists():
                filepath = test_path
                break

        if not filepath:
            raise FileNotFoundError(f"❌ Aucun fichier de prix trouvé dans {prix_path}")

        print(f"📂 Chargement des données de prix depuis {filepath.name}...")
        df = pd.read_csv(filepath, sep=",", decimal=".")

        # Convertir les dates si présentes
        if 'datetime' in df.columns or 'date' in df.columns:
            date_col = 'datetime' if 'datetime' in df.columns else 'date'
            df[date_col] = pd.to_datetime(df[date_col])

            # Filtrer par dates si spécifiées
            if start_date:
                df = df[df[date_col] >= start_date]
            if end_date:
                df = df[df[date_col] <= end_date]

        print(f"✅ {len(df)} lignes chargées")
        return df

    def save_processed_site_data(self, df, prm):
        filepath = self.processed_path / f"data_processed_{prm}.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)
        print(f"✅ Données sauvegardées : {filepath}")


class DatabaseDataLoader(DataLoader):
    """
    Implémentation du DataLoader pour base de données (FUTURE).

    Cette classe servira à charger les données depuis une base de données SQL.
    Pour le moment, c'est un stub qui lève des exceptions NotImplementedError.

    Structure de tables attendue :
    - table 'sites' : id_site, ville, code_postal, prm, lat, lon, prod_elec
    - table 'consommation' : datetime, prm, puissance_moy_heure, temperature, humidite, ...
    - table 'meteo' : datetime, temperature, humidite, vitesse_vent, couverture_nuages
    - table 'prix_spot' : datetime, prix

    TODO: Implémenter la connexion à la base de données et les requêtes SQL.
    """

    def __init__(self, config_path: str = "config/config.yaml",
                 connection_string: Optional[str] = None):
        """
        Initialise le DatabaseDataLoader.

        Args:
            config_path: Chemin vers le fichier de configuration
            connection_string: Chaîne de connexion à la base de données
        """
        super().__init__(config_path)
        self.connection_string = connection_string
        # TODO: Initialiser la connexion à la base de données
        # import sqlalchemy
        # self.engine = sqlalchemy.create_engine(connection_string)

    def load_sites_table(self) -> pd.DataFrame:
        """
        Charge la table de référence des sites depuis la base de données.

        Returns:
            DataFrame avec les informations des sites
        """
        # TODO: Implémenter la requête SQL
        # return pd.read_sql_query("SELECT * FROM sites ORDER BY ville", self.engine)
        raise NotImplementedError(
            "DatabaseDataLoader n'est pas encore implémenté. "
            "Utilisez CSVDataLoader pour le moment."
        )

    def list_available_sites(self) -> List[str]:
        """
        Liste tous les sites disponibles depuis la base de données.

        Returns:
            Liste des PRMs disponibles
        """
        # TODO: Implémenter la requête SQL
        # Exemple: SELECT DISTINCT prm FROM sites ORDER BY prm
        raise NotImplementedError(
            "DatabaseDataLoader n'est pas encore implémenté. "
            "Utilisez CSVDataLoader pour le moment."
        )

    def load_dataclean(self, prm: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de consommation depuis la base de données.

        Args:
            prm: Identifiant PRM du site (None = tous les sites)
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les données de consommation
        """
        # TODO: Implémenter la requête SQL
        # Exemple: SELECT * FROM consommation WHERE prm = ? AND datetime BETWEEN ? AND ?
        raise NotImplementedError(
            "DatabaseDataLoader n'est pas encore implémenté. "
            "Utilisez CSVDataLoader pour le moment."
        )

    def load_meteo_data(self, prm: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données météorologiques depuis la base de données.

        Args:
            prm: Code PRM du site (obligatoire pour charger la météo spécifique)
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les données météo
        """
        # TODO: Implémenter la requête SQL
        # Exemple: SELECT * FROM meteo WHERE datetime BETWEEN ? AND ?
        raise NotImplementedError(
            "DatabaseDataLoader n'est pas encore implémenté. "
            "Utilisez CSVDataLoader pour le moment."
        )

    def load_prix_data(self, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Charge les données de prix spot depuis la base de données.

        Args:
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)

        Returns:
            DataFrame avec les prix spot
        """
        # TODO: Implémenter la requête SQL
        # Exemple: SELECT * FROM prix_spot WHERE datetime BETWEEN ? AND ?
        raise NotImplementedError(
            "DatabaseDataLoader n'est pas encore implémenté. "
            "Utilisez CSVDataLoader pour le moment."
        )


def get_data_loader(source: str = "csv", config_path: str = "config/config.yaml",
                    **kwargs) -> DataLoader:
    """
    Factory function pour créer le bon DataLoader selon la source.

    Args:
        source: Type de source ('csv' ou 'database')
        config_path: Chemin vers le fichier de configuration
        **kwargs: Arguments additionnels pour le loader (ex: connection_string pour database)

    Returns:
        Instance de DataLoader appropriée

    Example:
        >>> loader = get_data_loader('csv')
        >>> sites = loader.list_available_sites()
        >>> df = loader.load_dataclean(prm='30000250086126')
    """
    if source.lower() == 'csv':
        return CSVDataLoader(config_path)
    elif source.lower() in ['database', 'db', 'sql']:
        return DatabaseDataLoader(config_path, **kwargs)
    else:
        raise ValueError(f"Source inconnue : {source}. Utilisez 'csv' ou 'database'.")
