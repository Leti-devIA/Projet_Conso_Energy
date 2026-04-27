# 📋 Guide CI/CD - Workflows GitHub Actions

## 🎯 Qu'est-ce que le CI/CD ?

**CI (Intégration Continue)** : Tests automatiques à chaque modification de code
**CD (Déploiement Continu)** : Déploiement automatique après validation

---

## 📂 Nos Workflows

### 1️⃣ `ci.yml` - Tests Automatiques

**Quand ?** À chaque push ou Pull Request sur `main` ou `develop`

**Que fait-il ?**
- ✅ Installe Python et les dépendances
- 🧹 Vérifie la qualité du code (flake8, ruff)
- 🧪 Lance les tests unitaires avec couverture
- 📊 Affiche un rapport de couverture

**Pourquoi ?** Pour s'assurer que chaque modification ne casse pas le code existant.

---

### 2️⃣ `cd-api-dataclean.yml` - API de Nettoyage

**Quand ?**
- Manuellement depuis GitHub Actions
- Automatiquement si le code de `api/api-dataclean/` change

**Que fait-il ?**
- 🐳 Crée une image Docker de l'API
- ⬆️ Pousse l'image sur Docker Hub
- 🚀 Déploie sur le serveur (à configurer)

---

### 3️⃣ `cd-api-inference.yml` - API de Prédiction

**Quand ?**
- Manuellement
- Automatiquement si `api/api-inference/` ou `src/` change

**Que fait-il ?**
- 🐳 Build l'image Docker avec les modèles Prophet
- ⬆️ Push sur Docker Hub
- 🚀 Déploie l'API de prédiction

---

### 4️⃣ `cd-dashboard.yml` - Dashboard Streamlit

**Quand ?**
- Manuellement
- Automatiquement si les fichiers `dashboard_*.py` changent

**Que fait-il ?**
- ✅ Teste le lancement du dashboard
- 🐳 Build l'image Docker (optionnel)
- 🚀 Prêt pour déploiement

---

## 🔧 Configuration Requise

### Étape 1 : Créer les Secrets GitHub

1. Aller sur **GitHub** → Votre repo → **Settings**
2. **Secrets and variables** → **Actions** → **New repository secret**

**Secrets à ajouter :**

| Nom | Description | Exemple |
|-----|-------------|---------|
| `DOCKER_USERNAME` | Votre nom d'utilisateur Docker Hub | `monnie36` |
| `DOCKER_PASSWORD` | Votre mot de passe Docker Hub | `********` |
| `SERVER_HOST` | IP de votre serveur (optionnel) | `51.83.45.123` |
| `SSH_PRIVATE_KEY` | Clé SSH pour le serveur (optionnel) | `-----BEGIN...` |

---

### Étape 2 : Créer un Compte Docker Hub (si besoin)

1. Aller sur https://hub.docker.com
2. Créer un compte gratuit
3. Noter votre username et password
4. Les ajouter dans les secrets GitHub

---

## 🚀 Comment Utiliser les Workflows

### Lancer le CI (Tests)

```bash
# Le CI se lance automatiquement à chaque commit
git add .
git commit -m "feat: ajout nouvelle fonctionnalité"
git push origin main
```

**Vérifier :** Aller sur GitHub → **Actions** → Voir le workflow en cours

---

### Lancer le CD (Déploiement)

**Option 1 : Automatique**
- Push sur `main` avec modifications dans `api/api-dataclean/`
- Le workflow CD se lance automatiquement

**Option 2 : Manuel**
1. Aller sur GitHub → **Actions**
2. Choisir le workflow (ex: "CD - Déploiement API DataClean")
3. Cliquer sur **Run workflow** → **Run**

---

## 🧪 Tester en Local Avant de Push

### Tests

```bash
# Installe les dépendances
pip install -r requirements.txt
pip install pytest pytest-cov flake8 ruff

# Lance les tests
pytest tests/ -v --cov=src

# Vérifie le code
flake8 src/ --count --select=E9,F63,F7,F82 --show-source
```

### Build Docker

```bash
# API DataClean
cd api/api-dataclean
docker build -t api-dataclean:test .

# API Inference
cd api/api-inference
docker build -t api-inference:test .
```

---

## 📊 Comprendre les Résultats

### ✅ Workflow Réussi (vert)
- Tous les tests passent
- Le code respecte les standards
- Prêt pour déploiement

### ❌ Workflow Échoué (rouge)
- Cliquer sur le workflow
- Lire les logs pour identifier l'erreur
- Corriger et re-push

---

## 🎓 Pour Votre Certification

### Points Forts à Présenter

1. **CI/CD Complet**
   - Tests automatiques à chaque commit
   - Déploiement automatisé avec Docker

2. **Bonnes Pratiques**
   - Protection de branche `main` (PR obligatoire)
   - Environnement `production` avec approbation
   - Secrets sécurisés dans GitHub

3. **Monitoring**
   - Badge CI dans le README
   - Logs tracés de chaque déploiement
   - Couverture de code automatique

---

## 🔗 Badge CI pour le README

Ajoutez ce badge dans votre `README.md` :

```markdown
![CI](https://github.com/VOTRE-USERNAME/VOTRE-REPO/workflows/CI%20-%20Tests%20et%20Validation/badge.svg)
```

Remplacez `VOTRE-USERNAME` et `VOTRE-REPO` par vos valeurs.

---

## 📚 Ressources

- [Documentation GitHub Actions](https://docs.github.com/fr/actions)
- [Docker Hub](https://hub.docker.com)
- [Guide Pytest](https://docs.pytest.org)

---

## ❓ Questions Fréquentes

**Q : Le workflow échoue à "Connexion Docker Hub"**
R : Vérifiez que les secrets `DOCKER_USERNAME` et `DOCKER_PASSWORD` sont bien configurés.

**Q : Comment déployer sur un serveur ?**
R : Décommentez les lignes SSH dans les workflows CD et ajoutez le secret `SSH_PRIVATE_KEY`.

**Q : Peut-on tester le workflow sans push ?**
R : Oui, utilisez `act` pour tester localement : https://github.com/nektos/act

---

**🎉 Votre CI/CD est configurée ! Bonne chance pour votre certification !**
