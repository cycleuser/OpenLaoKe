"""Project initializer - automatic project detection and initialization."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ProjectType(StrEnum):
    """Supported project types."""

    PYTHON = "python"
    NODE_JS = "nodejs"
    GO = "go"
    RUST = "rust"
    JAVA_MAVEN = "java_maven"
    JAVA_GRADLE = "java_gradle"
    GENERIC = "generic"


@dataclass
class ProjectAnalysis:
    """Analysis result of a project."""

    project_type: ProjectType
    path: Path
    has_git: bool = False
    has_readme: bool = False
    has_agents_md: bool = False
    has_tests: bool = False
    has_ci: bool = False
    existing_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    suggested_structure: dict[str, Any] = field(default_factory=dict)


@dataclass
class InitResult:
    """Result of project initialization."""

    success: bool
    project_type: ProjectType
    path: Path
    files_created: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


class ProjectInitializer:
    """Automatic project detection and initialization system."""

    PROJECT_FILES: dict[ProjectType, list[str]] = {
        ProjectType.PYTHON: ["pyproject.toml", "setup.py", "requirements.txt", "setup.cfg"],
        ProjectType.NODE_JS: ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        ProjectType.GO: ["go.mod", "go.sum"],
        ProjectType.RUST: ["Cargo.toml", "Cargo.lock"],
        ProjectType.JAVA_MAVEN: ["pom.xml"],
        ProjectType.JAVA_GRADLE: [
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        ],
        ProjectType.GENERIC: [],
    }

    REQUIRED_FILES: dict[ProjectType, list[str]] = {
        ProjectType.PYTHON: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.NODE_JS: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.GO: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.RUST: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.JAVA_MAVEN: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.JAVA_GRADLE: ["README.md", ".gitignore", "AGENTS.md"],
        ProjectType.GENERIC: ["README.md", ".gitignore", "AGENTS.md"],
    }

    def detect_project_type(self, path: Path) -> ProjectType | None:
        """Detect the type of project at the given path."""
        if not path.exists() or not path.is_dir():
            return None

        files = set(os.listdir(path))

        for project_type, project_files in self.PROJECT_FILES.items():
            if project_type == ProjectType.GENERIC:
                continue
            for project_file in project_files:
                if project_file in files:
                    if project_type in (ProjectType.JAVA_MAVEN, ProjectType.JAVA_GRADLE):
                        if "pom.xml" in files:
                            return ProjectType.JAVA_MAVEN
                        if any(f in files for f in ["build.gradle", "build.gradle.kts"]):
                            return ProjectType.JAVA_GRADLE
                    return project_type

        return ProjectType.GENERIC

    def analyze_project(self, path: Path) -> ProjectAnalysis:
        """Analyze an existing project structure."""
        project_type = self.detect_project_type(path) or ProjectType.GENERIC

        files = set(os.listdir(path)) if path.exists() else set()

        has_git = ".git" in files or (path / ".git").is_dir()
        has_readme = "README.md" in files or "README.rst" in files or "README.txt" in files
        has_agents_md = "AGENTS.md" in files
        has_tests = self._check_test_directory(path, files)
        has_ci = ".github" in files or ".gitlab-ci.yml" in files or "Jenkinsfile" in files

        existing_files = [f for f in files if (path / f).is_file()]
        required = self.REQUIRED_FILES.get(project_type, [])
        missing_files = [f for f in required if f not in files]

        dependencies = self._detect_dependencies(path, project_type)

        suggested_structure = self._suggest_structure(project_type, has_tests, has_ci)

        return ProjectAnalysis(
            project_type=project_type,
            path=path,
            has_git=has_git,
            has_readme=has_readme,
            has_agents_md=has_agents_md,
            has_tests=has_tests,
            has_ci=has_ci,
            existing_files=existing_files,
            missing_files=missing_files,
            dependencies=dependencies,
            suggested_structure=suggested_structure,
        )

    def _check_test_directory(self, path: Path, files: set[str]) -> bool:
        """Check if project has test directories."""
        test_dirs = {"tests", "test", "__tests__", "spec", "specs"}
        test_files = {
            "*_test.py",
            "test_*.py",
            "*.test.js",
            "*.spec.js",
            "*_test.go",
            "*_test.rs",
        }

        for test_dir in test_dirs:
            if test_dir in files and (path / test_dir).is_dir():
                return True

        for file_pattern in test_files:
            prefix, suffix = file_pattern.split("*")
            for f in files:
                if f.startswith(prefix.lstrip("*")) and f.endswith(suffix.rstrip("*")):
                    return True

        return False

    def _detect_dependencies(self, path: Path, project_type: ProjectType) -> list[str]:
        """Detect project dependencies."""
        dependencies = []

        if project_type == ProjectType.PYTHON:
            deps_files = ["requirements.txt", "pyproject.toml", "setup.py"]
            for deps_file in deps_files:
                deps_path = path / deps_file
                if deps_path.exists():
                    dependencies.extend(self._parse_python_deps(deps_path))

        elif project_type == ProjectType.NODE_JS:
            package_json = path / "package.json"
            if package_json.exists():
                dependencies.extend(self._parse_node_deps(package_json))

        return dependencies

    def _parse_python_deps(self, deps_path: Path) -> list[str]:
        """Parse Python dependencies from file."""
        deps = []
        try:
            content = deps_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(
                        line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                    )
        except Exception:
            pass
        return deps

    def _parse_node_deps(self, package_json: Path) -> list[str]:
        """Parse Node.js dependencies from package.json."""
        deps = []
        try:
            import json

            data = json.loads(package_json.read_text(encoding="utf-8"))
            deps.extend(data.get("dependencies", {}).keys())
            deps.extend(data.get("devDependencies", {}).keys())
        except Exception:
            pass
        return deps

    def _suggest_structure(
        self, project_type: ProjectType, has_tests: bool, has_ci: bool
    ) -> dict[str, Any]:
        """Suggest project structure improvements."""
        structure: dict[str, Any] = {
            "directories": [],
            "files": [],
            "config": [],
        }

        if not has_tests:
            if project_type == ProjectType.PYTHON:
                structure["directories"].append("tests/")
                structure["files"].append("tests/__init__.py")
            elif project_type == ProjectType.NODE_JS:
                structure["directories"].append("__tests__/")
            elif project_type == ProjectType.GO:
                structure["files"].append("*_test.go")
            elif project_type == ProjectType.RUST:
                pass

        if not has_ci:
            structure["directories"].append(".github/workflows/")

        return structure

    def get_required_files(self, project_type: ProjectType) -> list[str]:
        """Get list of required files for a project type."""
        return self.REQUIRED_FILES.get(project_type, [])

    def create_project_structure(self, path: Path, project_type: ProjectType) -> bool:
        """Create basic project structure."""
        try:
            path.mkdir(parents=True, exist_ok=True)

            if project_type == ProjectType.PYTHON:
                self._create_python_structure(path)
            elif project_type == ProjectType.NODE_JS:
                self._create_node_structure(path)
            elif project_type == ProjectType.GO:
                self._create_go_structure(path)
            elif project_type == ProjectType.RUST:
                self._create_rust_structure(path)
            elif project_type in (ProjectType.JAVA_MAVEN, ProjectType.JAVA_GRADLE):
                self._create_java_structure(path, project_type)
            else:
                self._create_generic_structure(path)

            return True
        except Exception:
            return False

    def _create_python_structure(self, path: Path) -> None:
        """Create Python project structure."""
        dirs = ["src", "tests", "docs"]
        for d in dirs:
            (path / d).mkdir(exist_ok=True)
        (path / "tests" / "__init__.py").touch()

    def _create_node_structure(self, path: Path) -> None:
        """Create Node.js project structure."""
        dirs = ["src", "tests", "lib"]
        for d in dirs:
            (path / d).mkdir(exist_ok=True)

    def _create_go_structure(self, path: Path) -> None:
        """Create Go project structure."""
        dirs = ["cmd", "pkg", "internal"]
        for d in dirs:
            (path / d).mkdir(exist_ok=True)

    def _create_rust_structure(self, path: Path) -> None:
        """Create Rust project structure."""
        dirs = ["src"]
        for d in dirs:
            (path / d).mkdir(exist_ok=True)

    def _create_java_structure(self, path: Path, project_type: ProjectType) -> None:
        """Create Java project structure."""
        if project_type == ProjectType.JAVA_MAVEN:
            dirs = ["src/main/java", "src/main/resources", "src/test/java"]
        else:
            dirs = ["src/main/java", "src/main/resources", "src/test/java"]
        for d in dirs:
            (path / d).mkdir(parents=True, exist_ok=True)

    def _create_generic_structure(self, path: Path) -> None:
        """Create generic project structure."""
        dirs = ["src", "docs"]
        for d in dirs:
            (path / d).mkdir(exist_ok=True)

    def generate_config_files(self, analysis: ProjectAnalysis) -> dict[str, str]:
        """Generate configuration files content for the project."""
        configs: dict[str, str] = {}

        if not analysis.has_git:
            configs[".gitignore"] = self._generate_gitignore(analysis.project_type)

        if not analysis.has_readme:
            configs["README.md"] = self._generate_readme(analysis)

        if not analysis.has_agents_md:
            configs["AGENTS.md"] = self._generate_agents_md(analysis)

        if (
            analysis.project_type == ProjectType.PYTHON
            and "pyproject.toml" not in analysis.existing_files
        ):
            configs["pyproject.toml"] = self._generate_pyproject(analysis)

        return configs

    def _generate_gitignore(self, project_type: ProjectType) -> str:
        """Generate .gitignore content based on project type."""
        common = """# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Editor directories and files
.idea/
.vscode/
*.swp
*.swo
*~

# Logs
*.log
logs/
"""

        python_specific = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
ENV/
env/
.venv

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json
"""

        node_specific = """
# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.yarn-integrity

# Build
dist/
build/
.cache/
.parcel-cache/

# Testing
coverage/
.nyc_output/
"""

        go_specific = """
# Go
*.exe
*.exe~
*.dll
*.so
*.dylib
*.test
*.out

go.work
go.work.sum

# Build
bin/
"""

        rust_specific = """
# Rust
target/
Cargo.lock

# Build
**/*.rs.bk
"""

        java_specific = """
# Java
*.class
*.jar
*.war
*.ear

# Maven
target/
pom.xml.tag
pom.xml.releaseBackup
pom.xml.versionsBackup
pom.xml.next
release.properties
dependency-reduced-pom.xml

# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar
"""

        content = common
        if project_type == ProjectType.PYTHON:
            content += python_specific
        elif project_type == ProjectType.NODE_JS:
            content += node_specific
        elif project_type == ProjectType.GO:
            content += go_specific
        elif project_type == ProjectType.RUST:
            content += rust_specific
        elif project_type in (ProjectType.JAVA_MAVEN, ProjectType.JAVA_GRADLE):
            content += java_specific

        return content

    def _generate_readme(self, analysis: ProjectAnalysis) -> str:
        """Generate README.md content."""
        project_name = analysis.path.name

        install_cmd = ""
        run_cmd = ""
        test_cmd = ""

        if analysis.project_type == ProjectType.PYTHON:
            install_cmd = "pip install -e ."
            run_cmd = "python -m {package_name}"
            test_cmd = "pytest"
        elif analysis.project_type == ProjectType.NODE_JS:
            install_cmd = "npm install"
            run_cmd = "npm start"
            test_cmd = "npm test"
        elif analysis.project_type == ProjectType.GO:
            install_cmd = "go mod download"
            run_cmd = "go run ./cmd/{project_name}"
            test_cmd = "go test ./..."
        elif analysis.project_type == ProjectType.RUST:
            install_cmd = "cargo build"
            run_cmd = "cargo run"
            test_cmd = "cargo test"

        return f"""# {project_name}

## Description

{project_name} - A {analysis.project_type.value} project.

## Installation

```bash
{install_cmd}
```

## Usage

```bash
{run_cmd}
```

## Testing

```bash
{test_cmd}
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
"""

    def _generate_agents_md(self, analysis: ProjectAnalysis) -> str:
        """Generate AGENTS.md content."""
        project_name = analysis.path.name

        setup_cmd = ""
        lint_cmd = ""
        test_cmd = ""

        if analysis.project_type == ProjectType.PYTHON:
            setup_cmd = """```bash
pip install -e ".[dev]"
```"""
            lint_cmd = """```bash
ruff check .
ruff format .
mypy
```"""
            test_cmd = """```bash
pytest
pytest --cov
```"""
        elif analysis.project_type == ProjectType.NODE_JS:
            setup_cmd = """```bash
npm install
```"""
            lint_cmd = """```bash
npm run lint
npm run format
```"""
            test_cmd = """```bash
npm test
```"""
        elif analysis.project_type == ProjectType.GO:
            setup_cmd = """```bash
go mod download
```"""
            lint_cmd = """```bash
golangci-lint run
```"""
            test_cmd = """```bash
go test ./...
```"""
        elif analysis.project_type == ProjectType.RUST:
            setup_cmd = """```bash
cargo build
```"""
            lint_cmd = """```bash
cargo clippy
cargo fmt
```"""
            test_cmd = """```bash
cargo test
```"""
        else:
            setup_cmd = "See project documentation for setup instructions."
            lint_cmd = "See project documentation for linting instructions."
            test_cmd = "See project documentation for testing instructions."

        return f"""# AGENTS.md - {project_name}

{project_name} is a {analysis.project_type.value} project.

## Commands

### Setup

{setup_cmd}

### Lint & Format

{lint_cmd}

### Test

{test_cmd}

## Code Style

Follow the project's existing code style and conventions.

## Architecture

Project type: {analysis.project_type.value}

## Key Patterns

- Keep code clean and well-documented
- Write tests for new functionality
- Follow the existing project structure
"""

    def _generate_pyproject(self, analysis: ProjectAnalysis) -> str:
        """Generate pyproject.toml content."""
        project_name = analysis.path.name

        return f"""[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{project_name}"
version = "0.1.0"
description = "A Python project"
readme = "README.md"
requires-python = ">=3.11"
license = {{text = "MIT"}}
authors = [
    {{name = "Your Name", email = "your.email@example.com"}}
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
"""

    def install_dependencies(self, project_type: ProjectType) -> bool:
        """Install project dependencies automatically."""
        try:
            if project_type == ProjectType.PYTHON:
                return self._install_python_deps()
            elif project_type == ProjectType.NODE_JS:
                return self._install_node_deps()
            elif project_type == ProjectType.GO:
                return self._install_go_deps()
            elif project_type == ProjectType.RUST:
                return self._install_rust_deps()
            return True
        except Exception:
            return False

    def _install_python_deps(self) -> bool:
        """Install Python dependencies."""
        commands = [
            ["pip", "install", "-e", ".[dev]"],
            ["pip", "install", "-e", "."],
            ["pip", "install", "-r", "requirements.txt"],
        ]

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue

        return False

    def _install_node_deps(self) -> bool:
        """Install Node.js dependencies."""
        managers = [
            (["npm", "install"], "package-lock.json"),
            (["yarn", "install"], "yarn.lock"),
            (["pnpm", "install"], "pnpm-lock.yaml"),
        ]

        for cmd, lockfile in managers:
            if Path(lockfile).exists() or not any(Path(lf).exists() for _, lf in managers):
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode == 0:
                        return True
                except Exception:
                    continue

        return False

    def _install_go_deps(self) -> bool:
        """Install Go dependencies."""
        try:
            result = subprocess.run(
                ["go", "mod", "download"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _install_rust_deps(self) -> bool:
        """Install Rust dependencies."""
        try:
            result = subprocess.run(
                ["cargo", "fetch"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def auto_initialize(self, path: Path) -> InitResult:
        """Automatically initialize a project.

        Flow: Detect → Analyze → Create Structure → Generate Files → Install Deps
        """
        files_created: list[str] = []
        files_skipped: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        next_steps: list[str] = []

        project_type = self.detect_project_type(path)
        if project_type is None:
            return InitResult(
                success=False,
                project_type=ProjectType.GENERIC,
                path=path,
                errors=["Path does not exist or is not a directory"],
            )

        analysis = self.analyze_project(path)

        if not analysis.has_git:
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=path,
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                files_created.append(".git/")
                next_steps.append("Configure git: git config user.name 'Your Name'")
                next_steps.append("Configure git: git config user.email 'your.email@example.com'")
            except Exception as e:
                warnings.append(f"Could not initialize git repository: {e}")

        if not self.create_project_structure(path, project_type):
            errors.append("Failed to create project structure")

        configs = self.generate_config_files(analysis)

        for filename, content in configs.items():
            file_path = path / filename
            if file_path.exists():
                files_skipped.append(filename)
                warnings.append(f"{filename} already exists, skipping")
            else:
                try:
                    file_path.write_text(content, encoding="utf-8")
                    files_created.append(filename)
                except Exception as e:
                    errors.append(f"Failed to create {filename}: {e}")

        if not analysis.has_tests and project_type in (ProjectType.PYTHON,):
            tests_dir = path / "tests"
            if not tests_dir.exists():
                try:
                    tests_dir.mkdir(exist_ok=True)
                    (tests_dir / "__init__.py").touch()
                    files_created.append("tests/")
                    next_steps.append("Add tests to the tests/ directory")
                except Exception as e:
                    warnings.append(f"Could not create tests directory: {e}")

        deps_installed = await asyncio.get_event_loop().run_in_executor(
            None, self.install_dependencies, project_type
        )

        if not deps_installed:
            warnings.append("Could not install dependencies automatically")
            next_steps.append("Install dependencies manually")

        if project_type == ProjectType.PYTHON:
            next_steps.extend(
                [
                    "Create a virtual environment: python -m venv .venv",
                    "Activate it: source .venv/bin/activate (Linux/Mac) or .venv\\Scripts\\activate (Windows)",
                    "Install dependencies: pip install -e '.[dev]'",
                ]
            )
        elif project_type == ProjectType.NODE_JS:
            next_steps.extend(
                [
                    "Install dependencies: npm install",
                    "Start developing: npm run dev (if available)",
                ]
            )
        elif project_type == ProjectType.GO:
            next_steps.extend(
                [
                    "Run the project: go run ./cmd/...",
                    "Build the project: go build ./cmd/...",
                ]
            )
        elif project_type == ProjectType.RUST:
            next_steps.extend(
                [
                    "Build the project: cargo build",
                    "Run the project: cargo run",
                ]
            )

        next_steps.append("Review and update README.md with your project details")
        next_steps.append("Review and update AGENTS.md with project-specific instructions")

        return InitResult(
            success=len(errors) == 0,
            project_type=project_type,
            path=path,
            files_created=files_created,
            files_skipped=files_skipped,
            errors=errors,
            warnings=warnings,
            next_steps=next_steps,
        )
