"""Bootstrap detection for project discovery.

On first turn, scans workspace and injects compact project summary:
runtime + version, package manager, framework, entry point, build/test commands.
Eliminates the initial tool calls small models waste on project discovery.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class ProjectBootstrap:
    runtime: str = ""
    runtime_version: str = ""
    package_manager: str = ""
    framework: str = ""
    entry_point: str = ""
    build_command: str = ""
    test_command: str = ""
    run_command: str = ""

    def to_summary(self, max_chars: int = 200) -> str:
        parts = []
        if self.runtime:
            v = f" {self.runtime_version}" if self.runtime_version else ""
            parts.append(f"Runtime: {self.runtime}{v}")
        if self.package_manager:
            parts.append(f"Package: {self.package_manager}")
        if self.framework:
            parts.append(f"Framework: {self.framework}")
        if self.entry_point:
            parts.append(f"Entry: {self.entry_point}")
        if self.build_command:
            parts.append(f"Build: {self.build_command}")
        if self.test_command:
            parts.append(f"Test: {self.test_command}")
        if self.run_command:
            parts.append(f"Run: {self.run_command}")
        summary = " | ".join(parts)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3] + "..."
        return summary


def detect_bootstrap(work_dir: str = "") -> ProjectBootstrap:
    """Scan workspace and detect project configuration."""
    b = ProjectBootstrap()
    wd = work_dir or os.getcwd()

    _detect_node(wd, b)
    _detect_python(wd, b)
    _detect_rust(wd, b)
    _detect_go(wd, b)
    _detect_java(wd, b)
    _detect_dotnet(wd, b)
    _detect_ruby(wd, b)

    return b


def _detect_node(wd: str, b: ProjectBootstrap) -> None:
    pkgs = [
        f
        for f in ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
        if os.path.exists(os.path.join(wd, f))
    ]
    if not pkgs:
        return
    b.runtime = "Node.js"
    _detect_node_version(wd, b)
    if os.path.exists(os.path.join(wd, "pnpm-lock.yaml")):
        b.package_manager = "pnpm"
    elif os.path.exists(os.path.join(wd, "yarn.lock")):
        b.package_manager = "yarn"
    else:
        b.package_manager = "npm"
    try:
        with open(os.path.join(wd, "package.json")) as f:
            pkg = json.load(f)
    except Exception:
        return
    scripts = pkg.get("scripts", {})
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    b.build_command = scripts.get("build", "")
    b.test_command = scripts.get("test", "")
    b.run_command = scripts.get("start", "") or scripts.get("dev", "")
    if "next" in deps:
        b.framework = "Next.js"
    elif "react" in deps:
        b.framework = "React"
    elif "vue" in deps:
        b.framework = "Vue"
    elif "express" in deps:
        b.framework = "Express"
    elif "fastify" in deps:
        b.framework = "Fastify"
    if pkg.get("main"):
        b.entry_point = pkg["main"]


def _detect_python(wd: str, b: ProjectBootstrap) -> None:
    py_files = [
        f
        for f in ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"]
        if os.path.exists(os.path.join(wd, f))
    ]
    if not py_files:
        return
    b.runtime = "Python"
    _detect_python_version(wd, b)
    b.package_manager = "pip"
    if os.path.exists(os.path.join(wd, "pyproject.toml")):
        b.package_manager = "pip/poetry"

    # Framework detection
    pt_path = os.path.join(wd, "pyproject.toml")
    if os.path.exists(pt_path):
        try:
            with open(pt_path) as f:
                content = f.read().lower()
        except Exception:
            content = ""
        if "fastapi" in content:
            b.framework = "FastAPI"
        elif "django" in content:
            b.framework = "Django"
        elif "flask" in content:
            b.framework = "Flask"
    if not b.framework and os.path.exists(os.path.join(wd, "manage.py")):
        b.framework = "Django"

    if os.path.exists(os.path.join(wd, "pytest.ini")):
        b.test_command = "pytest"
    elif os.path.exists(os.path.join(wd, "manage.py")):
        b.test_command = "python manage.py test"


def _detect_rust(wd: str, b: ProjectBootstrap) -> None:
    if not os.path.exists(os.path.join(wd, "Cargo.toml")):
        return
    b.runtime = "Rust"
    b.package_manager = "cargo"
    b.build_command = "cargo build"
    b.test_command = "cargo test"
    b.run_command = "cargo run"


def _detect_go(wd: str, b: ProjectBootstrap) -> None:
    if not os.path.exists(os.path.join(wd, "go.mod")):
        return
    b.runtime = "Go"
    b.package_manager = "go mod"
    b.build_command = "go build"
    b.test_command = "go test ./..."
    b.run_command = "go run ."


def _detect_java(wd: str, b: ProjectBootstrap) -> None:
    if os.path.exists(os.path.join(wd, "build.gradle")) or os.path.exists(
        os.path.join(wd, "build.gradle.kts")
    ):
        b.runtime = "Java"
        b.package_manager = "gradle"
        b.build_command = "./gradlew build"
        b.test_command = "./gradlew test"
        b.run_command = "./gradlew run"
    elif os.path.exists(os.path.join(wd, "pom.xml")):
        b.runtime = "Java"
        b.package_manager = "maven"
        b.build_command = "mvn compile"
        b.test_command = "mvn test -q"
        b.run_command = "mvn exec:java"


def _detect_dotnet(wd: str, b: ProjectBootstrap) -> None:
    sln_files = [f for f in os.listdir(wd) if f.endswith(".sln")]
    csproj_files = [f for f in os.listdir(wd) if f.endswith(".csproj")]
    if sln_files or csproj_files:
        b.runtime = ".NET"
        b.package_manager = "dotnet"
        b.build_command = "dotnet build"
        b.test_command = "dotnet test"


def _detect_ruby(wd: str, b: ProjectBootstrap) -> None:
    if os.path.exists(os.path.join(wd, "Gemfile")):
        b.runtime = "Ruby"
        b.package_manager = "bundler"
        if os.path.exists(os.path.join(wd, ".rspec")):
            b.test_command = "bundle exec rspec"
        elif os.path.exists(os.path.join(wd, "Rakefile")):
            b.test_command = "rake test"


def _detect_node_version(wd: str, b: ProjectBootstrap) -> None:
    paths = [".nvmrc", ".node-version"]
    for p in paths:
        fp = os.path.join(wd, p)
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    b.runtime_version = f.read().strip()
            except Exception:
                pass
            return


def _detect_python_version(wd: str, b: ProjectBootstrap) -> None:
    paths = [".python-version", ".python_version"]
    for p in paths:
        fp = os.path.join(wd, p)
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    b.runtime_version = f.read().strip()
            except Exception:
                pass
            return
