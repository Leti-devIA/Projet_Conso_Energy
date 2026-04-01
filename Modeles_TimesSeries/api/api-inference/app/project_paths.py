from pathlib import Path
import os


def resolve_project_root(start: Path) -> Path:
    """Résout dynamiquement la racine projet (Modeles_TimesSeries) en local comme en Docker."""
    root_from_env = os.getenv("PROJECT_ROOT")
    if root_from_env:
        candidate = Path(root_from_env).resolve()
        if candidate.exists():
            return candidate

    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "src").exists() and (candidate / "config").exists():
            return candidate

    return current
