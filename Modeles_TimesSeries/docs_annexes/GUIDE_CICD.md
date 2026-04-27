# 🚀 Guide CI/CD - Démarrage Rapide

## ✅ Ce qui a été configuré

Votre projet dispose maintenant d'un système CI/CD complet :

### 📦 4 Workflows GitHub Actions

1. **`ci.yml`** → Tests automatiques à chaque commit
2. **`cd-api-dataclean.yml`** → Déploiement API de nettoyage
3. **`cd-api-inference.yml`** → Déploiement API de prédiction
4. **`cd-dashboard.yml`** → Déploiement du dashboard Streamlit

### 🛠️ 3 Scripts Utilitaires

1. **`run_ci_tests.sh`** → Teste en local avant de push
2. **`build_and_push.sh`** → Build et push les images Docker
3. **`deploy.sh`** → Déploie tout le projet en local

---

## 🎯 Utilisation en 3 Étapes

### Étape 1 : Configurer les Secrets GitHub

Sur GitHub, allez dans **Settings** → **Secrets and variables** → **Actions**

Ajoutez ces 2 secrets minimum :
- `DOCKER_USERNAME` : votre nom sur Docker Hub
- `DOCKER_PASSWORD` : votre mot de passe Docker Hub

> **Pas de compte Docker Hub ?** Créez-en un gratuitement : https://hub.docker.com

---

### Étape 2 : Tester en Local

```bash
# Testez que tout fonctionne avant de push
bash scripts/run_ci_tests.sh
```

Si ça passe ✅, vous êtes prêt à push !

---

### Étape 3 : Push et Regarder la Magie Opérer

```bash
git add .
git commit -m "feat: ajout CI/CD"
git push origin main
```

Puis allez sur **GitHub** → **Actions** → Voyez les tests se lancer automatiquement ! 🎉

---

## 📊 Workflows Expliqués Simplement

### CI - Tests Automatiques (`ci.yml`)

**Quand ?** À chaque `git push`

**Fait quoi ?**
```
1. Installe Python + dépendances
2. Vérifie le code (flake8, ruff)
3. Lance les tests unitaires
4. Affiche la couverture de code
```

**Résultat :** Badge ✅ ou ❌ visible sur GitHub

---

### CD - Déploiement (`cd-*.yml`)

**Quand ?** Manuellement OU automatiquement si code change

**Fait quoi ?**
```
1. Build une image Docker
2. Push sur Docker Hub
3. Prêt pour déploiement
```

**Résultat :** Vos APIs sont déployables en un clic

---

## 🎓 Pour Votre Certification

### Points Clés à Présenter

✅ **Pipeline CI/CD complète**
- Tests automatiques
- Linting du code
- Déploiement Docker automatisé

✅ **Bonnes Pratiques**
- Secrets sécurisés dans GitHub
- Tests avant déploiement
- Workflows séparés par service

✅ **Démonstration Live**
1. Montrez les workflows sur GitHub Actions
2. Faites un commit → les tests se lancent
3. Montrez les images sur Docker Hub

---

## 🧪 Commandes Utiles

### Tests en Local

```bash
# Tous les tests du workflow CI
bash scripts/run_ci_tests.sh

# Seulement les tests unitaires
pytest tests/ -v

# Seulement le linting
flake8 src/
```

### Docker en Local

```bash
# Déployer tout le projet
bash scripts/deploy.sh

# Build et push vers Docker Hub
export DOCKER_USERNAME="votre-username"
bash scripts/build_and_push.sh

# Voir les logs
docker-compose logs -f
```

### Workflows Manuels

Sur GitHub → **Actions** → Choisir un workflow → **Run workflow**

---

## 🔍 Comprendre les Erreurs

### ❌ "Connexion Docker Hub failed"
**Solution :** Vérifiez vos secrets `DOCKER_USERNAME` et `DOCKER_PASSWORD`

### ❌ "Tests failed"
**Solution :**
1. Lancez `bash scripts/run_ci_tests.sh` en local
2. Corrigez les tests qui échouent
3. Re-push

### ❌ "Build failed"
**Solution :**
1. Testez le build Docker en local : `cd api/api-dataclean && docker build .`
2. Vérifiez le `Dockerfile`

---

## 📝 Checklist Certification

Avant votre présentation, vérifiez :

- [ ] Les workflows CI/CD fonctionnent
- [ ] Au moins 1 workflow a été exécuté avec succès
- [ ] Les secrets sont configurés
- [ ] Vous comprenez chaque étape des workflows
- [ ] Vous pouvez expliquer CI vs CD
- [ ] Badge CI ajouté au README (optionnel)

---

## 🎁 Badge CI pour le README

Ajoutez ce badge au début de votre `README.md` :

```markdown
![CI](https://github.com/USERNAME/REPO/workflows/CI%20-%20Tests%20et%20Validation/badge.svg)
```

Remplacez `USERNAME` et `REPO` par vos vraies valeurs.

---

## 📚 Pour Aller Plus Loin

### Sujets Avancés (Bonus Certification)

- **Déploiement Cloud** : Azure, AWS, GCP
- **Monitoring** : Grafana, Prometheus
- **Notifications** : Slack, Discord
- **Tests de Performance** : Locust, k6
- **Sécurité** : Scan de vulnérabilités (Trivy)

### Ressources

- [GitHub Actions Docs](https://docs.github.com/fr/actions)
- [Docker Docs](https://docs.docker.com)
- [CI/CD Best Practices](https://github.com/features/actions)

---

## ❓ Questions Fréquentes

**Q : C'est quoi la différence entre CI et CD ?**
R : **CI** teste le code, **CD** le déploie. CI = qualité, CD = livraison.

**Q : Dois-je payer pour GitHub Actions ?**
R : Non, c'est gratuit pour les repos publics et limité pour les privés.

**Q : Puis-je utiliser GitLab CI au lieu de GitHub Actions ?**
R : Oui ! La logique est similaire, seule la syntaxe change.

**Q : Combien de temps prend un workflow ?**
R : CI ≈ 2-5 min | CD ≈ 5-10 min (dépend de la taille des images)

---

**🎉 Bravo ! Vous avez un vrai CI/CD professionnel !**

**Besoin d'aide ?** Lisez `.github/workflows/README.md` pour plus de détails.

---

*Guide créé avec le skill étudiant 🎓*
