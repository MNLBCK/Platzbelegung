"""Konfiguration für die Platzbelegungs-Übersicht."""

from __future__ import annotations

from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Vereins-Konfiguration
# ---------------------------------------------------------------------------

# Vereins-ID des SKV Hochberg (Württemberg)
CLUB_ID: str = "00ES8GNAVO00000PVV0AG08LVUPGND5I"

# Basis-URL der lokal laufenden fussball.de REST API
# (https://github.com/iste2/Fu-ball.de-REST-API)
API_BASE_URL: str = "http://localhost:5000"

# Aktuelle Saison (2025/2026)
SEASON: str = "2526"


# ---------------------------------------------------------------------------
# Zeitraum-Berechnung
# ---------------------------------------------------------------------------

def get_date_range() -> tuple[date, date]:
    """Gibt den Zeitraum zurück, der abgefragt werden soll.

    Der Zeitraum umfasst den aktuellen Monat sowie den Monat, der in
    3 Wochen beginnt (kann der gleiche oder der nächste Monat sein).
    Zurückgegeben wird (erster_tag, letzter_tag) des gesamten Bereichs.
    """
    today = date.today()
    in_three_weeks = today + timedelta(weeks=3)

    start = today.replace(day=1)

    # Letzter Tag des Monats, der in 3 Wochen liegt
    if in_three_weeks.month == 12:
        end = in_three_weeks.replace(day=31)
    else:
        end = in_three_weeks.replace(
            month=in_three_weeks.month + 1, day=1
        ) - timedelta(days=1)

    return start, end
