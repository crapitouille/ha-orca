# Exemples

## Scénarios maison pour l'eau chaude — `scenarios-eau-chaude.yaml`

Un sélecteur **Économique / Confort / Vacances** qui règle les deux consignes d'eau chaude de
la PAC : celle du programme horaire et celle appliquée en dehors du programme.

| Scénario | Pendant le programme | Hors programme | Anti-légionelle de la PAC |
|---|---|---|---|
| Confort | 55 °C | 55 °C | inchangé |
| Économique | 45 °C, ou 56 °C s'il y a du surplus solaire | 45 °C | inchangé |
| Vacances | 42 °C | 42 °C | coupé (option) |

**Surplus solaire, en Économique.** Quand l'injection dans le réseau dépasse le seuil (2 kW),
la consigne du programme passe à 56 °C pour une durée de maintien (20 min). À la fin du
maintien :

* l'injection dépasse encore le seuil : le maintien repart ;
* la PAC produit de l'eau chaude et l'injection reste au-dessus de l'« injection minimale pour
  prolonger » (0 kW par défaut) : le maintien repart aussi. Sans cela, la consommation de la PAC
  ferait retomber l'injection sous le seuil et le compresseur serait arrêté puis relancé à
  chaque maintien ;
* sinon : retour à 45 °C.

La consigne haute ne fait chauffer que pendant les plages du programme horaire de l'eau chaude.

**Retour de vacances.** Au passage de Vacances à Économique ou Confort, les consignes sont
rétablies tout de suite et un cycle anti-légionelle est mis en attente. À la première heure
creuse (immédiatement si on y est déjà), le programme anti-légionelle de la PAC est réactivé et
son jour, son heure et sa minute sont placés après le délai réglé (10 min). Le programme
hebdomadaire garde ensuite ce jour et cette heure.

### Réglages

Tout se règle depuis le tableau de bord (cartes `scenarios-eau-chaude-cartes.yaml`) :

| Réglage | Entité | Valeur de départ conseillée |
|---|---|---|
| Scénario | `input_select.ecs_scenario` | — |
| Consigne Confort, Vacances, Économique | `input_number.ecs_t_confort`, `ecs_t_vacances`, `ecs_t_defaut` | 55, 42, 45 °C |
| Profiter du surplus solaire | `input_boolean.ecs_surplus_actif` | activé |
| Consigne avec surplus | `input_number.ecs_t_surplus` | 56 °C |
| Seuil d'injection | `input_number.ecs_seuil_surplus_kw` | 2 kW |
| Durée de maintien | `input_number.ecs_maintien_min` | 20 min |
| Injection minimale pour prolonger pendant la chauffe | `input_number.ecs_seuil_prolongation_kw` | 0 kW |
| Couper l'anti-légionelle pendant les vacances | `input_boolean.ecs_vacances_couper_legio` | activé |
| Cycle anti-légionelle au retour, en heure creuse | `input_boolean.ecs_legio_apres_vacances` | activé |
| Délai avant le cycle | `input_number.ecs_legio_delai_min` | 10 min |
| Capteur de puissance au compteur (W ou kW) | `select.ecs_capteur_reseau` | votre compteur |
| Compteur positif en injection | `input_boolean.ecs_reseau_injection_positive` | désactivé (P1 : négatif en injection) |
| Capteur d'heures creuses (« on » en heure creuse) | `select.ecs_capteur_heures_creuses` | votre capteur de tarif |

Sans l'option « cycle au retour », le programme anti-légionelle coupé pendant les vacances est
réactivé tel quel au retour. Désactiver l'option alors qu'un cycle est en attente l'annule de la
même façon.

### Installation

1. Copier le fichier dans le dossier `packages` de la configuration et déclarer ce dossier
   dans `configuration.yaml` :

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

2. Adapter si besoin les entités de la PAC (`orca_heat_pump_*`, noms de Home Assistant 2026.11).
3. Redémarrer, puis ajouter à un tableau de bord les cartes de `scenarios-eau-chaude-cartes.yaml`.
4. **Avant de choisir un scénario**, régler les valeurs du tableau ci-dessus : au premier
   démarrage, les nombres valent leur minimum, les options sont désactivées et aucun capteur
   n'est choisi.

Les mêmes éléments peuvent être créés depuis l'interface (Paramètres → Appareils et services →
Entrées, et Automatisations).

### Tests

`tests/test_scenarios.py` charge ce fichier dans Home Assistant à côté de l'intégration et
vérifie, contre le simulateur de PAC, ce qui est écrit pour chaque scénario et pour chaque
réglage. `tests/test_dashboard.py` vérifie que chaque réglage est modifiable depuis les cartes.

### À vérifier sur votre PAC

* que le cycle anti-légionelle démarre bien quand son heure est déplacée de cette façon ; la
  variable « cycle » de la PAC (`2_Legionela_Cikel`) peut espacer les cycles de plusieurs
  semaines ;
* la numérotation des jours : 1 = lundi … 7 = dimanche.
