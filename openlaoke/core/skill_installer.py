"""Skill installer - download and install skills from GitHub repositories.

Supports:
1. GitHub repositories with skills.json index
2. Direct URLs to skill directories
3. OpenCode discovery protocol (index.json)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import httpx


@dataclass
class SkillInfo:
    """Metadata about a skill."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    source: str = ""
    source_url: str = ""
    files: list[str] = field(default_factory=list)
    installed_path: Path | None = None


@dataclass
class InstallResult:
    """Result of a skill installation."""

    skill_name: str
    success: bool
    message: str = ""
    path: Path | None = None


class SkillInstaller:
    """Install skills from GitHub repositories and other sources."""

    def __init__(self, install_dir: Path | None = None):
        self.install_dir = install_dir or Path.home() / ".openlaoke" / "skills"
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = Path.home() / ".openlaoke" / "cache" / "skills"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def close(self):
        await self._client.aclose()

    async def install_from_github(
        self, repo_url: str, skill_name: str | None = None
    ) -> list[InstallResult]:
        """Install skills from a GitHub repository.

        Supports two formats:
        1. Repos with skills.json index (like cycleuser/Skills)
        2. Direct skill directories with SKILL.md
        """
        # Normalize URL
        repo_url = repo_url.rstrip("/")
        if "github.com" in repo_url:
            # Convert web URL to raw content URL
            parts = repo_url.split("github.com/")
            if len(parts) == 2:
                repo_path = parts[1]
                raw_base = f"https://raw.githubusercontent.com/{repo_path}/main"
                api_base = f"https://api.github.com/repos/{repo_path}/contents"
            else:
                return [
                    InstallResult(skill_name or "unknown", False, f"Invalid GitHub URL: {repo_url}")
                ]
        else:
            raw_base = repo_url
            api_base = repo_url

        results = []

        # Try skills.json first
        try:
            skills_index = await self._fetch_json(f"{raw_base}/skills.json")
            if skills_index and "skills" in skills_index:
                results = await self._install_from_index(
                    raw_base, api_base, skills_index, skill_name
                )
        except Exception:
            pass

        # Also scan the skills/ directory directly (some skills may not be in skills.json)
        try:
            dir_results = await self._scan_skills_directory(raw_base, api_base, skill_name)
            # Merge results, avoiding duplicates
            existing_names = {r.skill_name for r in results}
            for r in dir_results:
                if r.skill_name not in existing_names:
                    results.append(r)
                    existing_names.add(r.skill_name)
        except Exception:
            pass

        # If user requested a specific skill but we didn't find it via index or directory scan,
        # try installing it directly (handles API rate limits or skills not yet indexed)
        if skill_name and not results:
            result = await self._install_single_skill(raw_base, api_base, skill_name)
            results.append(result)

        # If we got results, return them
        if results:
            return results

        # Try OpenCode discovery protocol (index.json)
        try:
            return await self._install_from_opencode_index(repo_url, skill_name)
        except Exception:
            pass

        # List all directories and try each as a skill
        try:
            contents = await self._fetch_json(api_base)
            if isinstance(contents, list):
                dirs = [item["name"] for item in contents if item.get("type") == "dir"]
                for d in dirs:
                    if not d.startswith("."):
                        result = await self._install_single_skill(raw_base, api_base, d)
                        results.append(result)
        except Exception as e:
            results.append(InstallResult("unknown", False, f"Failed to list repo: {e}"))

        return results

    async def _install_from_index(
        self, raw_base: str, api_base: str, index: dict, skill_name: str | None
    ) -> list[InstallResult]:
        """Install skills from a skills.json index."""
        results = []
        skills = index.get("skills", [])

        for skill in skills:
            name = skill.get("name", "")
            if skill_name and name != skill_name:
                continue

            result = await self._install_single_skill(raw_base, api_base, name)
            results.append(result)

        return results

    async def _scan_skills_directory(
        self, raw_base: str, api_base: str, skill_name: str | None
    ) -> list[InstallResult]:
        """Scan the skills/ directory in a GitHub repo and install all skills found."""
        results = []

        # Try skills/ subdirectory
        skills_dir_url = f"{api_base}/skills"
        contents = await self._fetch_json(skills_dir_url)

        if not isinstance(contents, list):
            # API rate limited or directory doesn't exist
            # If specific skill requested, the caller will handle it via _install_single_skill
            return results

        skill_dirs = [item["name"] for item in contents if item.get("type") == "dir"]

        for name in skill_dirs:
            if skill_name and name != skill_name:
                continue

            result = await self._install_single_skill(raw_base, api_base, name)
            results.append(result)

        return results

    async def _install_from_opencode_index(
        self, url: str, skill_name: str | None
    ) -> list[InstallResult]:
        """Install skills using OpenCode discovery protocol (index.json)."""
        base = url.rstrip("/") + "/"
        index_url = f"{base}index.json"

        index_data = await self._fetch_json(index_url)
        if not index_data or "skills" not in index_data:
            return []

        results = []
        host = base.rstrip("/")

        for skill in index_data["skills"]:
            name = skill.get("name", "")
            files = skill.get("files", [])

            if not files or "SKILL.md" not in files:
                continue

            if skill_name and name != skill_name:
                continue

            result = await self._download_skill_files(host, name, files)
            results.append(result)

        return results

    async def _install_single_skill(self, raw_base: str, api_base: str, name: str) -> InstallResult:
        """Install a single skill from a GitHub repo."""
        # Check if already installed
        skill_dir = self.install_dir / name
        if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
            return InstallResult(name, True, f"Already installed at {skill_dir}", skill_dir)

        try:
            # Check if SKILL.md exists
            skill_url = f"{raw_base}/skills/{name}/SKILL.md"
            resp = await self._client.head(skill_url)
            if resp.status_code != 200:
                # Try without skills/ prefix
                skill_url = f"{raw_base}/{name}/SKILL.md"
                resp = await self._client.head(skill_url)
                if resp.status_code != 200:
                    return InstallResult(name, False, "SKILL.md not found")

            # Get all files in the skill directory
            dir_url = f"{api_base}/skills/{name}"
            contents = await self._fetch_json(dir_url)
            if not isinstance(contents, list):
                # Fallback: try without skills/ prefix
                dir_url = f"{api_base}/{name}"
                contents = await self._fetch_json(dir_url)

            files = []
            if isinstance(contents, list):
                files = [item["name"] for item in contents if item.get("type") == "file"]

            # If API listing fails or returns no files, use known defaults
            if not files:
                files = ["SKILL.md"]

            if "SKILL.md" not in files:
                return InstallResult(name, False, "SKILL.md not in skill directory")

            # Create skill directory
            skill_dir = self.install_dir / name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Download each file
            for fname in files:
                file_url = f"{raw_base}/skills/{name}/{fname}"
                resp = await self._client.get(file_url)
                if resp.status_code == 200:
                    (skill_dir / fname).write_text(resp.text, encoding="utf-8")
                else:
                    # Try without skills/ prefix
                    file_url = f"{raw_base}/{name}/{fname}"
                    resp = await self._client.get(file_url)
                    if resp.status_code == 200:
                        (skill_dir / fname).write_text(resp.text, encoding="utf-8")

            return InstallResult(name, True, f"Installed to {skill_dir}", skill_dir)

        except Exception as e:
            return InstallResult(name, False, str(e))

    async def _download_skill_files(self, host: str, name: str, files: list[str]) -> InstallResult:
        """Download skill files from OpenCode-style index."""
        try:
            skill_dir = self.install_dir / name
            skill_dir.mkdir(parents=True, exist_ok=True)

            for fname in files:
                file_url = f"{host}/{name}/{fname}"
                resp = await self._client.get(file_url)
                if resp.status_code == 200:
                    (skill_dir / fname).write_text(resp.text, encoding="utf-8")

            if (skill_dir / "SKILL.md").exists():
                return InstallResult(name, True, f"Installed to {skill_dir}", skill_dir)
            else:
                shutil.rmtree(skill_dir, ignore_errors=True)
                return InstallResult(name, False, "SKILL.md not found after download")

        except Exception as e:
            return InstallResult(name, False, str(e))

    async def _fetch_json(self, url: str) -> dict | list | None:
        """Fetch and parse JSON from URL."""
        resp = await self._client.get(url)
        if resp.status_code == 200:
            return resp.json()
        return None

    def list_installed(self) -> list[SkillInfo]:
        """List all installed skills."""
        skills = []
        if not self.install_dir.exists():
            return skills

        for skill_dir in sorted(self.install_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            content = skill_file.read_text(encoding="utf-8")
            name = skill_dir.name
            description = ""

            # Parse frontmatter for description
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml

                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter:
                            description = frontmatter.get("description", "")
                            name = frontmatter.get("name", name)
                    except Exception:
                        pass

            files = [f.name for f in skill_dir.iterdir() if f.is_file()]

            skills.append(
                SkillInfo(
                    name=name,
                    description=description,
                    installed_path=skill_dir,
                    files=files,
                )
            )

        return skills

    def remove_skill(self, name: str) -> InstallResult:
        """Remove an installed skill."""
        skill_dir = self.install_dir / name
        if not skill_dir.exists():
            return InstallResult(name, False, f"Skill '{name}' not found")

        shutil.rmtree(skill_dir)
        return InstallResult(name, True, f"Removed '{name}'")

    def get_skill_path(self, name: str) -> Path | None:
        """Get the path to an installed skill."""
        skill_dir = self.install_dir / name
        if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
            return skill_dir
        return None
