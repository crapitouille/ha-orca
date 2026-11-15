"""Génère les entrées config.yml des familles ajoutées (programmes horaires,
anti-légionelle, alarmes, puissance/débit, heures de fonctionnement, vacances)."""
import sys

all_fields = {l.strip() for l in open(sys.argv[1]) if l.strip()}
out = []
seen_tags = set()

def entry(tag, id_, en, si, type_, hc=0, unit=None, value_map=None, adj=None, desc=""):
    if tag not in all_fields:
        raise SystemExit(f"tag inconnu dans all_fields: {tag}")
    if tag in seen_tags:
        raise SystemExit(f"tag en double: {tag}")
    seen_tags.add(tag)
    l = [f"- tag: {tag}", f"  id: {id_}", "  name:", f'    en: "{en}"', f'    si: "{si}"',
         f'  description: "{desc}"', f'  type: "{type_}"']
    if unit is not None:
        l.append(f'  unit: "{unit}"')
    if value_map:
        l.append("  value_map:")
        l += [f'    {k}: "{v}"' for k, v in value_map.items()]
    l.append("  adjustable:")
    if adj is True:
        l.append("    enabled: true")
    elif adj:
        l += ["    enabled: true", "    range:", f"      min: {adj[0]}", f"      max: {adj[1]}", f"      step: {adj[2]}"]
    else:
        l.append("    enabled: false")
    l.append(f"  heating_circuit: {hc}")
    out.append("\n".join(l))

def section(title):
    out.append(f"## {title}")

HOUR, MINUTE = (0, 23, 1), (0, 59, 1)
PROGRAMMES = {0: "24h", 1: "program 1", 2: "program 2", 3: "program 3", 4: "program 4", 5: "program 5"}

# ---------------------------------------------------------------- programmes horaires
section("Timer programmes 1-5 (casovniki), 3 periods each")
DAYS = [("Ponedeljek", "mon", "monday", "ponedeljek"), ("Torek", "tue", "tuesday", "torek"),
        ("Sreda", "wed", "wednesday", "sreda"), ("Cetrtek", "thu", "thursday", "četrtek"),
        ("Petek", "fri", "friday", "petek"), ("Sobota", "sat", "saturday", "sobota"),
        ("Nedelja", "sun", "sunday", "nedelja")]
TIMES = [("Ura_ON", "on_hour", "on hour", "ura vklopa", HOUR, "h"),
         ("Minute_ON", "on_minute", "on minute", "minuta vklopa", MINUTE, "min"),
         ("Ura_OFF", "off_hour", "off hour", "ura izklopa", HOUR, "h"),
         ("Minute_OFF", "off_minute", "off minute", "minuta izklopa", MINUTE, "min")]
for n in range(1, 6):
    for p in range(1, 4):
        for sl, key, en, si, rng, unit in TIMES:
            entry(f"2_TIMER_{n}_{sl}_{p}", f"timer{n}_p{p}_{key}",
                  f"timer {n} period {p} {en}", f"časovnik {n} obdobje {p} {si}",
                  "integer", unit=unit, adj=rng)
        for sl, key, en, si in DAYS:
            entry(f"2_TIMER_{n}_{sl}_{p}", f"timer{n}_p{p}_{key}",
                  f"timer {n} period {p} {en}", f"časovnik {n} obdobje {p} {si}",
                  "boolean", adj=True)

section("Timer programme selection")
entry("2_Izbira_TIMERJA_SV", "wh_timer_programme", "hot water timer programme",
      "časovni program sanitarne vode", "multimode", hc=4, value_map=PROGRAMMES)
entry("2_Izbira_TIMERJA_ZALOG", "buffer_timer_programme", "buffer timer programme",
      "časovni program zalogovnika", "multimode", hc=5, value_map=PROGRAMMES)
entry("2_Izbira_TIMERJA_TISJE", "silent_timer_programme", "silent mode timer programme",
      "časovni program tihega delovanja", "multimode", value_map=PROGRAMMES)

# ---------------------------------------------------------------- anti-légionelle
section("Anti-legionella programme (protilegionelni program)")
entry("2_Legionela_vklop", "legionella_turned_on", "legionella programme", "protilegionelni program",
      "boolean", hc=4, adj=True)
entry("2_Temperatura_legionela", "legionella_temp", "legionella temperature",
      "temperatura protilegionelnega programa", "float", hc=4, unit="°C", adj=(60.0, 65.0, 0.5))
entry("2_On_Dan_Legionella", "legionella_day", "legionella start day", "dan pričetka protilegionelnega programa",
      "integer", hc=4, unit="", adj=(1, 7, 1), desc="1-7, dan v tednu")
entry("2_On_Ura_Legionella", "legionella_hour", "legionella start hour", "ura pričetka protilegionelnega programa",
      "integer", hc=4, unit="h", adj=HOUR)
entry("2_On_Min_Legionella", "legionella_minute", "legionella start minute", "minuta pričetka protilegionelnega programa",
      "integer", hc=4, unit="min", adj=MINUTE)
entry("2_Legionela_Cikel", "legionella_cycle", "legionella cycle", "cikel protilegionelnega programa",
      "integer", hc=4, unit="")
entry("2_Legionela_MAX_CAS", "legionella_max_time", "legionella max duration", "najdaljši čas protilegionelnega programa",
      "integer", hc=4, unit="min")

# ---------------------------------------------------------------- alarmes (lecture seule)
section("Alarms (read only)")
for tag, id_, en, si in [
    ("2_JE_ALARM", "alarm_active", "alarm active", "alarm aktiven"),
    ("2_Alarm_skupna_napaka", "alarm_common_fault", "alarm common fault", "alarm skupna napaka"),
    ("2_Alarm_ni_pretoka", "alarm_no_flow", "alarm no flow", "alarm ni pretoka"),
    ("2_Alarm_pretocno_stikalo", "alarm_flow_switch", "alarm flow switch", "alarm pretočno stikalo"),
    ("2_Alarm_prenizka_temp_TC", "alarm_hp_temp_low", "alarm heat pump temperature too low", "alarm prenizka temperatura TČ"),
    ("2_Alarm_Talno", "alarm_floor", "alarm floor heating", "alarm talno"),
    ("2_Alarm_Talno_VF2", "alarm_floor_vf2", "alarm floor heating VF2", "alarm talno VF2"),
    ("2_Alarm_RF1", "alarm_rf1", "alarm room sensor 1", "alarm prostorski senzor 1"),
    ("2_Alarm_RF2", "alarm_rf2", "alarm room sensor 2", "alarm prostorski senzor 2"),
    ("2_Alarm_RF3", "alarm_rf3", "alarm room sensor 3", "alarm prostorski senzor 3"),
]:
    entry(tag, id_, en, si, "boolean")
entry("2_Vrsta_alarma", "alarm_type", "alarm type", "vrsta alarma", "integer", unit="")
entry("2_NAPAKA", "error_code", "error code", "napaka", "integer", unit="")

# ---------------------------------------------------------------- puissance / débit (lecture seule)
section("Power and flow (read only)")
entry("2_Moc_TC", "hp_power", "heat pump power", "moč toplotne črpalke", "float", unit="%")
for tag, id_, en, si in [
    ("2_Limita_moci_pri_OGR", "power_limit_heating", "power limit heating", "limita moči pri ogrevanju"),
    ("2_Limita_moci_pri_SV", "power_limit_water", "power limit hot water", "limita moči pri sanitarni vodi"),
    ("2_Limita_moci_pri_HLAJ", "power_limit_cooling", "power limit cooling", "limita moči pri hlajenju"),
    ("2_Max_moc_TC_TISJA", "max_power_silent", "max power silent mode", "največja moč v tihem delovanju"),
    ("2_Max_moc_TC_pri_ZALOG", "max_power_buffer", "max power buffer", "največja moč pri zalogovniku"),
    ("2_Min_moc_TC_pri_SV", "min_power_water", "min power hot water", "najmanjša moč pri sanitarni vodi"),
    ("2_Min_moc_TC_pri_ZALOG", "min_power_buffer", "min power buffer", "najmanjša moč pri zalogovniku"),
    ("2_PV_Max_moc_TC", "pv_max_power", "pv max power", "največja moč pri PV"),
    ("2_PV_Max_moc_TC_HL", "pv_max_power_cooling", "pv max power cooling", "največja moč pri PV hlajenje"),
]:
    entry(tag, id_, en, si, "float", unit="%")
entry("2_I_Pretok", "input_flow", "flow input", "vhod pretok", "integer", unit="")
entry("2_I_Kompresor", "input_compressor", "compressor input", "vhod kompresor", "integer", unit="")

# ---------------------------------------------------------------- heures de fonctionnement (lecture seule)
section("Operating hours (read only). Total = thousands * 1000 + units")
entry("2_URE_Komp_XXX000", "compressor_hours_thousands", "compressor operating hours thousands",
      "ure delovanja kompresorja tisočice", "integer", unit="")
entry("2_URE_Komp_000XXX", "compressor_hours_units", "compressor operating hours units",
      "ure delovanja kompresorja enice", "integer", unit="h")
entry("2_URE_EH_XXX000", "heater_hours_thousands", "electric heater operating hours thousands",
      "ure delovanja električnega grelca tisočice", "integer", unit="")
entry("2_URE_EH_000XXX", "heater_hours_units", "electric heater operating hours units",
      "ure delovanja električnega grelca enice", "integer", unit="h")

# ---------------------------------------------------------------- vacances
section("Holiday mode (pocitniski rezim)")
entry("2_POCITNISKI", "holiday_turned_on", "holiday mode", "počitniški režim", "boolean", adj=True)
entry("2_Dan_pocitniski", "holiday_day", "holiday end day", "počitnice do dan", "integer", unit="", adj=(1, 31, 1))
entry("2_Mesec_pocitniski", "holiday_month", "holiday end month", "počitnice do mesec", "integer", unit="", adj=(1, 12, 1))
entry("2_Leto_pocitniski", "holiday_year", "holiday end year", "počitnice do leto", "integer", unit="", adj=(0, 99, 1),
      desc="Dvomestno leto (25 = 2025)")

# ---------------------------------------------------------------- eau chaude : régime bas
section("Hot water: lower temperature regime (outside the timer programme)")
entry("2_Temp_vode_sanitarna_NIZJA", "wh_reduced_temp", "hot water reduced temperature",
      "nižja temperatura sanitarne vode", "float", hc=4, unit="°C", adj=(10.0, 60.0, 0.1),
      desc="Nižji temperaturni režim: aktiven, ko časovni program ni aktiven")
entry("2_Temp_zelena_SV", "wh_active_setpoint", "hot water current desired temperature",
      "trenutna želena temperatura sanitarne vode", "float", hc=4, unit="°C")

header = """
################################################################################
# Added families: timer programmes, anti-legionella, alarms, power and flow,
# operating hours, holiday mode, hot water lower temperature regime.
# Type "integer" = whole number sent and received as is (hours, minutes, days),
# unlike "float" which is a single-decimal value stored x10.
################################################################################
"""
print(header + "\n" + "\n\n".join(out))
sys.stderr.write(f"{len(seen_tags)} variables ajoutées\n")
