from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from bridge import resolve_ps3_cover_url
from cover_art import (ART_BASE, CATALOG_URL, MAX_XML, MISS_TTL, NETWORK_RETRY_SECONDS, CoverResolver,
                       load_local_cover_index,
                       artwork_regions, base_title, parse_catalog, serial_id, square_cover_url)
from presence_parser import LegacyPresence

PNG = b"\x89PNG\r\n\x1a\nimage"
JPEG = b"\xff\xd8\xffimage"
XML = b'''<datafile>
<game><id>NPEB90181</id><locale lang="EN"><title>Lost Planet 2</title></locale></game>
<game><id>BLUS30434</id><locale lang="EN"><title>Lost Planet 2</title></locale></game>
<game><id>BCES00050</id><locale lang="EN"><title>Folklore</title></locale></game>
<game><id>BLUS99999</id><locale lang="EN"><title>Lost Planet 3</title></locale></game>
</datafile>'''


def archive(data=XML):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("ps3tdb.xml", data)
    return buffer.getvalue()


def game(title="LOST PLANET 2 Co-op Demo", serial="NPEB90181_00", icon="https://sony.test/icon.png"):
    return LegacyPresence("online", "PS3", title, serial, None, icon)


class Response:
    def __init__(self, status=404, data=b""):
        self.status_code, self.data = status, data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def iter_content(self, _):
        yield self.data


class CoverArtTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        self.responses = {}
        self.session = Mock(headers={})
        self.session.get.side_effect = lambda url, **_: self.responses.get(url, Response())
        self.now = [10000.0]
        self.logs = []
        self.resolver = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0], log=self.logs.append)

    def urls(self):
        return [call.args[0] for call in self.session.get.call_args_list]

    def test_healthy_sony_cover_does_not_download_catalog(self):
        original = game().title_icon_url
        self.responses[original] = Response(200, PNG)
        self.responses[square_cover_url(original)] = Response(200, PNG)
        self.assertEqual(self.resolver.resolve(game(), original), square_cover_url(original))
        self.assertNotIn(CATALOG_URL, self.urls())
        self.assertFalse(self.session.trust_env)
        self.assertIn("PS3Presence", self.session.headers["User-Agent"])

    def test_exact_demo_serial_is_preferred(self):
        source = f"{ART_BASE}/EN/NPEB90181.jpg"
        self.responses[CATALOG_URL] = Response(200, archive())
        self.responses[source] = Response(200, JPEG)
        self.assertEqual(self.resolver.resolve(game(), game().title_icon_url), source)
        self.assertNotIn(f"{ART_BASE}/US/BLUS30434.jpg", self.urls())
        self.assertTrue(any("GameTDB" in line for line in self.logs))

    def test_missing_demo_uses_matching_full_game_not_sequel(self):
        source = f"{ART_BASE}/US/BLUS30434.jpg"
        self.responses[CATALOG_URL] = Response(200, archive())
        self.responses[source] = Response(200, JPEG)
        result = self.resolver.resolve(game(), game().title_icon_url)
        self.assertEqual(result, source)
        self.assertFalse(any("BLUS99999" in url for url in self.urls()))
        self.assertEqual(game().title_name, "LOST PLANET 2 Co-op Demo")

    def test_folklore_download_demo_matches_full_title(self):
        source = f"{ART_BASE}/EN/BCES00050.jpg"
        self.responses[CATALOG_URL] = Response(200, archive())
        self.responses[source] = Response(200, JPEG)
        self.assertEqual(self.resolver.resolve(game("Folklore™ - Download Demo", "NPEA90019_00"), None), source)

    def test_title_without_serial_can_still_match(self):
        source = f"{ART_BASE}/EN/BCES00050.jpg"
        self.responses[CATALOG_URL] = Response(200, archive())
        self.responses[source] = Response(200, JPEG)
        self.assertEqual(self.resolver.resolve(game("Folklore", None), None), source)

    def test_result_is_reused_after_restart_without_network(self):
        original = game().title_icon_url
        self.responses[original] = Response(200, PNG)
        self.assertEqual(self.resolver.resolve(game(), original), original)
        self.session.get.reset_mock()
        other = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0])
        self.assertEqual(other.resolve(game(), original), original)
        self.session.get.assert_not_called()

    def test_missing_result_retries_only_after_cooldown(self):
        self.responses[CATALOG_URL] = Response(200, archive())
        self.assertIsNone(self.resolver.resolve(game(), None))
        self.session.get.reset_mock()
        self.assertIsNone(self.resolver.resolve(game(), None))
        self.session.get.assert_not_called()
        self.now[0] += MISS_TTL + 1
        self.assertIsNone(self.resolver.resolve(game(), None))
        self.assertGreater(self.session.get.call_count, 0)

    def test_valid_sony_image_survives_unavailable_square_proxy(self):
        source = game().title_icon_url
        self.responses[source] = Response(200, PNG)
        self.assertEqual(self.resolver.resolve(game(), source), source)
        self.assertNotIn(CATALOG_URL, self.urls())

    def test_http_200_html_is_not_artwork(self):
        source = game().title_icon_url
        self.responses[source] = Response(200, b"<html>Error</html>")
        self.assertIsNone(self.resolver.resolve(game(), source))
        self.assertIn(CATALOG_URL, self.urls())

    def test_network_errors_do_not_stop_presence(self):
        self.session.get.side_effect = requests.ConnectionError("offline")
        self.assertIsNone(self.resolver.resolve(game(), None))

    def test_gametdb_https_timeout_recovers_over_http_and_remembers_route(self):
        secure = f"{ART_BASE}/EN/BCES00050.jpg"
        plain = secure.replace("https://", "http://", 1)
        def request(url, **_):
            if url.startswith("https://art.gametdb.com"):
                raise requests.ReadTimeout("HTTPS unavailable")
            return Response(200, JPEG) if url == plain else Response()
        self.session.get.side_effect = request
        self.assertTrue(self.resolver._is_image(secure))
        self.assertIn(plain, self.urls())
        self.session.get.reset_mock()
        self.assertTrue(self.resolver._is_image(secure))
        self.assertEqual(self.urls(), [plain])

    def test_http_fallback_never_applies_to_sony_or_arbitrary_sites(self):
        self.session.get.side_effect = requests.ReadTimeout("unavailable")
        self.assertIsNone(self.resolver._get("https://sony.test/icon.png", 100))
        self.assertIsNone(self.resolver._get("https://unrelated.test/file", 100))
        self.assertTrue(all(url.startswith("https://") for url in self.urls()))

    def test_gametdb_404_is_not_retried_over_http(self):
        self.assertIsNone(self.resolver._get(f"{ART_BASE}/EN/BCES00050.jpg", 100))
        self.assertEqual(len(self.urls()), 1)

    def test_http_catalog_and_image_produce_a_local_cover(self):
        source = f"{ART_BASE}/EN/NPEB90181.jpg"
        def request(url, **_):
            if url.startswith("https://www.gametdb.com") or url.startswith("https://art.gametdb.com"):
                raise requests.ConnectTimeout("HTTPS unavailable")
            if url == CATALOG_URL.replace("https://", "http://", 1):
                return Response(200, archive())
            if url == source.replace("https://", "http://", 1):
                return Response(200, JPEG)
            return Response()
        self.session.get.side_effect = request
        result = self.resolver.resolve(game(), None)
        self.assertEqual(result, source.replace("https://", "http://", 1))
        local = self.resolver.local_url(result)
        self.assertTrue(local.startswith("file:///"))
        self.assertEqual(next(self.path.glob("*.img")).read_bytes(), JPEG)
        self.assertEqual(load_local_cover_index(self.path), {game().title_id: local})
        offline = CoverResolver(self.path, session=Mock(headers={}), clock=lambda: self.now[0])
        self.assertEqual(offline.resolve(game(), None), result)
        offline.session.get.assert_not_called()

    def test_old_success_url_without_image_is_revalidated(self):
        key = json.dumps([game().title_id, "lost planet 2 co op demo", None], ensure_ascii=False)
        (self.path / "resolved.json").write_text(json.dumps({key: dict(at=self.now[0], url="https://broken.test/art.png")}), encoding="utf-8")
        self.responses[CATALOG_URL] = Response(200, archive())
        source = f"{ART_BASE}/EN/NPEB90181.jpg"
        self.responses[source] = Response(200, JPEG)
        restarted = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0])
        self.assertEqual(restarted.resolve(game(), None), source)
        self.assertIn("https://broken.test/art.png", self.urls())
        self.assertIsNotNone(restarted.local_url(source))

    def test_catalog_network_failure_retries_after_one_minute(self):
        self.responses[CATALOG_URL] = Response(503)
        self.assertIsNone(self.resolver.resolve(game(), None))
        self.responses[CATALOG_URL] = Response(200, archive())
        source = f"{ART_BASE}/US/BLUS30434.jpg"
        self.responses[source] = Response(200, JPEG)
        self.now[0] += NETWORK_RETRY_SECONDS + 1
        self.assertEqual(self.resolver.resolve(game(), None), source)
        self.assertEqual(self.urls().count(CATALOG_URL), 2)

    def test_network_failure_cache_does_not_block_retry_after_restart(self):
        self.session.get.side_effect = requests.ConnectionError("offline")
        self.assertIsNone(self.resolver.resolve(game(), None))
        self.now[0] += NETWORK_RETRY_SECONDS + 1
        self.session.get.side_effect = lambda url, **_: self.responses.get(url, Response())
        self.responses[CATALOG_URL] = Response(200, archive())
        source = f"{ART_BASE}/EN/NPEB90181.jpg"
        self.responses[source] = Response(200, JPEG)
        restarted = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0])
        self.assertEqual(restarted.resolve(game(), None), source)

    def test_old_hour_long_failure_cache_is_ignored_but_success_is_kept(self):
        key = json.dumps([game().title_id, "lost planet 2 co op demo", None], ensure_ascii=False)
        (self.path / "resolved.json").write_text(json.dumps({key: dict(at=self.now[0], url=None),
            "existing": dict(at=self.now[0], url="https://existing.test/cover.png")}), encoding="utf-8")
        self.responses[CATALOG_URL] = Response(200, archive())
        source = f"{ART_BASE}/EN/NPEB90181.jpg"
        self.responses[source] = Response(200, JPEG)
        restarted = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0])
        self.assertIn("existing", restarted._cache)
        self.assertEqual(restarted.resolve(game(), None), source)

    def test_stopped_worker_does_not_request_or_cache_missing_artwork(self):
        self.resolver.cancelled = lambda: True
        self.assertIsNone(self.resolver.resolve(game(), game().title_icon_url))
        self.session.get.assert_not_called()
        self.assertFalse((self.path / "resolved.json").exists())

    def test_lookup_deadline_prevents_more_network_requests(self):
        with patch("cover_art.time.monotonic", side_effect=[0, 31, 31, 31, 31]):
            self.assertIsNone(self.resolver.resolve(game(), game().title_icon_url))
        self.session.get.assert_not_called()

    def test_catalog_has_a_longer_read_timeout_than_artwork(self):
        self.resolver._get(CATALOG_URL, 1000)
        self.assertEqual(self.session.get.call_args.kwargs["timeout"], (3, 15))
        self.resolver._get("https://art.gametdb.com/cover.jpg", 1000)
        self.assertEqual(self.session.get.call_args.kwargs["timeout"], (3, 5))

    def test_stale_catalog_survives_catalog_server_failure(self):
        (self.path / "ps3tdb.xml").write_bytes(XML)
        self.now[0] = 2e10
        self.assertEqual(self.resolver._load_catalog(), parse_catalog(XML))
        self.assertIn(CATALOG_URL, self.urls())

    def test_cache_write_failure_is_nonfatal(self):
        source = game().title_icon_url
        self.responses[source] = Response(200, PNG)
        with patch("cover_art._write_atomically", side_effect=OSError("read-only")):
            self.assertEqual(self.resolver.resolve(game(), source), source)

    def test_invalid_archive_and_cache_are_nonfatal(self):
        (self.path / "resolved.json").write_text('{"wrong":{"at":"bad"}}', encoding="utf-8")
        resolver = CoverResolver(self.path, session=self.session, clock=lambda: self.now[0])
        self.responses[CATALOG_URL] = Response(200, b"not a zip")
        self.assertIsNone(resolver.resolve(game(), None))

    def test_catalog_rejects_entities_and_oversized_xml(self):
        for data in (b'<!DOCTYPE datafile [<!ENTITY x "danger">]><datafile/>', b"x" * (MAX_XML + 1)):
            with self.assertRaises(ValueError):
                parse_catalog(data)

    def test_serial_and_demo_normalization_keep_editions_and_numbers(self):
        self.assertEqual(serial_id("NPEB90181_00"), "NPEB90181")
        self.assertEqual(serial_id("BLUS-30434"), "BLUS30434")
        self.assertEqual(serial_id("../wrong"), "")
        self.assertEqual(base_title("LOST PLANET 2 Co-op Demo"), "lost planet 2")
        self.assertEqual(base_title("Folklore™ - Download Demo"), "folklore")
        self.assertEqual(base_title("Lost Planet 3"), "lost planet 3")
        self.assertEqual(base_title("Game: Definitive Edition"), "game definitive edition")
        self.assertEqual(artwork_regions("BLUS30434"), ("US", "EN"))

    def test_sony_generation_failure_still_uses_catalog(self):
        psn = Mock()
        psn.game_title.side_effect = RuntimeError("no icon")
        resolver = Mock()
        resolver.resolve.return_value = "https://art.gametdb.com/cover.jpg"
        active = game(icon=None)
        self.assertEqual(resolve_ps3_cover_url(psn, active, resolver=resolver), resolver.resolve.return_value)
        resolver.resolve.assert_called_once_with(active, None)


if __name__ == "__main__":
    unittest.main()
