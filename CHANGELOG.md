# Journal des modifications

Base : [Tomasinjo/orca-energy-ha](https://github.com/Tomasinjo/orca-energy-ha) 2.4.3.

## 2.5.1

- Thermostat : l'entité se crée aussi quand aucune sonde d'ambiance n'est raccordée au circuit
  (elle échouait avec `KeyError: 'hc_room_temp_1'`). La température mesurée reste vide dans ce cas.
- Thermostat : la marche et l'arrêt du circuit fonctionnent (`set_hvac_mode`, `turn_on`, `turn_off`).
- Thermostat : seuls « arrêt » et le mode réglé sur la PAC sont proposés ; le mode de fonctionnement
  n'est plus écrit depuis Home Assistant.
- Thermostat : bornes de consigne reprises de `config.yml` (10 à 35 °C).
- `manifest.json` : `aiohttp` et `PyYAML` retirés des dépendances (fournis par Home Assistant, refusés par hassfest).
- Icône de l'intégration, tests de régression automatisés, fichier de test `test.py` retiré du composant.
- Exemple de tableau de bord : `dashboards/pompe-a-chaleur.yaml`.

## 2.5.0

- 207 variables ajoutées : programmes horaires, anti-légionelle, alarmes, puissance et débit,
  heures de fonctionnement, mode vacances.
- Nouveau type `integer` dans `config.yml` pour les valeurs entières (heures, minutes, jours, compteurs).
- Lecture par lots de 100 variables au lieu de 150.
