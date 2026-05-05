"""Enhanced knowledge base with documentation downloading.

Integrates builtin knowledge and downloadable documentation
for comprehensive knowledge retrieval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from openlaoke.core.doc_downloader import DocumentationDownloader, DocumentChunk


@dataclass
class KnowledgeSnippet:
    topic: str
    content: str
    source: str
    relevance_score: float = 1.0
    tags: list[str] = field(default_factory=list)
    language: str = "general"
    url: str = ""


class EnhancedKnowledgeBase:
    """Knowledge base with builtin knowledge and downloadable docs."""

    BUILTIN_KNOWLEDGE: dict[str, dict[str, str | list[str]]] = {
        "python_basics": {
            "topic": "Python Programming Basics",
            "content": """
Python fundamentals for small models:

1. Function definition with type hints:
```python
def calculate_sum(numbers: list[int]) -> int:
    \"\"\"Calculate sum of numbers.\"\"\"
    return sum(numbers)
```

2. Class with __init__:
```python
class Calculator:
    def __init__(self, name: str) -> None:
        self.name = name
        self.result = 0.0

    def add(self, x: float, y: float) -> float:
        self.result = x + y
        return self.result
```

3. Loops and conditions:
```python
for i in range(10):
    if i % 2 == 0:
        print(f"{i} is even")
    else:
        print(f"{i} is odd")
```

4. Import statements (always at top):
```python
from __future__ import annotations
import time
from pathlib import Path
from typing import Any
```

Critical syntax rules:
- Always use `def function_name(params) -> return_type:`
- Always indent with 4 spaces
- Always include docstring with triple quotes
- Never forget `:` after if/for/def/class
""",
            "source": "Python Official Tutorial",
            "tags": ["python", "basics", "syntax", "functions", "classes"],
            "language": "python",
        },
        "javascript_basics": {
            "topic": "JavaScript Programming Basics",
            "content": """
JavaScript fundamentals for small models:

1. Function definition (ES6+):
```javascript
function calculateSum(numbers) {
    return numbers.reduce((a, b) => a + b, 0);
}

// Arrow function
const calculateSum = (numbers) => {
    return numbers.reduce((a, b) => a + b, 0);
};
```

2. Class syntax:
```javascript
class Calculator {
    constructor(name) {
        this.name = name;
        this.result = 0;
    }

    add(x, y) {
        this.result = x + y;
        return this.result;
    }
}
```

3. Async/await:
```javascript
async function fetchData(url) {
    const response = await fetch(url);
    const data = await response.json();
    return data;
}
```
""",
            "source": "JavaScript MDN Guide",
            "tags": ["javascript", "js", "basics", "syntax", "es6"],
            "language": "javascript",
        },
        "rust_basics": {
            "topic": "Rust Programming Basics",
            "content": """
Rust fundamentals for small models:

1. Function definition:
```rust
fn calculate_sum(numbers: &[i32]) -> i32 {
    numbers.iter().sum()
}
```

2. Struct and impl:
```rust
struct Calculator {
    name: String,
    result: f64,
}

impl Calculator {
    fn new(name: &str) -> Self {
        Calculator {
            name: name.to_string(),
            result: 0.0,
        }
    }
}
```

3. Error handling:
```rust
fn divide(a: f64, b: f64) -> Result<f64, String> {
    if b == 0.0 {
        Err("Division by zero".to_string())
    } else {
        Ok(a / b)
    }
}
```

Ownership rules:
- Each value has exactly one owner
- Use `&` for borrowing (references)
- Use `&mut` for mutable borrowing
""",
            "source": "Rust Book",
            "tags": ["rust", "basics", "syntax", "ownership", "structs"],
            "language": "rust",
        },
        "go_basics": {
            "topic": "Go Programming Basics",
            "content": """
Go fundamentals for small models:

1. Function definition:
```go
func calculateSum(numbers []int) int {
    sum := 0
    for _, n := range numbers {
        sum += n
    }
    return sum
}
```

2. Struct and methods:
```go
type Calculator struct {
    name   string
    result float64
}

func NewCalculator(name string) *Calculator {
    return &Calculator{name: name, result: 0.0}
}

func (c *Calculator) Add(x, y float64) float64 {
    c.result = x + y
    return c.result
}
```

3. Error handling:
```go
func divide(a, b float64) (float64, error) {
    if b == 0.0 {
        return 0, errors.New("division by zero")
    }
    return a / b, nil
}
```
""",
            "source": "Go Tour",
            "tags": ["go", "golang", "basics", "syntax", "structs", "goroutines"],
            "language": "go",
        },
    }

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".openlaoke" / "knowledge"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_cache: dict[str, KnowledgeSnippet] = {}
        self.downloaded_chunks: list[DocumentChunk] = []
        self.downloader = DocumentationDownloader(cache_dir)

        self._load_builtin_knowledge()
        self._load_downloaded_knowledge()

    def _load_builtin_knowledge(self) -> None:
        """Load built-in knowledge snippets."""
        for key, data in self.BUILTIN_KNOWLEDGE.items():
            self.knowledge_cache[key] = KnowledgeSnippet(
                topic=str(data["topic"]),
                content=str(data["content"]),
                source=str(data["source"]),
                tags=(
                    [str(t) for t in tags_raw]
                    if isinstance((tags_raw := data.get("tags", [])), list)
                    else [str(tags_raw)]
                    if isinstance(tags_raw, str)
                    else []
                ),
                language=str(data.get("language", "general")),
            )

    def _load_downloaded_knowledge(self) -> None:
        """Load previously downloaded knowledge."""
        index_file = self.cache_dir / "downloaded_index.json"

        if index_file.exists():
            try:
                with open(index_file, encoding="utf-8") as f:
                    index_data = json.load(f)

                for chunk_data in index_data.get("chunks", []):
                    chunk = DocumentChunk(
                        doc_id=chunk_data["doc_id"],
                        source=chunk_data["source"],
                        title=chunk_data["title"],
                        content=chunk_data["content"],
                        url=chunk_data["url"],
                        category=chunk_data["category"],
                        language=chunk_data["language"],
                        chunk_index=chunk_data["chunk_index"],
                        metadata=chunk_data.get("metadata", {}),
                    )
                    self.downloaded_chunks.append(chunk)

                print(f"Loaded {len(self.downloaded_chunks)} downloaded knowledge chunks")
            except Exception as e:
                print(f"Error loading downloaded knowledge: {e}")

    def download_for_task(self, task_description: str, force: bool = False) -> int:
        """Download relevant documentation for a task."""
        chunks = self.downloader.download_task_relevant_docs(task_description, force=force)

        self.downloaded_chunks.extend(chunks)

        self._save_downloaded_index()

        return len(chunks)

    def _save_downloaded_index(self) -> None:
        """Save downloaded knowledge index."""
        index_file = self.cache_dir / "downloaded_index.json"

        chunks_data = [
            {
                "doc_id": chunk.doc_id,
                "source": chunk.source,
                "title": chunk.title,
                "content": chunk.content,
                "url": chunk.url,
                "category": chunk.category,
                "language": chunk.language,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
            }
            for chunk in self.downloaded_chunks
        ]

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(
                {"chunks": chunks_data, "total": len(chunks_data)}, f, ensure_ascii=False, indent=2
            )

    def search(
        self,
        query: str,
        max_results: int = 5,
        language: str | None = None,
        category: str | None = None,
    ) -> list[KnowledgeSnippet]:
        """Search knowledge base for relevant information."""
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        scored: list[tuple[float, KnowledgeSnippet]] = []

        for snippet in self.knowledge_cache.values():
            if language and snippet.language != language and snippet.language != "general":
                continue

            score = self._calculate_relevance(snippet, query_lower, query_words)

            if score > 0:
                scored.append((score, snippet))

        for chunk in self.downloaded_chunks:
            if language and chunk.language != language and chunk.language != "general":
                continue
            if category and chunk.category != category:
                continue

            score = self._calculate_chunk_relevance(chunk, query_lower, query_words)

            if score > 0:
                snippet = KnowledgeSnippet(
                    topic=chunk.title,
                    content=chunk.content,
                    source=chunk.source,
                    relevance_score=score,
                    tags=[chunk.category, chunk.language],
                    language=chunk.language,
                    url=chunk.url,
                )
                scored.append((score, snippet))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [snippet for score, snippet in scored[:max_results]]

    def _calculate_relevance(
        self, snippet: KnowledgeSnippet, query_lower: str, query_words: set[str]
    ) -> float:
        """Calculate relevance score for builtin knowledge."""
        score = 0.0

        if query_lower in snippet.topic.lower():
            score += 3.0

        for word in query_words:
            if word in snippet.content.lower():
                score += 1.0

        for tag in snippet.tags:
            if tag in query_words:
                score += 2.0

        return score

    def _calculate_chunk_relevance(
        self, chunk: DocumentChunk, query_lower: str, query_words: set[str]
    ) -> float:
        """Calculate relevance score for downloaded chunk."""
        score = 0.0

        if query_lower in chunk.title.lower():
            score += 4.0

        if query_lower in chunk.source.lower():
            score += 3.0

        for word in query_words:
            if word in chunk.content.lower():
                score += 0.5

        if chunk.category in query_words:
            score += 2.0

        return score

    def get_examples(self, language: str, max_examples: int = 3) -> list[str]:
        """Get code examples for a language."""
        examples = []

        if language in ["python", "py"]:
            examples.append(
                'def example_function(x: int, y: int) -> int:\n    """Example function."""\n    return x + y'
            )
            examples.append(
                "class ExampleClass:\n    def __init__(self, name: str) -> None:\n        self.name = name"
            )
            examples.append(
                'for i in range(10):\n    if i % 2 == 0:\n        print(f"{i} is even")'
            )

        elif language in ["javascript", "js"]:
            examples.append("function exampleFunction(x, y) {\n    return x + y;\n}")
            examples.append(
                "class ExampleClass {\n    constructor(name) {\n        this.name = name;\n    }\n}"
            )

        elif language == "rust":
            examples.append("fn example_function(x: i32, y: i32) -> i32 {\n    x + y\n}")
            examples.append("struct ExampleStruct {\n    name: String,\n}")

        elif language == "go":
            examples.append("func exampleFunction(x, y int) int {\n    return x + y\n}")
            examples.append("type ExampleStruct struct {\n    name string\n}")

        return examples[:max_examples]


def create_knowledge_base(cache_dir: Path | None = None) -> EnhancedKnowledgeBase:
    """Create an enhanced knowledge base instance."""
    return EnhancedKnowledgeBase(cache_dir)
