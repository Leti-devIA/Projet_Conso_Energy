import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch):
    monkeypatch.setenv("INFERENCE_API_KEY", "test-key")


@pytest.fixture
def client():
    return TestClient(app)


def auth_headers():
    return {"X-API-Key": "test-key"}


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"].startswith("ok")


def test_sync_requires_api_key(client):
    response = client.post("/sync/prm/30000250086126")
    assert response.status_code == 401


def test_sync_invalid_prm(client):
    response = client.post("/sync/prm/abc", headers=auth_headers())
    assert response.status_code == 422


def test_predict_not_found_history(client):
    response = client.post("/predict/prm/30000250086126", headers=auth_headers())
    assert response.status_code in {200, 404, 502}


def test_predict_json_only_ok(client, monkeypatch, tmp_path):
    from app.routers import predict as predict_router

    # Modèle factice présent pour passer la validation "model exists"
    fake_model = tmp_path / "prophet_model_30000250086126_latest.pkl"
    fake_model.write_text("fake", encoding="utf-8")
    monkeypatch.setattr(predict_router, "MODELS_DIR", tmp_path)

    # Données historiques mockées (issues dataclean JSON)
    historical_df = pd.DataFrame(
        {
            "datetime": ["2026-01-01 00:00:00", "2026-01-01 01:00:00"],
            "temperature": [10.0, 11.0],
            "humidite": [70.0, 68.0],
            "vitesse_vent": [5.0, 4.5],
            "couverture_nuages": [40.0, 35.0],
            "puissance_moy_heure": [100.0, 120.0],
        }
    )
    historical_df["datetime"] = pd.to_datetime(historical_df["datetime"])

    monkeypatch.setattr(
        predict_router,
        "_fetch_history_from_dataclean",
        lambda prm: historical_df,
    )

    # Météo future mockée
    monkeypatch.setattr(
        predict_router,
        "_build_future_weather_from_history",
        lambda df: pd.DataFrame({"datetime": ["2026-01-02 00:00:00"]}),
    )

    # Résultat brut de predict_future mocké
    monkeypatch.setattr(
        predict_router,
        "predict_future",
        lambda prm, meteo_future_df, model_dir, config_path: pd.DataFrame(
            {
                "datetime": ["2026-01-02 00:00:00", "2026-01-02 01:00:00"],
                "yhat": [130.0, 140.0],
                "yhat_lower": [120.0, 130.0],
                "yhat_upper": [140.0, 150.0],
            }
        ),
    )

    # Format dashboard mocké
    monkeypatch.setattr(
        predict_router,
        "format_predictions_for_dashboard",
        lambda df_pred, historique_start: pd.DataFrame(
            [
                {
                    "datetime": "2026-01-02 00:00:00",
                    "puissance_moy_heure_pred": 130.0,
                    "puissance_moy_heure_pred_lower": 120.0,
                    "puissance_moy_heure_pred_upper": 140.0,
                    "jours_depuis_debut": 1.0,
                    "annee": 2026,
                },
                {
                    "datetime": "2026-01-02 01:00:00",
                    "puissance_moy_heure_pred": 140.0,
                    "puissance_moy_heure_pred_lower": 130.0,
                    "puissance_moy_heure_pred_upper": 150.0,
                    "jours_depuis_debut": 1.04,
                    "annee": 2026,
                },
            ]
        ),
    )

    response = client.post("/predict/prm/30000250086126", headers=auth_headers())
    assert response.status_code == 200

    payload = response.json()
    assert payload["prm"] == "30000250086126"
    assert payload["rows"] == 2
    assert "prediction_file" not in payload
    assert len(payload["series"]) == 2


def test_latest_prediction_not_found_in_fabric(client, monkeypatch):
    from app.routers import predict as predict_router

    class FakeRepo:
        def __init__(self, _conn):
            pass

        def get_latest_predictions_series(self, prm):
            return []

    class FakeConn:
        def close(self):
            return None

    monkeypatch.setattr(predict_router, "get_db_connection", lambda: FakeConn())
    monkeypatch.setattr(predict_router, "FabricRepository", FakeRepo)

    response = client.get(
        "/predictions/prm/30000250086126/latest",
        headers=auth_headers(),
    )
    assert response.status_code == 404


def test_latest_prediction_ok_from_fabric(client, monkeypatch):
    from app.routers import predict as predict_router

    class FakeRepo:
        def __init__(self, _conn):
            pass

        def get_latest_predictions_series(self, prm):
            return [
                {
                    "datetime": "2026-01-01 00:00:00",
                    "puissance_moy_heure_pred": 100,
                    "puissance_moy_heure_pred_lower": 90,
                    "puissance_moy_heure_pred_upper": 110,
                    "jours_depuis_debut": 0,
                    "annee": 2026,
                },
                {
                    "datetime": "2026-01-01 01:00:00",
                    "puissance_moy_heure_pred": 120,
                    "puissance_moy_heure_pred_lower": 100,
                    "puissance_moy_heure_pred_upper": 130,
                    "jours_depuis_debut": 0.04,
                    "annee": 2026,
                },
            ]

    class FakeConn:
        def close(self):
            return None

    monkeypatch.setattr(predict_router, "get_db_connection", lambda: FakeConn())
    monkeypatch.setattr(predict_router, "FabricRepository", FakeRepo)

    response = client.get(
        "/predictions/prm/30000250086126/latest",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == 2
    assert payload["prm"] == "30000250086126"
    assert len(payload["series"]) == 2
    assert payload["source"] == "fabric"
