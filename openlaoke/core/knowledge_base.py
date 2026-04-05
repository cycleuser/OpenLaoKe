"""Knowledge base system for small models.

Inspired by GangDan project - retrieve knowledge from official docs
to help small models generate better code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class KnowledgeSnippet:
    topic: str
    content: str
    source: str
    relevance_score: float = 1.0
    tags: list[str] = field(default_factory=list)


class KnowledgeBase:
    """Local knowledge base for small models."""

    BUILTIN_KNOWLEDGE = {
        "cpu_benchmark": {
            "topic": "CPU Benchmark Implementation",
            "content": """
To measure real CPU performance:

1. Single-core benchmark:
   - Use math operations (sin, cos, sqrt, log)
   - Count operations per second
   - Calculate GFLOPS (Giga Floating-point Operations Per Second)

2. Multi-core benchmark:
   - Use multiprocessing.Pool or ProcessPoolExecutor
   - Distribute work across all cores
   - Measure parallel efficiency

Example operations that stress CPU:
```python
import math
result = math.sin(x) * math.cos(x) + math.sqrt(abs(x))
```

Key metrics:
- Operations/second (higher is better)
- GFLOPS = (ops/sec) / 1e9
- Parallelism factor = multi_core_score / single_core_score

Python libraries to use:
- `time.perf_counter()` for accurate timing
- `multiprocessing.cpu_count()` to get core count
- `concurrent.futures.ProcessPoolExecutor` for parallel execution

Important: Use real calculations, NOT estimates!
""",
            "source": "Python Official Documentation",
            "tags": ["cpu", "benchmark", "performance", "multiprocessing"],
        },
        "file_operations": {
            "topic": "File Operations Best Practices",
            "content": """
Python file operations best practices:

1. Always use context manager (with statement):
```python
with open('file.txt', 'w') as f:
    f.write(content)
```

2. Check file existence:
```python
from pathlib import Path
if Path('file.txt').exists():
    # file exists
```

3. Create directories safely:
```python
Path('output').mkdir(parents=True, exist_ok=True)
```

4. Read/write JSON:
```python
import json
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)
```

Common errors to avoid:
- SyntaxError: Check for missing parentheses, quotes
- FileNotFoundError: Use Path.exists() first
- PermissionError: Check write permissions
""",
            "source": "Python Best Practices",
            "tags": ["file", "io", "path", "json"],
        },
        "python_syntax": {
            "topic": "Python Syntax Common Errors",
            "content": """
Common Python syntax errors and fixes:

1. Missing closing parenthesis:
```python
# Wrong
result = int(abc

# Correct
result = int(abc)
```

2. IndentationError:
- Use 4 spaces (not tabs)
- Be consistent with indentation level

3. Invalid syntax on function definition:
```python
# Wrong
def function(:
    pass

# Correct  
def function():
    pass
```

4. Variable assignment in return:
```python
# Wrong
return x = 5

# Correct
x = 5
return x
```

5. Mixing tabs and spaces:
- Configure editor to show whitespace
- Use auto-formatting tools (black, ruff)

Debug tips:
- Check the line BEFORE the error
- Look for missing colons, brackets, parentheses
- Use `python -m py_compile file.py` to check syntax
""",
            "source": "Python Debugging Guide",
            "tags": ["syntax", "error", "debug", "python"],
        },
    }

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".openlaoke" / "knowledge"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_cache: dict[str, KnowledgeSnippet] = {}

        self._load_builtin_knowledge()

    def _load_builtin_knowledge(self) -> None:
        """Load built-in knowledge snippets."""
        for key, data in self.BUILTIN_KNOWLEDGE.items():
            self.knowledge_cache[key] = KnowledgeSnippet(
                topic=data["topic"],
                content=data["content"],
                source=data["source"],
                tags=data.get("tags", []),
            )

    def search(self, query: str, max_results: int = 3) -> list[KnowledgeSnippet]:
        """Search knowledge base for relevant information."""
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        scored: list[tuple[float, KnowledgeSnippet]] = []

        for snippet in self.knowledge_cache.values():
            score = 0.0

            if query_lower in snippet.topic.lower():
                score += 3.0

            for word in query_words:
                if word in snippet.content.lower():
                    score += 1.0

            for tag in snippet.tags:
                if tag in query_words:
                    score += 2.0

            if score > 0:
                scored.append((score, snippet))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:max_results]]

    def enhance_prompt(self, user_request: str, base_prompt: str) -> str:
        """Enhance system prompt with relevant knowledge."""
        relevant = self.search(user_request)

        if not relevant:
            return base_prompt

        knowledge_sections = ["\n📚 RELEVANT KNOWLEDGE BASE:\n"]

        for i, snippet in enumerate(relevant, 1):
            knowledge_sections.append(f"\n--- Knowledge {i}: {snippet.topic} ---\n")
            knowledge_sections.append(f"Source: {snippet.source}\n")
            knowledge_sections.append(snippet.content)
            knowledge_sections.append("\n")

        knowledge_sections.append(
            "\nUse this knowledge to generate ACCURATE code. Double-check syntax before writing!\n"
        )

        return base_prompt + "\n".join(knowledge_sections)


def create_knowledge_base(cache_dir: Path | None = None) -> KnowledgeBase:
    """Create a knowledge base instance."""
    return KnowledgeBase(cache_dir)
