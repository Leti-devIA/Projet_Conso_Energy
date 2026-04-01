import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ENV = ROOT_DIR / "config" / "fabric_runtime.env"
NGROK_API_URL = os.getenv("NGROK_API_URL", "http://127.0.0.1:4040/api/tunnels")
SYNC_OUTPUT_ENV = Path(os.getenv("SYNC_OUTPUT_ENV", str(DEFAULT_OUTPUT_ENV)))
SYNC_MAX_WAIT_SECONDS = int(os.getenv("SYNC_MAX_WAIT_SECONDS", "60"))
SYNC_POLL_INTERVAL_SECONDS = float(os.getenv("SYNC_POLL_INTERVAL_SECONDS", "2"))


def get_ngrok_https_url(api_url: str) -> str:
    request = Request(api_url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    tunnels = payload.get("tunnels", [])
    for tunnel in tunnels:
        public_url = str(tunnel.get("public_url", "")).strip()
        if public_url.startswith("https://"):
            return public_url

    raise RuntimeError(
        "Aucun tunnel HTTPS ngrok trouvé. Vérifie que ngrok est démarré et expose ton API."
    )


def wait_for_ngrok_https_url(
    api_url: str,
    max_wait_seconds: int,
    poll_interval_seconds: float,
) -> str:
    start = time.time()
    last_error = None

    while (time.time() - start) < max_wait_seconds:
        try:
            return get_ngrok_https_url(api_url)
        except Exception as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)

    raise RuntimeError(
        f"Timeout après {max_wait_seconds}s en attente d'un tunnel HTTPS ngrok. "
        f"Dernière erreur: {last_error}"
    )


def write_runtime_json(output_path: Path, api_base_url: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "api_base_url": api_base_url,
        "generated_by": "sync_ngrok_to_fabric_config.py",
    }
    output_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def write_runtime_env(output_path: Path, api_base_url: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"API_BASE_URL={api_base_url}\n", encoding="utf-8")


def main() -> None:
    api_base_url = wait_for_ngrok_https_url(
        api_url=NGROK_API_URL,
        max_wait_seconds=SYNC_MAX_WAIT_SECONDS,
        poll_interval_seconds=SYNC_POLL_INTERVAL_SECONDS,
    )
    write_runtime_env(SYNC_OUTPUT_ENV, api_base_url)

    print("✅ URL ngrok détectée:", api_base_url)
    print("✅ Config ENV mise à jour:", SYNC_OUTPUT_ENV)
    print(
        "ℹ️ Injecte API_BASE_URL via pipeline."
    )


if __name__ == "__main__":
    main()
