"""Tests für den Parser (parser.py)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from platzbelegung.models import Game, OccupancySlot, TeamSide, Venue
from platzbelegung.parser import (
    extract_venue,
    games_to_occupancy,
    group_by_date,
    group_by_venue,
)

CLUB_ID = "CLUB001"

_HOME_SIDE = TeamSide(
    id="SIDE001",
    club_id=CLUB_ID,
    name="SKV Hochberg",
    kind="Herren",
)
_AWAY_SIDE = TeamSide(
    id="SIDE002",
    club_id="CLUB002",
    name="FC Gegner",
    kind="Herren",
)


def _make_game(
    kick_off: datetime,
    address: str,
    home_club: str = CLUB_ID,
    kind: str = "Herren",
) -> Game:
    home = TeamSide(id="H", club_id=home_club, name="SKV Hochberg", kind=kind)
    away = TeamSide(id="A", club_id="CLUB002", name="FC Gegner", kind=kind)
    return Game(
        id="G1",
        kick_off=kick_off,
        home_side=home,
        away_side=away,
        league="Kreisliga A",
        squad="Herren",
        address=address,
    )


class TestExtractVenue:
    def test_full_address(self):
        venue = extract_venue(
            "Kunstrasenplatz, Sportanlage Hochberg, Hauptstr. 1, 70000 Stuttgart"
        )
        assert venue.name == "Kunstrasenplatz"
        assert venue.address == "Sportanlage Hochberg, Hauptstr. 1, 70000 Stuttgart"

    def test_single_part(self):
        venue = extract_venue("Unbekannter Platz")
        assert venue.name == "Unbekannter Platz"
        assert venue.address == "Unbekannter Platz"

    def test_empty_address(self):
        venue = extract_venue("")
        assert venue.name == "Unbekannt"
        assert venue.address == ""

    def test_two_parts(self):
        venue = extract_venue("Sportplatz, Musterstraße 1")
        assert venue.name == "Sportplatz"
        assert venue.address == "Musterstraße 1"

    def test_venue_str(self):
        venue = Venue(name="Kunstrasenplatz", address="Hauptstr. 1, 70000 Stuttgart")
        assert "Kunstrasenplatz" in str(venue)
        assert "Hauptstr." in str(venue)

    def test_venue_str_same_name_address(self):
        venue = Venue(name="Hauptplatz", address="Hauptplatz")
        assert str(venue) == "Hauptplatz"


class TestGamesToOccupancy:
    def test_home_game_creates_slot(self):
        game = _make_game(datetime(2026, 3, 15, 15, 0), "Platz A, Straße 1, 70001 Stadt")
        slots = games_to_occupancy([game], CLUB_ID, {"Herren": 90})
        assert len(slots) == 1
        slot = slots[0]
        assert slot.is_home_game is True
        assert slot.team_kind == "Herren"
        assert slot.opponent == "FC Gegner"

    def test_away_game_no_slot(self):
        game = _make_game(
            datetime(2026, 3, 15, 15, 0),
            "Platz A, Straße 1, 70001 Stadt",
            home_club="OTHER_CLUB",
        )
        slots = games_to_occupancy([game], CLUB_ID, {"Herren": 90})
        assert len(slots) == 0

    def test_start_time_includes_buffer(self):
        game = _make_game(datetime(2026, 3, 15, 15, 0), "Platz A, Straße 1")
        slots = games_to_occupancy([game], CLUB_ID, {"Herren": 90})
        # 15:00 - 15 min buffer = 14:45
        assert slots[0].start_time == time(14, 45)

    def test_end_time_calculated(self):
        game = _make_game(datetime(2026, 3, 15, 15, 0), "Platz A, Straße 1")
        slots = games_to_occupancy([game], CLUB_ID, {"Herren": 90})
        # 15:00 + 90 min = 16:30
        assert slots[0].end_time == time(16, 30)

    def test_uses_default_duration_if_missing(self):
        game = _make_game(datetime(2026, 3, 15, 15, 0), "Platz A, Straße 1", kind="Herren")
        slots = games_to_occupancy([game], CLUB_ID, {})  # no durations
        # default 90 min → 15:00 + 90 = 16:30
        assert slots[0].end_time == time(16, 30)

    def test_slots_sorted_by_date_and_time(self):
        games = [
            _make_game(datetime(2026, 3, 22, 15, 0), "Platz A"),
            _make_game(datetime(2026, 3, 15, 11, 0), "Platz A"),
            _make_game(datetime(2026, 3, 15, 15, 0), "Platz A"),
        ]
        slots = games_to_occupancy(games, CLUB_ID, {"Herren": 90})
        dates = [(s.date, s.start_time) for s in slots]
        assert dates == sorted(dates)


class TestGroupByVenue:
    def test_groups_correctly(self):
        venue_a = Venue(name="Platz A", address="Straße 1")
        venue_b = Venue(name="Platz B", address="Straße 2")
        slots = [
            OccupancySlot(venue=venue_a, date=date(2026, 3, 15), start_time=time(15, 0),
                          end_time=time(16, 30), team_name="Herren", team_kind="Herren",
                          opponent="FC X", league="Liga A"),
            OccupancySlot(venue=venue_b, date=date(2026, 3, 15), start_time=time(11, 0),
                          end_time=time(12, 10), team_name="D-Jugend", team_kind="D-Junioren",
                          opponent="FC Y", league="Liga B"),
            OccupancySlot(venue=venue_a, date=date(2026, 3, 22), start_time=time(13, 0),
                          end_time=time(14, 30), team_name="Herren II", team_kind="Herren",
                          opponent="SV Z", league="Liga A"),
        ]
        grouped = group_by_venue(slots)
        assert len(grouped[venue_a]) == 2
        assert len(grouped[venue_b]) == 1


class TestGroupByDate:
    def test_groups_correctly(self):
        venue_a = Venue(name="Platz A", address="Straße 1")
        slots = [
            OccupancySlot(venue=venue_a, date=date(2026, 3, 15), start_time=time(15, 0),
                          end_time=time(16, 30), team_name="Herren", team_kind="Herren",
                          opponent="FC X", league="Liga A"),
            OccupancySlot(venue=venue_a, date=date(2026, 3, 22), start_time=time(11, 0),
                          end_time=time(12, 10), team_name="Herren II", team_kind="Herren",
                          opponent="FC Y", league="Liga A"),
            OccupancySlot(venue=venue_a, date=date(2026, 3, 15), start_time=time(11, 0),
                          end_time=time(12, 10), team_name="D-Jugend", team_kind="D-Junioren",
                          opponent="SV Z", league="Liga B"),
        ]
        grouped = group_by_date(slots)
        assert len(grouped[date(2026, 3, 15)]) == 2
        assert len(grouped[date(2026, 3, 22)]) == 1


class TestScrapedGamesToOccupancy:
    def test_creates_slot_from_scraped_game(self):
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1",
            venue_name="Platz 1",
            date="28.03.2026",
            time="14:00",
            home_team="SKV Hochberg",
            guest_team="FC Muster",
            competition="Kreisliga A",
            start_date="2026-03-28T14:00:00",
            scraped_at="2026-03-30T09:00:00Z",
        )
        slots = scraped_games_to_occupancy([game], preparation_buffer_minutes=15, default_duration_minutes=90)
        assert len(slots) == 1
        s = slots[0]
        assert s.date == date(2026, 3, 28)
        assert s.start_time == time(13, 45)  # 14:00 - 15min
        assert s.end_time == time(15, 30)    # 14:00 + 90min
        assert s.team_name == "SKV Hochberg"
        assert s.opponent == "FC Muster"
        assert s.league == "Kreisliga A"

    def test_duration_from_competition_name(self):
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1",
            venue_name="Platz",
            date="01.04.2026",
            time="10:00",
            home_team="TSV",
            guest_team="VfB",
            competition="B-Junioren Kreisliga",
            start_date="2026-04-01T10:00:00",
            scraped_at="",
        )
        slots = scraped_games_to_occupancy(
            [game],
            preparation_buffer_minutes=15,
            default_duration_minutes=90,
            game_durations={"B-Junioren": 70},
        )
        assert len(slots) == 1
        # Duration should be 70 min
        assert slots[0].end_time == time(11, 10)  # 10:00 + 70min

    def test_invalid_start_date_skipped(self):
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1", venue_name="X", date="", time="",
            home_team="A", guest_team="B", competition="Liga",
            start_date="not-a-date", scraped_at="",
        )
        slots = scraped_games_to_occupancy([game])
        assert slots == []

    def test_results_sorted_by_date_and_time(self):
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        games = [
            ScrapedGame(
                venue_id="V1", venue_name="P", date="05.04.2026", time="14:00",
                home_team="A", guest_team="B", competition="Liga",
                start_date="2026-04-05T14:00:00", scraped_at="",
            ),
            ScrapedGame(
                venue_id="V1", venue_name="P", date="01.04.2026", time="10:00",
                home_team="C", guest_team="D", competition="Liga",
                start_date="2026-04-01T10:00:00", scraped_at="",
            ),
        ]
        slots = scraped_games_to_occupancy(games)
        assert slots[0].date < slots[1].date


class TestHomeGameFilteringExplicit:
    """Explizite Tests für die Heimspiel-Filterung und Platzhalter-Zeilen."""

    def test_away_game_at_foreign_venue_excluded(self):
        """Auswärtsspiel auf einem fremden Platz erzeugt keinen Belegungsslot.

        Der Verein spielt auswärts: home_side.club_id != CLUB_ID.
        Der eigene Platz ist dabei nicht belegt.
        """
        game = _make_game(
            datetime(2026, 4, 10, 15, 0),
            "Auswärtsplatz, Fremde Straße 5, 80001 Fremdstadt",
            home_club="FOREIGN_CLUB",
        )
        slots = games_to_occupancy([game], CLUB_ID, {"Herren": 90})
        assert slots == [], "Auswärtsspiel darf keinen Slot erzeugen"

    def test_mixed_home_and_away_only_home_included(self):
        """Aus einer gemischten Spielliste werden nur Heimspiele berücksichtigt."""
        home_game = _make_game(
            datetime(2026, 4, 5, 15, 0), "Heimplatz, Heimstraße 1, 70001 Heimstadt"
        )
        away_game = _make_game(
            datetime(2026, 4, 12, 15, 0),
            "Auswärtsplatz, Fremde Str. 1, 80001 Fremdstadt",
            home_club="FOREIGN_CLUB",
        )
        slots = games_to_occupancy([home_game, away_game], CLUB_ID, {"Herren": 90})
        assert len(slots) == 1
        assert slots[0].venue.name == "Heimplatz"


class TestScrapedGamesToOccupancyFiltering:
    """Explizite Tests für Filterung von Platzhalter-Zeilen und Sonderfällen."""

    def test_spielfrei_guest_excluded(self):
        """ScrapedGame mit 'spielfrei' als Gegner darf keinen Belegungsslot erzeugen."""
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1",
            venue_name="Platz 1",
            date="05.04.2026",
            time="11:00",
            home_team="SKV Hochberg",
            guest_team="spielfrei",
            competition="Kreisliga A",
            start_date="2026-04-05T11:00:00",
            scraped_at="",
        )
        slots = scraped_games_to_occupancy([game])
        assert slots == [], "'spielfrei'-Eintrag darf keinen Belegungsslot erzeugen"

    def test_spielfrei_uppercase_excluded(self):
        """'Spielfrei' in gemischter Groß-/Kleinschreibung wird ebenfalls gefiltert."""
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1",
            venue_name="Platz",
            date="05.04.2026",
            time="11:00",
            home_team="SKV Hochberg",
            guest_team="Spielfrei",
            competition="Liga",
            start_date="2026-04-05T11:00:00",
            scraped_at="",
        )
        slots = scraped_games_to_occupancy([game])
        assert slots == []

    def test_empty_guest_team_excluded(self):
        """ScrapedGame ohne Gegner wird übersprungen."""
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="V1",
            venue_name="Platz",
            date="05.04.2026",
            time="11:00",
            home_team="SKV Hochberg",
            guest_team="",
            competition="Liga",
            start_date="2026-04-05T11:00:00",
            scraped_at="",
        )
        slots = scraped_games_to_occupancy([game])
        assert slots == []

    def test_malformed_venue_name_does_not_crash(self):
        """ScrapedGame mit leerem Venue-Namen wird trotzdem verarbeitet."""
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        game = ScrapedGame(
            venue_id="",
            venue_name="",
            date="05.04.2026",
            time="14:00",
            home_team="SKV Hochberg",
            guest_team="FC Muster",
            competition="Liga",
            start_date="2026-04-05T14:00:00",
            scraped_at="",
        )
        slots = scraped_games_to_occupancy([game])
        assert len(slots) == 1
        assert slots[0].venue.name == ""

    def test_valid_game_alongside_spielfrei(self):
        """Nur das echte Spiel wird konvertiert; der spielfrei-Eintrag wird verworfen."""
        from platzbelegung.models import ScrapedGame
        from platzbelegung.parser import scraped_games_to_occupancy

        games = [
            ScrapedGame(
                venue_id="V1",
                venue_name="Platz 1",
                date="05.04.2026",
                time="14:00",
                home_team="SKV Hochberg",
                guest_team="FC Muster",
                competition="Liga",
                start_date="2026-04-05T14:00:00",
                scraped_at="",
            ),
            ScrapedGame(
                venue_id="V1",
                venue_name="Platz 1",
                date="12.04.2026",
                time="14:00",
                home_team="SKV Hochberg",
                guest_team="spielfrei",
                competition="Liga",
                start_date="2026-04-12T14:00:00",
                scraped_at="",
            ),
        ]
        slots = scraped_games_to_occupancy(games)
        assert len(slots) == 1
        assert slots[0].opponent == "FC Muster"
