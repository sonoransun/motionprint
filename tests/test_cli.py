"""CLI argument handling: palette, hex overrides, tempo/speed composition."""

from __future__ import annotations

import pytest

from motionprint import cli


@pytest.fixture
def captured_generate(monkeypatch, tmp_path):
    """Replace scene.generate with a capture so tests stay fast and headless."""
    captured: dict = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return "0" * 64

    monkeypatch.setattr(cli, "generate", fake_generate)
    return captured


def _run(args, tmp_path):
    out = tmp_path / "out.mp4"
    return ["-s", "hello", "-o", str(out), *args]


def test_default_invocation_uses_default_palette_and_speed_one(captured_generate, tmp_path, capsys):
    cli.main(_run([], tmp_path))
    assert captured_generate["palette"].name == "default"
    assert captured_generate["speed_multiplier"] == 1.0


def test_named_palette_passed_through(captured_generate, tmp_path, capsys):
    cli.main(_run(["--palette", "vibrant"], tmp_path))
    assert captured_generate["palette"].name == "vibrant"


def test_tempo_times_speed(captured_generate, tmp_path, capsys):
    cli.main(_run(["--tempo", "energetic", "--speed", "0.5"], tmp_path))
    assert captured_generate["speed_multiplier"] == 1.0

    captured_generate.clear()
    cli.main(_run(["--tempo", "calm", "--speed", "2.0"], tmp_path))
    assert captured_generate["speed_multiplier"] == 1.0

    captured_generate.clear()
    cli.main(_run(["--tempo", "energetic", "--speed", "2.0"], tmp_path))
    assert captured_generate["speed_multiplier"] == 4.0


def test_hex_override_layers_on_preset(captured_generate, tmp_path, capsys):
    cli.main(_run(["--palette", "vibrant", "--primary-color", "#ff0000"], tmp_path))
    spec = captured_generate["palette"]
    assert spec.primary_override == pytest.approx((1.0, 0.0, 0.0))
    # Secondary still follows the vibrant preset bands (no override).
    assert spec.secondary_override is None
    assert spec.secondary_sat_range is not None


def test_rejects_unknown_palette(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(_run(["--palette", "neon"], tmp_path))


def test_rejects_bad_hex(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(_run(["--primary-color", "not-a-color"], tmp_path))


def test_rejects_speed_out_of_range(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(_run(["--speed", "0"], tmp_path))
    with pytest.raises(SystemExit):
        cli.main(_run(["--speed", "50"], tmp_path))
