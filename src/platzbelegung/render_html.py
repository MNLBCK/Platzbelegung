"""HTML-Generierung aus Belegungsslots mittels Jinja2.

Erzeugt eine eigenständige, offline-fähige HTML-Datei aus
``OccupancySlot``-Objekten.  Die Jinja2-Vorlage in
``templates/occupancy.html.j2`` enthält das gesamte Layout inkl. CSS,
sodass kein externer Aufruf erforderlich ist.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from platzbelegung.models import OccupancySlot
from platzbelegung.parser import group_by_date, group_by_venue

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "occupancy.html.j2"

_WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
_MONTHS_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _format_date_de(d: date) -> str:
    weekday = _WEEKDAYS_DE[d.weekday()]
    month = _MONTHS_DE[d.month]
    return f"{weekday}, {d.day:02d}. {month} {d.year}"


def render_html(
    slots: list[OccupancySlot],
    output_path: str | Path,
    generated_at: str = "",
    template_path: str | Path | None = None,
) -> Path:
    """Generiert eine statische HTML-Datei aus Belegungsslots.

    Args:
        slots: Alle zu zeigenden Belegungsslots.
        output_path: Pfad, unter dem die HTML-Datei gespeichert wird.
        generated_at: Zeitstempel der Datenerzeugung (wird im Header angezeigt).
        template_path: Optionaler Pfad zu einer eigenen Jinja2-Vorlage.
            Standard: ``templates/occupancy.html.j2``.

    Returns:
        Pfad der erstellten HTML-Datei.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as exc:
        raise ImportError(
            "Jinja2 ist nicht installiert. Bitte 'pip install jinja2' ausführen."
        ) from exc

    tmpl_path = Path(template_path or _TEMPLATE_PATH)
    env = Environment(
        loader=FileSystemLoader(str(tmpl_path.parent)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    by_venue = group_by_venue(slots)
    venue_data = []
    for venue, venue_slots in sorted(by_venue.items(), key=lambda kv: str(kv[0])):
        by_date = group_by_date(venue_slots)
        days = [
            {
                "date": d,
                "date_formatted": _format_date_de(d),
                "slots": sorted(day_slots, key=lambda s: s.start_time),
            }
            for d, day_slots in sorted(by_date.items())
        ]
        venue_data.append({"venue": venue, "days": days})

    template = env.get_template(tmpl_path.name)
    html = template.render(
        venues=venue_data,
        generated_at=generated_at,
        slot_count=len(slots),
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    return output_path
