"""Tests for SkillInstaller, which downloads skills from GitHub.

Every HTTP call goes through an ``httpx.MockTransport`` route table, so the tests
exercise the real request/parse/write path without a network. Files land in a
temporary install directory and are read back.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from openlaoke.core.skill_installer import SkillInstaller, safe_skill_name

RAW = "https://raw.githubusercontent.com/cycleuser/Skills/main"
API = "https://api.github.com/repos/cycleuser/Skills/contents"
REPO = "https://github.com/cycleuser/Skills"


class Server:
    """A path-to-response table used as an httpx transport handler."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        key = str(request.url)
        self.requests.append((request.method, key))
        value = self.routes.get(key)
        if value is None:
            return httpx.Response(404, text="not found")
        if isinstance(value, tuple):
            status, body = value
            return httpx.Response(status, text=body)
        return httpx.Response(200, json=value)

    def paths(self) -> list[str]:
        return [url for _method, url in self.requests]


def make(tmp_path: Path, routes: dict[str, object]) -> tuple[SkillInstaller, Server]:
    installer = SkillInstaller(install_dir=tmp_path / "skills")
    server = Server(routes)
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(server.handler))
    return installer, server


def run_install(installer: SkillInstaller, *args, **kwargs):
    async def go():
        try:
            return await installer.install_from_github(*args, **kwargs)
        finally:
            await installer.close()

    return asyncio.run(go())


SKILL_MD = "---\nname: pdf\ndescription: Read PDFs\n---\n\nDo the thing.\n"


def repo_routes(*, index: dict | None = None, skills: list[str] | None = None) -> dict:
    """Build a route table for a repository that contains the given skills."""
    routes: dict[str, object] = {}
    if index is not None:
        routes[f"{RAW}/skills.json"] = index
    if skills is not None:
        routes[f"{API}/skills"] = [
            {"name": name, "type": "dir", "path": f"skills/{name}"} for name in skills
        ]
    for name in skills or []:
        routes[f"{RAW}/skills/{name}/SKILL.md"] = (200, SKILL_MD)
        routes[f"{RAW}/skills/{name}/helper.py"] = (200, "print('hi')\n")
        routes[f"{API}/skills/{name}"] = [
            {"name": "SKILL.md", "type": "file"},
            {"name": "helper.py", "type": "file"},
        ]
    return routes


# --------------------------------------------------------------------------- #
# Name validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ["pdf", "pdf-tools", "a", "skill_1", "日本語"])
def test_safe_names(name: str) -> None:
    assert safe_skill_name(name) is True


@pytest.mark.parametrize("name", ["", ".", "..", "../evil", "a/b", "a\\b", "C:evil", "nul\x00byte"])
def test_unsafe_names(name: str) -> None:
    assert safe_skill_name(name) is False


# --------------------------------------------------------------------------- #
# GitHub installation
# --------------------------------------------------------------------------- #


def test_index_install_writes_every_listed_file(tmp_path) -> None:
    installer, server = make(
        tmp_path,
        repo_routes(index={"skills": [{"name": "pdf"}]}, skills=["pdf"]),
    )

    results = run_install(installer, REPO)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].skill_name == "pdf"
    target = tmp_path / "skills" / "pdf"
    assert (target / "SKILL.md").read_text(encoding="utf-8") == SKILL_MD
    assert (target / "helper.py").exists()
    # The index and the directory scan must not install the same skill twice.
    downloads = [
        url for method, url in server.requests if method == "GET" and url.endswith("/pdf/SKILL.md")
    ]
    assert len(downloads) == 1


def test_directory_scan_installs_every_skill(tmp_path) -> None:
    installer, _server = make(tmp_path, repo_routes(skills=["pdf", "docx"]))

    results = run_install(installer, REPO)

    assert {r.skill_name for r in results} == {"pdf", "docx"}
    assert all(r.success for r in results)
    assert (tmp_path / "skills" / "docx" / "SKILL.md").exists()


def test_a_named_skill_limits_the_index(tmp_path) -> None:
    installer, _server = make(
        tmp_path,
        repo_routes(index={"skills": [{"name": "pdf"}, {"name": "docx"}]}, skills=["pdf", "docx"]),
    )

    results = run_install(installer, REPO, "docx")

    assert [r.skill_name for r in results] == ["docx"]
    assert not (tmp_path / "skills" / "pdf").exists()


def test_an_unindexed_skill_is_tried_directly(tmp_path) -> None:
    installer, _server = make(tmp_path, repo_routes(skills=["solo"]))

    results = run_install(installer, REPO, "solo")

    assert results[0].success is True
    assert (tmp_path / "skills" / "solo" / "SKILL.md").exists()


def test_missing_everywhere_reports_a_failure_instead_of_none(tmp_path) -> None:
    """``install_from_github`` fell off the end and returned None before this."""
    installer, _server = make(tmp_path, {})

    results = run_install(installer, REPO)

    assert results is not None
    assert len(results) == 1
    assert results[0].success is False
    assert "No skill found" in results[0].message


def test_the_repository_root_is_scanned_as_a_last_resort(tmp_path) -> None:
    routes = {
        f"{API}": [{"name": "rooty", "type": "dir"}],
        f"{RAW}/rooty/SKILL.md": (200, SKILL_MD),
        f"{API}/rooty": [{"name": "SKILL.md", "type": "file"}],
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, REPO)

    assert results[0].skill_name == "rooty"
    assert results[0].success is True


def test_a_skill_without_skill_md_is_rejected(tmp_path) -> None:
    installer, _server = make(
        tmp_path,
        {
            f"{API}/skills": [{"name": "broken", "type": "dir"}],
            f"{RAW}/skills/broken/SKILL.md": (404, "nope"),
            f"{RAW}/broken/SKILL.md": (404, "nope"),
        },
    )

    results = run_install(installer, REPO)

    assert results[0].success is False
    assert "SKILL.md not found" in results[0].message


def test_files_are_fetched_without_the_skills_prefix_when_needed(tmp_path) -> None:
    routes = {
        f"{API}/skills": [{"name": "flat", "type": "dir"}],
        f"{RAW}/flat/SKILL.md": (200, SKILL_MD),
        f"{API}/flat": [{"name": "SKILL.md", "type": "file"}],
    }
    installer, server = make(tmp_path, routes)

    results = run_install(installer, REPO)

    assert results[0].success is True
    assert (tmp_path / "skills" / "flat" / "SKILL.md").exists()
    assert f"{RAW}/flat/SKILL.md" in server.paths()


def test_an_already_installed_skill_is_left_alone(tmp_path) -> None:
    target = tmp_path / "skills" / "pdf"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("old", encoding="utf-8")
    installer, server = make(tmp_path, repo_routes(index={"skills": [{"name": "pdf"}]}))

    results = run_install(installer, REPO)

    assert results[0].success is True
    assert "Already installed" in results[0].message
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "old"
    assert not [url for url in server.paths() if "/pdf/" in url]  # nothing was downloaded


def test_a_directory_name_from_the_index_is_validated(tmp_path) -> None:
    """A repository controls these names; one must not escape the skills dir."""
    routes = {
        f"{API}/skills": [{"name": "../escape", "type": "dir"}],
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, REPO)

    assert results[0].success is False
    assert "Unsafe skill name" in results[0].message
    assert not (tmp_path / "escape").exists()


def test_the_api_failure_message_is_reported(tmp_path) -> None:
    class Boom(Server):
        def handler(self, request: httpx.Request) -> httpx.Response:
            if "contents" in str(request.url):
                raise httpx.ConnectError("no network")
            return httpx.Response(404)

    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(Boom({}).handler))

    results = run_install(installer, REPO)

    assert results[0].success is False


# --------------------------------------------------------------------------- #
# OpenCode-style index
# --------------------------------------------------------------------------- #


def test_opencode_index_installs_files(tmp_path) -> None:
    base = "https://skills.example.com/pack"
    routes = {
        f"{base}/index.json": {"skills": [{"name": "ocr", "files": ["SKILL.md", "run.py"]}]},
        f"{base}/ocr/SKILL.md": (200, SKILL_MD),
        f"{base}/ocr/run.py": (200, "print(1)\n"),
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, base)

    assert results[0].success is True
    assert (tmp_path / "skills" / "ocr" / "run.py").exists()


def test_opencode_index_without_skill_md_rolls_back(tmp_path) -> None:
    base = "https://skills.example.com/pack"
    routes = {
        # SKILL.md is advertised but not actually served.
        f"{base}/index.json": {"skills": [{"name": "ocr", "files": ["SKILL.md"]}]},
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, base)

    assert results[0].success is False
    assert "SKILL.md not found after download" in results[0].message
    assert not (tmp_path / "skills" / "ocr").exists()


def test_opencode_entries_without_skill_md_are_skipped(tmp_path) -> None:
    base = "https://skills.example.com/pack"
    routes = {
        f"{base}/index.json": {"skills": [{"name": "no-files", "files": []}]},
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, base)

    assert results[0].success is False  # nothing found at all


def test_opencode_index_with_unsafe_name_is_rejected(tmp_path) -> None:
    base = "https://skills.example.com/pack"
    routes = {
        f"{base}/index.json": {"skills": [{"name": "../nope", "files": ["SKILL.md"]}]},
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, base)

    assert results[0].success is False
    assert "Unsafe skill name" in results[0].message


# --------------------------------------------------------------------------- #
# Local management
# --------------------------------------------------------------------------- #


def test_list_installed_reads_frontmatter(tmp_path) -> None:
    skills = tmp_path / "skills"
    (skills / "pdf").mkdir(parents=True)
    (skills / "pdf" / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (skills / "pdf" / "extra.md").write_text("x", encoding="utf-8")
    (skills / "no-manifest").mkdir()
    (skills / "loose-file.md").write_text("x", encoding="utf-8")
    (skills / "bad-yaml").mkdir()
    (skills / "bad-yaml" / "SKILL.md").write_text("---\nname: [unclosed\n---\n", encoding="utf-8")

    installer = SkillInstaller(install_dir=skills)
    asyncio.run(installer.close())
    listed = {info.name: info for info in installer.list_installed()}

    assert set(listed) == {"pdf", "bad-yaml"}
    assert listed["pdf"].description == "Read PDFs"
    assert sorted(listed["pdf"].files) == ["SKILL.md", "extra.md"]
    assert listed["pdf"].installed_path == skills / "pdf"


def test_list_installed_without_a_directory(tmp_path) -> None:
    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer.close())
    installer.install_dir.rmdir()

    assert installer.list_installed() == []


def test_remove_skill(tmp_path) -> None:
    skills = tmp_path / "skills"
    (skills / "gone").mkdir(parents=True)
    (skills / "gone" / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    installer = SkillInstaller(install_dir=skills)
    asyncio.run(installer.close())

    result = installer.remove_skill("gone")

    assert result.success is True
    assert not (skills / "gone").exists()


def test_remove_missing_or_unsafe_skill(tmp_path) -> None:
    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer.close())

    missing = installer.remove_skill("absent")
    unsafe = installer.remove_skill("../etc")

    assert missing.success is False
    assert "not found" in missing.message
    assert unsafe.success is False
    assert "Unsafe" in unsafe.message


def test_get_skill_path(tmp_path) -> None:
    skills = tmp_path / "skills"
    (skills / "pdf").mkdir(parents=True)
    (skills / "pdf" / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (skills / "empty").mkdir()
    installer = SkillInstaller(install_dir=skills)
    asyncio.run(installer.close())

    assert installer.get_skill_path("pdf") == skills / "pdf"
    assert installer.get_skill_path("empty") is None
    assert installer.get_skill_path("missing") is None
    assert installer.get_skill_path("../pdf") is None


def test_json_fetch_tolerates_non_200(tmp_path) -> None:
    installer, _server = make(tmp_path, {f"{RAW}/skills.json": (500, "boom")})

    async def go():
        try:
            return await installer._fetch_json(f"{RAW}/skills.json")
        finally:
            await installer.close()

    assert asyncio.run(go()) is None


def test_the_index_must_be_a_mapping_with_skills(tmp_path) -> None:
    installer, _server = make(tmp_path, {f"{RAW}/skills.json": ["not", "a", "mapping"]})

    results = run_install(installer, REPO)

    assert results[0].success is False


def test_json_round_trip_for_the_default_install_dir(tmp_path, monkeypatch) -> None:
    """The default install dir follows $HOME, the same place the registry reads."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    installer = SkillInstaller()
    asyncio.run(installer.close())

    assert installer.install_dir == home / ".openlaoke" / "skills"
    assert installer.install_dir.is_dir()
    assert json.dumps({"ok": True})  # keep the import meaningful on all platforms


# --------------------------------------------------------------------------- #
# Remaining paths: bad URLs, transport failures, odd listings
# --------------------------------------------------------------------------- #


def test_a_github_url_that_does_not_split_into_two_parts_is_rejected(tmp_path) -> None:
    installer, _server = make(tmp_path, {})

    results = run_install(installer, "https://github.com/a/github.com/b")

    assert results[0].success is False
    assert "Invalid GitHub URL" in results[0].message


def test_a_named_skill_is_tried_directly_when_the_listing_is_empty(tmp_path) -> None:
    """No skills.json, no /skills listing: the requested name is still attempted."""
    routes = {
        f"{RAW}/solo/SKILL.md": (200, SKILL_MD),
        f"{API}/solo": [{"name": "SKILL.md", "type": "file"}],
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, REPO, "solo")

    assert results[0].success is True
    assert (tmp_path / "skills" / "solo" / "SKILL.md").exists()


def test_a_listing_without_a_file_type_defaults_to_skill_md(tmp_path) -> None:
    routes = {
        f"{API}/skills": [{"name": "bare", "type": "dir"}],
        f"{RAW}/skills/bare/SKILL.md": (200, SKILL_MD),
        f"{API}/skills/bare": [],  # empty listing -> assume SKILL.md
        f"{RAW}/bare/SKILL.md": (200, SKILL_MD),
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, REPO)

    assert results[0].success is True


def test_a_directory_listing_without_skill_md_is_rejected(tmp_path) -> None:
    routes = {
        f"{API}/skills": [{"name": "odd", "type": "dir"}],
        f"{RAW}/skills/odd/SKILL.md": (200, SKILL_MD),
        f"{API}/skills/odd": [{"name": "notes.txt", "type": "file"}],
    }
    installer, _server = make(tmp_path, routes)

    results = run_install(installer, REPO)

    assert results[0].success is False
    assert "SKILL.md not in skill directory" in results[0].message


def test_a_scan_failure_does_not_break_the_install(tmp_path) -> None:
    class Flaky(Server):
        def handler(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/contents/skills"):
                raise httpx.ConnectError("listing unavailable")
            if url.endswith("/skills/solo/SKILL.md"):
                return httpx.Response(200, text=SKILL_MD)
            if url.endswith("/contents/solo"):
                return httpx.Response(200, json=[{"name": "SKILL.md", "type": "file"}])
            return httpx.Response(404)

    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(Flaky({}).handler))

    results = run_install(installer, REPO, "solo")

    assert results[0].success is True


def test_an_opencode_index_failure_is_tolerated(tmp_path) -> None:
    base = "https://skills.example.com/pack"

    class Flaky(Server):
        def handler(self, request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("index.json"):
                raise httpx.ConnectError("index unavailable")
            return httpx.Response(404)

    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(Flaky({}).handler))

    results = run_install(installer, base)

    assert results[0].success is False
    assert "No skill found" in results[0].message


def test_a_failed_file_write_is_reported(tmp_path) -> None:
    class Broken(Server):
        def handler(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/contents/skills"):
                return httpx.Response(200, json=[{"name": "pdf", "type": "dir"}])
            if request.method == "HEAD":
                return httpx.Response(200)
            if url.endswith("/contents/skills/pdf"):
                raise httpx.ReadTimeout("gave up")
            return httpx.Response(200, text=SKILL_MD)

    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(Broken({}).handler))

    results = run_install(installer, REPO)

    assert results[0].success is False
    assert "gave up" in results[0].message


def test_opencode_skips_unsafe_file_names(tmp_path) -> None:
    base = "https://skills.example.com/pack"
    routes = {
        f"{base}/index.json": {"skills": [{"name": "ocr", "files": ["SKILL.md", "../escape.py"]}]},
        f"{base}/ocr/SKILL.md": (200, SKILL_MD),
    }
    installer, server = make(tmp_path, routes)

    results = run_install(installer, base)

    assert results[0].success is True
    assert not (tmp_path / "escape.py").exists()
    assert not [url for url in server.paths() if "escape" in url]


def test_a_download_failure_is_reported(tmp_path) -> None:
    base = "https://skills.example.com/pack"

    class Broken(Server):
        def handler(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("index.json"):
                return httpx.Response(
                    200, json={"skills": [{"name": "ocr", "files": ["SKILL.md"]}]}
                )
            raise httpx.ConnectError("dropped")

    installer = SkillInstaller(install_dir=tmp_path / "skills")
    asyncio.run(installer._client.aclose())
    installer._client = httpx.AsyncClient(transport=httpx.MockTransport(Broken({}).handler))

    results = run_install(installer, base)

    assert results[0].success is False
    assert "dropped" in results[0].message


def test_a_named_skill_never_consults_the_opencode_index(tmp_path) -> None:
    """A named skill is fetched directly, so a repository index is irrelevant."""
    base = "https://skills.example.com/pack"
    routes = {
        f"{base}/index.json": {
            "skills": [
                {"name": "first", "files": ["SKILL.md"]},
                {"name": "second", "files": ["SKILL.md"]},
            ]
        },
        f"{base}/second/SKILL.md": (200, SKILL_MD),
    }
    installer, server = make(tmp_path, routes)

    results = run_install(installer, base, "second")

    assert [r.skill_name for r in results] == ["second"]
    assert not (tmp_path / "skills" / "first").exists()
    assert not [url for url in server.paths() if url.endswith("index.json")]
