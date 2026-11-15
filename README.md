<img src="https://raw.githubusercontent.com/crapitouille/ha-orca/main/custom_components/orca/brand/icon.png" alt="Orca" height="96">

# Orca — pompe à chaleur (version étendue)

[![Marketplace Custom](https://img.shields.io/badge/Marketplace%20%7C%20HACS-Custom-41BDF5.svg)](https://contributors.home-assistant.io/marketplace/)
[![Release](https://img.shields.io/github/v/release/crapitouille/ha-orca)](https://github.com/crapitouille/ha-orca/releases)
[![Validate](https://github.com/crapitouille/ha-orca/actions/workflows/validate.yml/badge.svg)](https://github.com/crapitouille/ha-orca/actions/workflows/validate.yml)
[![Tests](https://github.com/crapitouille/ha-orca/actions/workflows/tests.yml/badge.svg)](https://github.com/crapitouille/ha-orca/actions/workflows/tests.yml)

[![Ouvrir dans le Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=crapitouille&repository=ha-orca&category=integration)
[![Ajouter l'intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=orca)

Intégration Home Assistant pour piloter en local, par le réseau Ethernet, une pompe à chaleur
**Orca** (séries Mono et Duo, écran tactile Carel).

C'est une version étendue de l'intégration
[Tomasinjo/orca-energy-ha](https://github.com/Tomasinjo/orca-energy-ha) (2.4.3), dont elle garde le
fonctionnement, la configuration et toutes les entités. Elle y ajoute :

* **209 variables** de la PAC : programmes horaires, anti-légionelle, alarmes, puissance,
  heures de fonctionnement, mode vacances, température réduite de l'eau chaude ;
* un **thermostat qui fonctionne sans sonde d'ambiance**, avec marche et arrêt du circuit ;
* des **tests de régression automatisés** contre un simulateur de PAC.

## Ce que l'intégration apporte

Tout ce que fournit l'intégration d'origine (températures, état de la PAC, eau chaude sanitaire,
courbe de chauffe, limites de puissance), plus :

| Famille | Dans Home Assistant | Réglable |
|---|---|---|
| Programmes horaires 1 à 5, trois plages chacun | un interrupteur par jour, heure et minute de début et de fin, programme suivi par l'eau chaude et par le mode silencieux | oui |
| Anti-légionelle | activation, température, jour, heure, minute, cycle, durée maximale | oui, sauf cycle et durée maximale |
| Alarmes | alarme active, alarmes détaillées, type d'alarme, code d'erreur | non |
| Puissance et débit | puissance de la PAC, limites et plafonds par mode, entrées débit et compresseur | non |
| Heures de fonctionnement | compresseur et appoint électrique | non |
| Mode vacances | activation et date de fin | oui |
| Eau chaude, régime bas | température appliquée en dehors du programme horaire, consigne en cours | oui pour la température |

Une variable que la PAC ne connaît pas est simplement ignorée : le nombre d'entités dépend du modèle
et de l'installation. Avec un plancher chauffant et de l'eau chaude sanitaire, on obtient environ
190 à 200 entités de plus que l'intégration d'origine.

Les heures de fonctionnement sont fournies par la PAC en deux compteurs. Le total se calcule ainsi :
`milliers × 1000 + unités`.

### Thermostat

Chaque circuit de chauffage a une entité thermostat :

* **consigne** de 10 à 35 °C. Si le circuit suit un programme horaire, la carte affiche deux
  consignes, nuit et jour ;
* **marche et arrêt** du circuit ;
* **température mesurée** si une sonde d'ambiance est raccordée, vide sinon.

Le thermostat propose « arrêt » et le mode réglé sur la PAC. Le mode de fonctionnement (chauffage,
rafraîchissement, automatique) se change sur l'écran de la PAC, pas depuis Home Assistant.

## Tableau de bord

Le fichier [`dashboards/pompe-a-chaleur.yaml`](dashboards/pompe-a-chaleur.yaml) est un tableau de
bord prêt à l'emploi, construit avec les seules cartes intégrées à Home Assistant :

* une vue **Accueil** pour l'utilisateur final : état de la PAC en clair, thermostat du plancher,
  eau chaude sanitaire, mode vacances, graphique des dernières 24 heures, et un encadré d'alerte
  qui n'apparaît qu'en cas d'alarme ;
* une vue **Technique** : fonctionnement, anti-légionelle, compteurs et programmes horaires.

Pour l'installer, créez un tableau de bord vide, ouvrez son *éditeur de configuration brute* et
collez-y le contenu du fichier. Les identifiants d'entités sont ceux de Home Assistant 2026.11 avec
les noms d'entités en anglais ; adaptez-les si les vôtres diffèrent.

## Prérequis

* Home Assistant 2026.2 ou plus récent.
* La PAC raccordée au réseau par la prise Ethernet de son écran tactile, avec une adresse IP fixe
  ou réservée sur le routeur.
* Les identifiants de l'interface web de la PAC.

## Installation

Cette intégration utilise le même domaine `orca` que l'intégration d'origine : **une seule des deux
peut être installée**. Si l'intégration d'origine est déjà en place, retirez d'abord son dépôt du
Marketplace ou de HACS, puis installez celle-ci.

### Marketplace (Home Assistant 2026.11 et plus récent)

1. Cliquez sur le bouton « Ouvrir dans le Marketplace » en haut de cette page, ou ajoutez
   `https://github.com/crapitouille/ha-orca` aux dépôts personnalisés du Marketplace, avec le type
   *Intégration*.
2. Téléchargez l'intégration.
3. Redémarrez Home Assistant.

### HACS (Home Assistant 2026.10 et plus ancien)

1. Dans HACS, ouvrez *Dépôts personnalisés*, ajoutez `https://github.com/crapitouille/ha-orca`
   avec la catégorie *Intégration*.
2. Téléchargez « Orca Heat Pump Extended ».
3. Redémarrez Home Assistant.

### Installation manuelle

Copiez le dossier `custom_components/orca` dans le dossier `custom_components` de votre
configuration Home Assistant, puis redémarrez.

## Configuration

*Paramètres → Appareils et services → Ajouter une intégration → Orca*, ou le bouton
« Ajouter l'intégration » en haut de cette page. Renseignez l'adresse IP de la PAC, l'identifiant et
le mot de passe, et la langue des noms d'entités (anglais ou slovène).

Les circuits sont détectés automatiquement. Les options de l'intégration permettent de les forcer si
la détection se trompe.

## État de validation

* **Tests automatisés** : 31 tests, sur Home Assistant 2026.2 et sur la version la plus récente,
  contre un simulateur qui rejoue des relevés réels de PAC Duo et Mono.
* **En conditions réelles** : installée sur une PAC Orca (plancher chauffant et eau chaude sanitaire)
  avec Home Assistant 2026.11. La lecture de toutes les familles y est vérifiée.
* **À vérifier chez vous** : les écritures ajoutées par cette version (programmes horaires,
  anti-légionelle, mode vacances, température réduite de l'eau chaude, marche et arrêt du thermostat)
  sont testées sur le simulateur.
  Après un premier réglage depuis Home Assistant, vérifiez sur l'écran de la PAC qu'il a bien été
  pris en compte.

Limites connues :

* les remises à zéro d'alarmes ne sont pas exposées ;
* la consommation électrique n'est pas fournie par la PAC ;
* Home Assistant signale des éléments dépréciés pour la version 2027.11 sur le thermostat et le
  chauffe-eau (hérités de l'intégration d'origine).

## Développement

### Lancer les tests

```
pip install -r requirements_test.txt
pytest
```

* `tests/mock_pac.py` : simulateur de l'API HTTP de la PAC (`/cgi/login`, `/cgi/readTags`,
  `/cgi/writeTags`).
* `tests/fixtures/field_dump_*.txt` : relevés réels issus du dépôt d'origine.
* `tests/fixtures/baseline_2.4.3.json` : ce que renvoyait l'intégration d'origine 2.4.3 pour chaque
  relevé. Les tests vérifient que les entités d'origine restent strictement identiques.

### Ajouter une variable

Toutes les variables sont déclarées dans `custom_components/orca/config.yml`. Chaque entrée a un
type :

| Type | Valeur |
|---|---|
| `boolean` | 0 ou 1 |
| `float` | nombre à une décimale, transmis multiplié par 10 (`215` = 21,5) |
| `integer` | nombre entier transmis tel quel (heures, minutes, jours, compteurs) |
| `multimode` | liste de valeurs nommées, décrite par `value_map` |

Une variable réglable précise sa plage (`min`, `max`, `step`). Pour trouver le nom d'une variable,
voir la [documentation du dépôt d'origine](https://github.com/Tomasinjo/orca-energy-ha/tree/main/development_resources)
et le dossier `tools/`.

### Publier une version

1. Mettre à jour `version` dans `custom_components/orca/manifest.json` et `CHANGELOG.md`.
2. Créer une *release* GitHub dont le tag est exactement ce numéro de version (par exemple `2.5.1`,
   sans « v »).

## Crédits et licence

Travail d'origine : [Tomasinjo/orca-energy-ha](https://github.com/Tomasinjo/orca-energy-ha) et ses
contributeurs. Licence [MIT](LICENSE).

Cette intégration n'est ni éditée ni soutenue par le fabricant de la pompe à chaleur.
