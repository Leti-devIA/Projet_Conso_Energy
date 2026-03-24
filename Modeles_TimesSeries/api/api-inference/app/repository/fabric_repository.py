"""
Requêtes pyodbc verso les tables IA du Fabric Warehouse.

Tables ciblées (T-SQL, schéma ia) :
    ia_modeles    – référentiel de modèles Prophet par PRM
    ia_metrics    – métriques MAE/RMSE/MAPE/R2 par modèle

Prérequis :
    - Les tables existent dans le Warehouse
    - DB_SERVER + DB_DATABASE définis dans .env
"""

import pyodbc
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class FabricDmlNotSupportedError(RuntimeError):
    """Le endpoint SQL cible refuse les opérations DML (ex: Lakehouse Delta via ODBC)."""


class FabricRepository:
    """Gère les interactions avec les tables ia_* dans Fabric Warehouse"""

    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn
        self.cursor = conn.cursor()

    @staticmethod
    def _is_dml_not_supported_error(error: Exception) -> bool:
        """Détecte l'erreur SQL Server 24559 remontée par Fabric SQL endpoint."""
        msg = str(error)
        return "24559" in msg and "DML" in msg

    # -------------------------------------------------------
    # ia_modeles
    # -------------------------------------------------------

    def upsert_model_registry(
        self,
        model_id: str,
        prm: str,
        model_name: str,
        model_version: str,
        artifact_uri: str,
        created_at: datetime,
        is_active: bool
    ) -> None:
        """
        Écrit le modèle dans ia_modeles.

        Désactive l'ancienne version active, insère la nouvelle.
        """

        logger.info(f"📝 Enregistrement {prm} dans ia_modeles...")

        try:
            # Désactiver l'ancienne version
            self.cursor.execute(
                "UPDATE ia_modeles SET IS_ACTIVE = 0 WHERE PRM = ? AND IS_ACTIVE = 1",
                (prm,)
            )
            logger.info(f"   ↻ Ancienne version désactivée")

            # Insérer la nouvelle
            self.cursor.execute(
                """
                INSERT INTO ia_modeles
                    (ID_MODELE, PRM, NOM_MODELE, VERSION_MODELE, URI, DATE_CREATION, IS_ACTIVE)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?)
                """,
                (model_id, prm, model_name, model_version, artifact_uri,
                 created_at, 1 if is_active else 0)
            )

            self.conn.commit()
            logger.info(f"   ✅ {prm} écrit en Fabric")

        except Exception as e:
            if self._is_dml_not_supported_error(e):
                logger.error(f"❌ DML non supporté pour ia_modeles : {str(e)}")
                raise FabricDmlNotSupportedError(str(e)) from e
            logger.error(f"❌ Erreur upsert model_registry : {str(e)}")
            raise

    def get_active_model(self, prm: str) -> Optional[Dict]:
        """Récupère le modèle actif d'un PRM depuis Fabric."""

        logger.info(f"📖 Lecture modèle actif pour {prm}...")

        try:
            self.cursor.execute(
                """
                SELECT TOP (1)
                    ID_MODELE, PRM, NOM_MODELE, VERSION_MODELE, URI,
                    DATE_CREATION, IS_ACTIVE
                FROM ia_modeles
                WHERE PRM = ? AND IS_ACTIVE = 1
                ORDER BY DATE_CREATION DESC
                """,
                (prm,)
            )
            row = self.cursor.fetchone()

            if not row:
                logger.warning(f"   ⚠️ Aucun modèle actif trouvé pour {prm}")
                return None

            columns = [col[0] for col in self.cursor.description]
            data = dict(zip(columns, row))

            normalized = {
                "model_id": data.get("ID_MODELE"),
                "prm": data.get("PRM"),
                "model_name": data.get("NOM_MODELE"),
                "model_version": data.get("VERSION_MODELE"),
                "artifact_uri": data.get("URI"),
                "created_at": data.get("DATE_CREATION"),
                "is_active": bool(data.get("IS_ACTIVE")),
            }

            logger.info(f"   ✅ Modèle trouvé : {normalized['model_version']}")
            return normalized

        except Exception as e:
            logger.error(f"❌ Erreur get_active_model : {str(e)}")
            return None

    # -------------------------------------------------------
    # ia.training_metrics
    # -------------------------------------------------------

    def insert_training_metrics(
        self,
        model_id: str,
        prm: str,
        metrics: Dict[str, float],
        measured_at: datetime
    ) -> int:
        """Écrit les métriques dans ia.training_metrics."""

        logger.info(f"📊 Enregistrement {len(metrics)} métrique(s) dans ia_metrics...")

        if not metrics:
            logger.warning(f"   ⚠️ Aucune métrique à insérer")
            return 0

        try:
            # Prépare les lignes
            rows = [
                (str(uuid.uuid4()), model_id, prm, name, float(value), measured_at)
                for name, value in metrics.items()
            ]

            # Insère en masse
            self.cursor.executemany(
                """
                INSERT INTO ia_metrics
                    (ID_METRIC, ID_MODELE, PRM, TYPE_METRIC, VALEUR_METRIC, DATE_MESURE)
                VALUES
                    (?, ?, ?, ?, ?, ?)
                """,
                rows
            )

            self.conn.commit()
            logger.info(f"   ✅ {len(rows)} métrique(s) écrite(s) en Fabric")
            return len(rows)

        except Exception as e:
            if self._is_dml_not_supported_error(e):
                logger.error(f"❌ DML non supporté pour ia_metrics : {str(e)}")
                raise FabricDmlNotSupportedError(str(e)) from e
            logger.error(f"❌ Erreur insert_training_metrics : {str(e)}")
            raise
