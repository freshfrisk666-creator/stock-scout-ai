from __future__ import annotations

import sys
import types

from runner.daily_runner import run_once


def test_run_once_delegates_to_main(monkeypatch):
    calls = {}

    fake_main = types.ModuleType("main")

    def fake_load_config(path):
        calls["config_path"] = path
        return {"ok": True}

    def fake_run_pipeline(cfg):
        calls["config"] = cfg
        return (
            [1, 2],
            [1],
            [1, 2, 3],
            {"equity": 100000.0},
            "STATUS",
            [{"ticker": "AAA", "reason": "TARGET_CLOSE"}],
        )

    fake_main.load_config = fake_load_config
    fake_main.run_pipeline = fake_run_pipeline
    monkeypatch.setitem(sys.modules, "main", fake_main)

    result = run_once("config/test.yaml")

    assert calls == {"config_path": "config/test.yaml", "config": {"ok": True}}
    assert result["scanned"] == 2
    assert result["top10"] == 1
    assert result["open_positions"] == 3
    assert result["closed_this_run"] == 1
    assert result["snapshot"]["equity"] == 100000.0


def test_run_once_accepts_default_path(monkeypatch):
    fake_main = types.ModuleType("main")
    fake_main.load_config = lambda path: {"path": path}
    fake_main.run_pipeline = lambda cfg: ([], [], [], {}, [], [])
    monkeypatch.setitem(sys.modules, "main", fake_main)

    result = run_once()

    assert result["config_path"] == "config/config.yaml"
    assert result["scanned"] == 0
    assert result["closed_this_run"] == 0
