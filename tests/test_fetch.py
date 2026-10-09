"""chess.com fetch tests (T1.3) — no network, via a fake Transport."""

import json
from pathlib import Path

from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.fetch import FetchError, Response, Transport, fetch_all

FIX = Path(__file__).resolve().parent / "fixtures"
EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"

LIST = "https://api.chess.com/pub/player/paulmorphy/games/archives"
PAST = "https://api.chess.com/pub/player/paulmorphy/games/2026/08"
CUR = "https://api.chess.com/pub/player/paulmorphy/games/2026/09"


class FakeTransport(Transport):
    def __init__(self):
        self.responses: dict[str, list[Response]] = {}
        self.calls: list[tuple[str, dict]] = []

    def add(self, url: str, *responses: Response):
        self.responses[url] = list(responses)

    def get(self, url: str, headers: dict) -> Response:
        self.calls.append((url, headers))
        queue = self.responses.get(url, [])
        if not queue:
            return Response(404, {}, None, "")
        return queue.pop(0)


def _config(username: str = "PaulMorphy"):
    cfg = load_config(EXAMPLE)
    cfg.username = username
    return cfg


def _archive_payload() -> dict:
    return json.loads((FIX / "sample_archive.json").read_text())


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    return conn


def test_second_run_requests_only_newest_month(tmp_path):
    transport = FakeTransport()
    transport.add(LIST, Response(200, {}, {"archives": [PAST, CUR]}, ""))
    transport.add(PAST, Response(200, {}, {"games": []}, ""))
    transport.add(CUR, Response(200, {}, _archive_payload(), ""))

    conn = _db(tmp_path)
    fetch_all(conn, _config(), transport, tmp_path / "raw")

    transport.calls.clear()
    transport.responses.clear()
    transport.add(LIST, Response(200, {}, {"archives": [PAST, CUR]}, ""))
    transport.add(CUR, Response(200, {}, _archive_payload(), ""))

    fetch_all(conn, _config(), transport, tmp_path / "raw")

    urls = [u for u, _ in transport.calls]
    assert urls == [LIST, CUR]  # past month not re-requested
    conn.close()


def test_429_then_200_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("chesscoach.fetch.time.sleep", lambda s: None)

    transport = FakeTransport()
    transport.add(LIST, Response(200, {}, {"archives": [CUR]}, ""))
    transport.add(
        CUR,
        Response(429, {}, None, ""),
        Response(200, {}, _archive_payload(), ""),
    )

    conn = _db(tmp_path)
    result = fetch_all(conn, _config(), transport, tmp_path / "raw")
    assert result.inserted == 1
    assert result.errors == 0

    cur_calls = [u for u, _ in transport.calls if u == CUR]
    assert len(cur_calls) == 2
    conn.close()


def test_fetch_filters_rules_and_time_class(tmp_path):
    base_game = _archive_payload()["games"][0]  # PaulMorphy Opera game
    ok = dict(base_game)
    ok["uuid"] = "uuid-ok"

    chess960 = dict(base_game)
    chess960["uuid"] = "uuid-960"
    chess960["rules"] = "chess960"

    bullet = dict(base_game)
    bullet["uuid"] = "uuid-bullet"
    bullet["time_class"] = "bullet"

    transport = FakeTransport()
    transport.add(LIST, Response(200, {}, {"archives": [CUR]}, ""))
    transport.add(CUR, Response(200, {}, {"games": [ok, chess960, bullet]}, ""))

    cfg = _config()
    cfg.fetch.time_classes = ["blitz", "rapid", "daily"]  # bullet excluded

    conn = _db(tmp_path)
    result = fetch_all(conn, cfg, transport, tmp_path / "raw")
    assert result.inserted == 1
    assert result.filtered == 2

    uuids = [r["uuid"] for r in conn.execute("SELECT uuid FROM games")]
    assert uuids == ["uuid-ok"]
    conn.close()


def test_fetch_archive_list_error(tmp_path):
    transport = FakeTransport()
    transport.add(LIST, Response(500, {}, None, ""))

    conn = _db(tmp_path)
    try:
        fetch_all(conn, _config(), transport, tmp_path / "raw")
        raise AssertionError("expected FetchError")
    except FetchError:
        pass
    finally:
        conn.close()
