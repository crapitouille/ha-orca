# Outils

- `all_fields.txt` : liste des variables connues d'une PAC Orca (source : dépôt d'origine,
  `development_resources/all_fields.txt`).
- `gen_config.py` : génère les entrées `config.yml` des familles ajoutées en 2.5.0.
  Il vérifie que chaque variable existe dans `all_fields.txt` et qu'aucune n'est déclarée deux fois.

      python tools/gen_config.py tools/all_fields.txt > /tmp/added.yml

Pour trouver le nom d'une variable (capture réseau depuis Moja Orca, fichiers de l'écran en FTP),
voir la documentation du dépôt d'origine :
https://github.com/Tomasinjo/orca-energy-ha/tree/main/development_resources
