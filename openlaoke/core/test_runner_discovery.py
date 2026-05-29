"""Test runner auto-discovery.

Detects project test command from config files and injects into system prompt.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class TestRunnerInfo:
    command: str = ""
    framework: str = ""
    confidence: float = 0.0


def detect_test_runner(work_dir: str = "") -> TestRunnerInfo:
    wd = work_dir or os.getcwd()

    runners: list[TestRunnerInfo] = []

    r = _detect_node_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_python_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_rust_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_go_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_java_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_ruby_tests(wd)
    if r.command:
        runners.append(r)

    r = _detect_dotnet_tests(wd)
    if r.command:
        runners.append(r)

    if runners:
        return max(runners, key=lambda r: r.confidence)
    return TestRunnerInfo()


def _detect_node_tests(wd: str) -> TestRunnerInfo:
    pkg_path = os.path.join(wd, "package.json")
    if not os.path.exists(pkg_path):
        return TestRunnerInfo()
    try:
        with open(pkg_path) as f:
            pkg = json.load(f)
    except Exception:
        return TestRunnerInfo()
    scripts = pkg.get("scripts", {})
    deps = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
    }

    if "test" in scripts:
        cmd = scripts["test"]
        framework = "npm test"
        if "vitest" in str(deps) or "vitest" in cmd:
            if "--run" not in cmd:
                cmd = cmd.replace("vitest", "vitest --run")
            framework = "vitest"
        elif "jest" in str(deps) or "jest" in cmd:
            if "--watch" in cmd:
                cmd = cmd.replace("--watch", "")
            framework = "jest"
        elif "mocha" in str(deps):
            framework = "mocha"
        return TestRunnerInfo(command=cmd, framework=framework, confidence=0.95)

    if "vitest" in deps:
        return TestRunnerInfo(command="npx vitest --run", framework="vitest", confidence=0.7)
    if "jest" in deps:
        return TestRunnerInfo(command="npx jest", framework="jest", confidence=0.7)
    if "mocha" in deps:
        return TestRunnerInfo(command="npx mocha", framework="mocha", confidence=0.7)

    if os.path.exists(os.path.join(wd, "vitest.config.ts")):
        return TestRunnerInfo(command="npx vitest --run", framework="vitest", confidence=0.5)
    if os.path.exists(os.path.join(wd, "jest.config.js")):
        return TestRunnerInfo(command="npx jest", framework="jest", confidence=0.5)

    return TestRunnerInfo()


def _detect_python_tests(wd: str) -> TestRunnerInfo:
    if os.path.exists(os.path.join(wd, "pytest.ini")) or os.path.exists(
        os.path.join(wd, "pyproject.toml")
    ):
        try:
            import tomllib

            with open(os.path.join(wd, "pyproject.toml"), "rb") as f:
                data = tomllib.load(f)
            if "tool" in data and "pytest" in data["tool"]:
                return TestRunnerInfo(command="pytest", framework="pytest", confidence=0.9)
        except Exception:
            pass
        return TestRunnerInfo(command="pytest", framework="pytest", confidence=0.9)

    if os.path.exists(os.path.join(wd, "manage.py")):
        return TestRunnerInfo(
            command="python manage.py test", framework="Django test", confidence=0.8
        )

    if os.path.exists(os.path.join(wd, "setup.cfg")):
        try:
            import configparser

            config = configparser.ConfigParser()
            config.read(os.path.join(wd, "setup.cfg"))
            if "tool:pytest" in config:
                return TestRunnerInfo(command="pytest", framework="pytest", confidence=0.85)
        except Exception:
            pass

    py_files = [f for f in os.listdir(wd) if f.startswith("test_") or f.endswith("_test.py")]
    if py_files:
        return TestRunnerInfo(command="python -m pytest", framework="pytest", confidence=0.5)

    return TestRunnerInfo()


def _detect_rust_tests(wd: str) -> TestRunnerInfo:
    if os.path.exists(os.path.join(wd, "Cargo.toml")):
        return TestRunnerInfo(command="cargo test", framework="cargo test", confidence=0.95)
    return TestRunnerInfo()


def _detect_go_tests(wd: str) -> TestRunnerInfo:
    if os.path.exists(os.path.join(wd, "go.mod")):
        return TestRunnerInfo(command="go test ./...", framework="go test", confidence=0.95)
    return TestRunnerInfo()


def _detect_java_tests(wd: str) -> TestRunnerInfo:
    if os.path.exists(os.path.join(wd, "build.gradle")) or os.path.exists(
        os.path.join(wd, "build.gradle.kts")
    ):
        return TestRunnerInfo(command="./gradlew test", framework="gradle test", confidence=0.9)
    if os.path.exists(os.path.join(wd, "pom.xml")):
        return TestRunnerInfo(command="mvn test -q", framework="maven test", confidence=0.9)
    return TestRunnerInfo()


def _detect_ruby_tests(wd: str) -> TestRunnerInfo:
    if os.path.exists(os.path.join(wd, "Gemfile")):
        if os.path.exists(os.path.join(wd, ".rspec")):
            return TestRunnerInfo(command="bundle exec rspec", framework="RSpec", confidence=0.9)
        if os.path.exists(os.path.join(wd, "Rakefile")):
            return TestRunnerInfo(command="rake test", framework="Minitest", confidence=0.8)
        return TestRunnerInfo(command="rspec", framework="RSpec", confidence=0.6)
    return TestRunnerInfo()


def _detect_dotnet_tests(wd: str) -> TestRunnerInfo:
    sln = [f for f in os.listdir(wd) if f.endswith(".sln")]
    csproj = [f for f in os.listdir(wd) if f.endswith(".csproj")]
    if sln or csproj:
        return TestRunnerInfo(command="dotnet test", framework="dotnet test", confidence=0.9)
    return TestRunnerInfo()
