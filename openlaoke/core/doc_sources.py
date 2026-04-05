"""Document sources for knowledge base.

Inspired by GangDan project - comprehensive documentation sources
for all major programming languages and frameworks.
"""

from __future__ import annotations

DOC_SOURCES = {
    "python": {
        "name": "Python",
        "category": "programming_language",
        "urls": [
            "https://docs.python.org/3/tutorial/index.html",
            "https://docs.python.org/3/tutorial/controlflow.html",
            "https://docs.python.org/3/tutorial/datastructures.html",
            "https://docs.python.org/3/tutorial/modules.html",
            "https://docs.python.org/3/tutorial/classes.html",
            "https://docs.python.org/3/tutorial/errors.html",
            "https://docs.python.org/3/library/functions.html",
        ],
        "description": "Python official documentation - core language features",
    },
    "javascript": {
        "name": "JavaScript",
        "category": "programming_language",
        "urls": [
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Introduction",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Grammar_and_types",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Control_flow_and_error_handling",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Loops_and_iteration",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions",
        ],
        "description": "JavaScript MDN guide - modern ES6+ features",
    },
    "typescript": {
        "name": "TypeScript",
        "category": "programming_language",
        "urls": [
            "https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes.html",
            "https://www.typescriptlang.org/docs/handbook/basic-types.html",
            "https://www.typescriptlang.org/docs/handbook/interfaces.html",
            "https://www.typescriptlang.org/docs/handbook/classes.html",
            "https://www.typescriptlang.org/docs/handbook/functions.html",
        ],
        "description": "TypeScript handbook - type system and features",
    },
    "rust": {
        "name": "Rust",
        "category": "programming_language",
        "urls": [
            "https://doc.rust-lang.org/book/ch01-00-getting-started.html",
            "https://doc.rust-lang.org/book/ch03-00-common-programming-concepts.html",
            "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html",
            "https://doc.rust-lang.org/book/ch05-00-structs.html",
            "https://doc.rust-lang.org/book/ch06-00-enums.html",
            "https://doc.rust-lang.org/book/ch10-00-generics.html",
        ],
        "description": "Rust book - ownership, borrowing, and type system",
    },
    "go": {
        "name": "Go",
        "category": "programming_language",
        "urls": [
            "https://go.dev/tour/welcome/1",
            "https://go.dev/tour/basics/1",
            "https://go.dev/tour/flowcontrol/1",
            "https://go.dev/tour/moretypes/1",
            "https://go.dev/tour/methods/1",
            "https://go.dev/tour/concurrency/1",
        ],
        "description": "Go tour - concurrency and simplicity",
    },
    "java": {
        "name": "Java",
        "category": "programming_language",
        "urls": [
            "https://docs.oracle.com/javase/tutorial/java/nutsandbolts/index.html",
            "https://docs.oracle.com/javase/tutorial/java/concepts/index.html",
            "https://docs.oracle.com/javase/tutorial/java/javaOO/index.html",
        ],
        "description": "Java tutorial - OOP and language basics",
    },
    "cpp": {
        "name": "C++",
        "category": "programming_language",
        "urls": [
            "https://en.cppreference.com/w/cpp/language/functions",
            "https://en.cppreference.com/w/cpp/language/classes",
            "https://en.cppreference.com/w/cpp/language/templates",
        ],
        "description": "C++ reference - modern C++ features",
    },
    "numpy": {
        "name": "NumPy",
        "category": "python_library",
        "urls": [
            "https://numpy.org/doc/stable/user/absolute_beginners.html",
            "https://numpy.org/doc/stable/user/basics.creation.html",
            "https://numpy.org/doc/stable/user/basics.indexing.html",
            "https://numpy.org/doc/stable/reference/routines.array-creation.html",
        ],
        "description": "NumPy basics - array operations and numerical computing",
    },
    "pandas": {
        "name": "Pandas",
        "category": "python_library",
        "urls": [
            "https://pandas.pydata.org/docs/user_guide/10min.html",
            "https://pandas.pydata.org/docs/user_guide/indexing.html",
            "https://pandas.pydata.org/docs/user_guide/basics.html",
            "https://pandas.pydata.org/docs/user_guide/io.html",
        ],
        "description": "Pandas - data analysis and manipulation",
    },
    "requests": {
        "name": "Requests",
        "category": "python_library",
        "urls": [
            "https://requests.readthedocs.io/en/latest/user/quickstart/",
            "https://requests.readthedocs.io/en/latest/user/advanced/",
        ],
        "description": "Requests - HTTP library for Python",
    },
    "flask": {
        "name": "Flask",
        "category": "web_framework",
        "urls": [
            "https://flask.palletsprojects.com/en/latest/quickstart/",
            "https://flask.palletsprojects.com/en/latest/tutorial/",
        ],
        "description": "Flask - web framework for Python",
    },
    "fastapi": {
        "name": "FastAPI",
        "category": "web_framework",
        "urls": [
            "https://fastapi.tiangolo.com/tutorial/",
            "https://fastapi.tiangolo.com/tutorial/path-params/",
            "https://fastapi.tiangolo.com/tutorial/query-params/",
            "https://fastapi.tiangolo.com/tutorial/body/",
        ],
        "description": "FastAPI - modern async web framework",
    },
    "pytest": {
        "name": "Pytest",
        "category": "testing_framework",
        "urls": [
            "https://docs.pytest.org/en/stable/getting-started.html",
            "https://docs.pytest.org/en/stable/how-to/assert.html",
            "https://docs.pytest.org/en/stable/how-to/fixtures.html",
        ],
        "description": "Pytest - Python testing framework",
    },
    "react": {
        "name": "React",
        "category": "frontend_framework",
        "urls": [
            "https://react.dev/learn",
            "https://react.dev/learn/thinking-in-react",
            "https://react.dev/reference/react",
        ],
        "description": "React - UI component library",
    },
    "vue": {
        "name": "Vue.js",
        "category": "frontend_framework",
        "urls": [
            "https://vuejs.org/guide/introduction.html",
            "https://vuejs.org/guide/essentials/reactivity-fundamentals.html",
            "https://vuejs.org/guide/essentials/component-basics.html",
        ],
        "description": "Vue.js - progressive JavaScript framework",
    },
    "django": {
        "name": "Django",
        "category": "web_framework",
        "urls": [
            "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
            "https://docs.djangoproject.com/en/stable/intro/tutorial02/",
            "https://docs.djangoproject.com/en/stable/topics/db/models/",
        ],
        "description": "Django - full-stack web framework",
    },
    "sqlalchemy": {
        "name": "SQLAlchemy",
        "category": "database",
        "urls": [
            "https://docs.sqlalchemy.org/en/20/tutorial/",
            "https://docs.sqlalchemy.org/en/20/core/engines.html",
            "https://docs.sqlalchemy.org/en/20/orm/quickstart.html",
        ],
        "description": "SQLAlchemy - ORM and database toolkit",
    },
    "multiprocessing": {
        "name": "Multiprocessing",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/multiprocessing.html",
        ],
        "description": "Python multiprocessing - parallel execution",
    },
    "asyncio": {
        "name": "AsyncIO",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/library/asyncio-task.html",
        ],
        "description": "Python asyncio - asynchronous programming",
    },
    "threading": {
        "name": "Threading",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/threading.html",
        ],
        "description": "Python threading - concurrent execution",
    },
    "pathlib": {
        "name": "Pathlib",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/pathlib.html",
        ],
        "description": "Python pathlib - object-oriented filesystem paths",
    },
    "json": {
        "name": "JSON",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/json.html",
        ],
        "description": "Python json - JSON encoder and decoder",
    },
    "logging": {
        "name": "Logging",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/logging.html",
            "https://docs.python.org/3/howto/logging.html",
        ],
        "description": "Python logging - event logging system",
    },
    "argparse": {
        "name": "Argparse",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/argparse.html",
        ],
        "description": "Python argparse - command-line argument parsing",
    },
    "unittest": {
        "name": "Unittest",
        "category": "testing_framework",
        "urls": [
            "https://docs.python.org/3/library/unittest.html",
        ],
        "description": "Python unittest - unit testing framework",
    },
    "typing": {
        "name": "Typing",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/typing.html",
            "https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html",
        ],
        "description": "Python typing - type hints support",
    },
    "dataclasses": {
        "name": "Dataclasses",
        "category": "python_library",
        "urls": [
            "https://docs.python.org/3/library/dataclasses.html",
        ],
        "description": "Python dataclasses - data classes",
    },
    "pydantic": {
        "name": "Pydantic",
        "category": "python_library",
        "urls": [
            "https://docs.pydantic.dev/latest/",
            "https://docs.pydantic.dev/latest/usage/models/",
        ],
        "description": "Pydantic - data validation using Python type annotations",
    },
    "click": {
        "name": "Click",
        "category": "cli_framework",
        "urls": [
            "https://click.palletsprojects.com/en/latest/quickstart/",
            "https://click.palletsprojects.com/en/latest/options/",
            "https://click.palletsprojects.com/en/latest/arguments/",
        ],
        "description": "Click - command-line interface creation kit",
    },
    "rich": {
        "name": "Rich",
        "category": "python_library",
        "urls": [
            "https://rich.readthedocs.io/en/stable/introduction.html",
            "https://rich.readthedocs.io/en/stable/console.html",
            "https://rich.readthedocs.io/en/stable/tables.html",
        ],
        "description": "Rich - pretty printing and rich text formatting",
    },
}

LANGUAGE_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "rs": "rust",
    "golang": "go",
    "cpp": "c++",
    "c++": "cpp",
}

FRAMEWORK_CATEGORIES = {
    "programming_language": [
        "python",
        "javascript",
        "typescript",
        "rust",
        "go",
        "java",
        "cpp",
    ],
    "python_library": [
        "numpy",
        "pandas",
        "requests",
        "multiprocessing",
        "asyncio",
        "threading",
        "pathlib",
        "json",
        "logging",
        "argparse",
        "typing",
        "dataclasses",
        "pydantic",
        "rich",
    ],
    "web_framework": [
        "flask",
        "fastapi",
        "django",
    ],
    "frontend_framework": [
        "react",
        "vue",
    ],
    "testing_framework": [
        "pytest",
        "unittest",
    ],
    "database": [
        "sqlalchemy",
    ],
    "cli_framework": [
        "click",
    ],
}

TASK_TO_KNOWLEDGE_MAPPING = {
    "benchmark": ["multiprocessing", "asyncio", "threading", "time"],
    "web_api": ["fastapi", "flask", "requests"],
    "data_analysis": ["numpy", "pandas"],
    "testing": ["pytest", "unittest"],
    "cli": ["click", "argparse", "rich"],
    "database": ["sqlalchemy", "json"],
    "file_io": ["pathlib", "json"],
    "async": ["asyncio", "aiohttp"],
    "gui": ["tkinter", "pyqt", "pyside"],
    "network": ["requests", "aiohttp", "socket"],
}


def get_doc_sources() -> dict[str, dict]:
    """Get all documentation sources."""
    return DOC_SOURCES


def get_sources_for_category(category: str) -> list[str]:
    """Get all sources for a given category."""
    return FRAMEWORK_CATEGORIES.get(category, [])


def get_sources_for_task(task_type: str) -> list[str]:
    """Get relevant sources for a task type."""
    return TASK_TO_KNOWLEDGE_MAPPING.get(task_type, [])
