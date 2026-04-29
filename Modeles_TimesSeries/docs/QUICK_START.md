# Quick Start

## 1) Installer
```bash
pip install -r requirements.txt
```

## 2) Lancer les APIs
```bash
cd api/api-dataclean
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd ../../api/api-inference
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 3) Lancer le dashboard
```bash
cd ../..
streamlit run dashboard_app.py
```

## 4) Lancer la doc MkDocs
```bash
mkdocs serve
```
