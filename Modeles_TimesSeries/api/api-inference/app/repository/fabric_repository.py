"""Repository Fabric (lecture modèles + prédictions)."""

import logging
from typing import Optional, Dict, List

import pyodbc

logger = logging.getLogger(__name__)


class FabricRepository:
    """Accès en lecture aux modèles et prédictions dans Fabric Warehouse."""

    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn
        self.cursor = conn.cursor()

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

    def get_latest_predictions_series(self, prm: str) -> Optional[List[Dict]]:
        """Lit la dernière série de prédictions d'un PRM depuis Fabric.

        Compatibilité schéma :
        - Nouveau schéma Fabric : DATE_HEURE / VALEUR_PREDITE / ID_RUN
        - Ancien schéma : DATETIME_PRED / PUISSANCE_MOY_HEURE_PRED / DATE_GENERATION
        """
        logger.info(f"📖 Lecture prédictions Fabric pour {prm}...")

        sql_candidates = [
            """
            SELECT
                PRM,
                DATE_HEURE AS DATETIME_PRED,
                VALEUR_PREDITE AS PUISSANCE_MOY_HEURE_PRED,
                VALEUR_PRED_BASSE AS PUISSANCE_MOY_HEURE_PRED_LOWER,
                VALEUR_PRED_HAUTE AS PUISSANCE_MOY_HEURE_PRED_UPPER,
                NULL AS JOURS_DEPUIS_DEBUT,
                NULL AS ANNEE,
                CAST(ID_RUN AS VARCHAR(100)) AS DATE_GENERATION
            FROM ia_predictions
            WHERE PRM = ?
              AND ID_RUN = (
                    SELECT MAX(ID_RUN)
                    FROM ia_predictions
                    WHERE PRM = ?
              )
            ORDER BY DATE_HEURE
            """,
            """
            SELECT
                PRM,
                DATETIME_PRED,
                PUISSANCE_MOY_HEURE_PRED,
                PUISSANCE_MOY_HEURE_PRED_LOWER,
                PUISSANCE_MOY_HEURE_PRED_UPPER,
                JOURS_DEPUIS_DEBUT,
                ANNEE,
                DATE_GENERATION
            FROM ia_predictions
            WHERE PRM = ?
              AND DATE_GENERATION = (
                    SELECT MAX(DATE_GENERATION)
                    FROM ia_predictions
                    WHERE PRM = ?
              )
            ORDER BY DATETIME_PRED
            """,
            """
            SELECT
                PRM,
                DATETIME_PRED,
                PUISSANCE_MOY_HEURE_PRED,
                PUISSANCE_MOY_HEURE_PRED_LOWER,
                PUISSANCE_MOY_HEURE_PRED_UPPER,
                JOURS_DEPUIS_DEBUT,
                ANNEE,
                NULL AS DATE_GENERATION
            FROM ia_predictions
            WHERE PRM = ?
            ORDER BY DATETIME_PRED
            """,
        ]

        rows = None
        last_error: Exception | None = None

        for sql in sql_candidates:
            try:
                params = (prm, prm) if "MAX(" in sql else (prm,)
                self.cursor.execute(sql, params)
                rows = self.cursor.fetchall()
                break
            except Exception as exc:
                last_error = exc
                continue

        if rows is None:
            logger.error("❌ Erreur SQL lecture ia_predictions")
            if last_error:
                logger.error(str(last_error))
            return None

        if not rows:
            logger.warning(f"   ⚠️ Aucune prédiction trouvée pour {prm}")
            return []

        columns = [col[0] for col in self.cursor.description]
        output: List[Dict] = []
        for row in rows:
            data = dict(zip(columns, row))
            output.append(
                {
                    "datetime": str(data.get("DATETIME_PRED")) if data.get("DATETIME_PRED") is not None else None,
                    "puissance_moy_heure_pred": float(data.get("PUISSANCE_MOY_HEURE_PRED")) if data.get("PUISSANCE_MOY_HEURE_PRED") is not None else None,
                    "puissance_moy_heure_pred_lower": (
                        float(data.get("PUISSANCE_MOY_HEURE_PRED_LOWER"))
                        if data.get("PUISSANCE_MOY_HEURE_PRED_LOWER") is not None
                        else None
                    ),
                    "puissance_moy_heure_pred_upper": (
                        float(data.get("PUISSANCE_MOY_HEURE_PRED_UPPER"))
                        if data.get("PUISSANCE_MOY_HEURE_PRED_UPPER") is not None
                        else None
                    ),
                    "jours_depuis_debut": (
                        float(data.get("JOURS_DEPUIS_DEBUT"))
                        if data.get("JOURS_DEPUIS_DEBUT") is not None
                        else None
                    ),
                    "annee": int(data.get("ANNEE")) if data.get("ANNEE") is not None else None,
                }
            )

        logger.info(f"   ✅ {len(output)} point(s) de prédiction lus depuis Fabric")
        return output
