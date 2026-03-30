"""Tests für render_html.py (Jinja2-HTML-Generierung)."""

from __future__ import annotations

from datetime import date, time

import pytest

from platzbelegung.models import OccupancySlot, Venue
from platzbelegung.render_html import render_html


def _make_slots() -> list[OccupancySlot]:
    venue = Venue(name="Kunstrasenplatz", address="Hauptstr. 1, 70000 Stuttgart")
    return [
        OccupancySlot(
            venue=venue,
            date=date(2026, 4, 5),
            start_time=time(10, 45),
            end_time=time(12, 15),
            team_name="SKV Hochberg",
            team_kind="Herren",
            opponent="FC Muster",
            league="Kreisliga A",
        ),
        OccupancySlot(
            venue=venue,
            date=date(2026, 4, 5),
            start_time=time(14, 45),
            end_time=time(16, 15),
            team_name="SKV Hochberg II",
            team_kind="Herren",
            opponent="SV Test",
            league="Kreisliga B",
        ),
    ]


class TestRenderHtml:
    def test_creates_file(self, tmp_path):
        output = tmp_path / "out.html"
        render_html(_make_slots(), output_path=output)
        assert output.exists()

    def test_file_is_valid_html(self, tmp_path):
        output = tmp_path / "out.html"
        render_html(_make_slots(), output_path=output)
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content

    def test_contains_venue_name(self, tmp_path):
        output = tmp_path / "out.html"
        render_html(_make_slots(), output_path=output)
        content = output.read_text(encoding="utf-8")
        assert "Kunstrasenplatz" in content

    def test_contains_team_names(self, tmp_path):
        output = tmp_path / "out.html"
        render_html(_make_slots(), output_path=output)
        content = output.read_text(encoding="utf-8")
        assert "SKV Hochberg" in content
        assert "FC Muster" in content

    def test_contains_generated_at(self, tmp_path):
        output = tmp_path / "out.html"
        render_html(_make_slots(), output_path=output, generated_at="2026-03-30T09:54:51Z")
        content = output.read_text(encoding="utf-8")
        assert "2026-03-30T09:54:51Z" in content

    def test_empty_slots_shows_empty_state(self, tmp_path):
        output = tmp_path / "empty.html"
        render_html([], output_path=output)
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        # Should show empty state message
        assert "platzbelegung scrape" in content

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "nested" / "deep" / "out.html"
        render_html(_make_slots(), output_path=output)
        assert output.exists()

    def test_returns_output_path(self, tmp_path):
        output = tmp_path / "result.html"
        returned = render_html(_make_slots(), output_path=output)
        assert returned == output
