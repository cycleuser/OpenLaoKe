"""Intent parser for programming tasks.

Parses user natural language requests into structured intents that can be
converted to ComponentSpecs for fine-grained task decomposition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntentType(StrEnum):
    WRITE_PROGRAM = "write_program"
    WRITE_FUNCTION = "write_function"
    WRITE_CLASS = "write_class"
    DEBUG_CODE = "debug_code"
    REFACTOR_CODE = "refactor_code"
    TEST_CODE = "test_code"
    ANALYZE_CODE = "analyze_code"
    DOCUMENT_CODE = "document_code"
    UNKNOWN = "unknown"


class ProgrammingLanguage(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CPP = "cpp"
    UNKNOWN = "unknown"


class TaskComplexity(StrEnum):
    ATOMIC = "atomic"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ProgrammingIntent:
    intent_type: IntentType
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    task_name: str = ""
    description: str = ""
    requirements: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.MODERATE
    confidence: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    raw_request: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "language": self.language.value,
            "task_name": self.task_name,
            "description": self.description,
            "requirements": self.requirements,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "constraints": self.constraints,
            "complexity": self.complexity.value,
            "confidence": self.confidence,
            "context": self.context,
            "raw_request": self.raw_request,
        }


class IntentParser:
    INTENT_PATTERNS = {
        IntentType.WRITE_PROGRAM: [
            r"(?:write|create|develop|build|implement)\s+(?:a\s+)?(?:new\s+)?(?:program|app|application|tool|utility|script)",
            r"(?:make|generate)\s+(?:a\s+)?(?:program|app|application)",
            r"(?:i\s+need|need|want)\s+(?:a\s+)?(?:program|app|application|tool)",
            r"(?:write|create)\s+(?:a\s+)?(?:python|javascript|rust|go|java)\s+(?:program|app|script)",
            r"写.*程序",
            r"创建.*程序",
            r"编写.*程序",
            r"写.*python",
            r"写一个.*文件",
            r"实现.*程序",
        ],
        IntentType.WRITE_FUNCTION: [
            r"(?:write|create|implement|define)\s+(?:a\s+)?(?:new\s+)?(?:function|method)",
            r"(?:add|make)\s+(?:a\s+)?(?:function|method)",
            r"(?:function|method)\s+(?:to|for)\s+",
            r"写.*函数",
            r"创建.*函数",
            r"实现.*函数",
        ],
        IntentType.WRITE_CLASS: [
            r"(?:write|create|implement|define)\s+(?:a\s+)?(?:new\s+)?(?:class|object|type)",
            r"(?:add|make)\s+(?:a\s+)?(?:class)",
            r"(?:class|object)\s+(?:to|for)\s+",
            r"写.*类",
            r"创建.*类",
            r"实现.*类",
        ],
        IntentType.DEBUG_CODE: [
            r"(?:debug|fix|solve|troubleshoot)\s+(?:the\s+)?(?:error|bug|issue|problem)",
            r"(?:error|bug|issue)\s+(?:in\s+)?(?:the\s+)?(?:code|program|function)",
            r"(?:something\s+is\s+wrong|not\s+working|broken)",
            r"(?:help\s+me\s+fix|how\s+to\s+fix)",
            r"调试|修复|解决.*错误|bug|问题",
        ],
        IntentType.REFACTOR_CODE: [
            r"(?:refactor|improve|optimize|clean\s+up|rewrite)\s+(?:the\s+)?(?:code|program|function)",
            r"(?:make\s+the\s+code)\s+(?:better|cleaner|more\s+efficient)",
            r"重构|改进|优化|重写.*代码",
        ],
        IntentType.TEST_CODE: [
            r"(?:write|create|add|make)\s+(?:tests?|test\s+cases?)",
            r"(?:test\s+the|testing\s+the)",
            r"写.*测试|创建.*测试",
        ],
        IntentType.ANALYZE_CODE: [
            r"(?:analyze|review|inspect|examine|check)\s+(?:the\s+)?(?:code|program|function)",
            r"(?:what\s+does\s+this\s+code\s+do)",
            r"分析|检查|审查.*代码",
        ],
        IntentType.DOCUMENT_CODE: [
            r"(?:document|add\s+docs|add\s+documentation)\s+(?:the\s+)?(?:code|function|class)",
            r"(?:write\s+comments|add\s+comments)",
            r"添加.*文档|注释",
        ],
    }

    LANGUAGE_PATTERNS = {
        ProgrammingLanguage.PYTHON: [
            r"\bpython\b(?:\s+program|\s+script|\s+code)?",
            r"\bpy\b",
            r"\.py\b",
        ],
        ProgrammingLanguage.JAVASCRIPT: [
            r"\bjavascript\b(?:\s+program|\s+script|\s+code)?",
            r"\bjs\b",
            r"\.js\b",
            r"\bnode\.js\b",
        ],
        ProgrammingLanguage.TYPESCRIPT: [
            r"\btypescript\b(?:\s+program|\s+script|\s+code)?",
            r"\bts\b",
            r"\.ts\b",
        ],
        ProgrammingLanguage.RUST: [
            r"\brust\b(?:\s+program|\s+code)?",
            r"\.rs\b",
        ],
        ProgrammingLanguage.GO: [
            r"\bgo\b(?:\s+program|\s+code)?(?:lang)?",
            r"\bgolang\b",
            r"\.go\b",
        ],
        ProgrammingLanguage.JAVA: [
            r"\bjava\b(?:\s+program|\s+code)?",
            r"\.java\b",
        ],
        ProgrammingLanguage.CPP: [
            r"\bc\+\+\b(?:\s+program|\s+code)?",
            r"\bcpp\b",
            r"\.cpp\b",
            r"\.cxx\b",
        ],
    }

    FEATURE_KEYWORDS = {
        "benchmark": ["performance", "speed", "measure", "time", "ops/sec", "benchmark"],
        "calculator": ["calculate", "compute", "math", "add", "subtract", "multiply", "divide"],
        "converter": ["convert", "transform", "translate", "change format"],
        "parser": ["parse", "parse file", "parse format", "extract", "analyze"],
        "generator": ["generate", "create", "produce", "make"],
        "validator": ["validate", "check", "verify", "test"],
        "monitor": ["monitor", "watch", "track", "observe", "status"],
        "logger": ["log", "record", "write log", "logging"],
        "downloader": ["download", "fetch", "retrieve", "get"],
        "uploader": ["upload", "send", "post", "push"],
        "processor": ["process", "handle", "manage", "execute"],
        "manager": ["manage", "manager", "management", "admin", "control"],
        "analyzer": ["analyze", "examine", "study", "inspect"],
        "optimizer": ["optimize", "improve", "enhance", "speed up"],
        "scheduler": ["schedule", "plan", "timing", "cron"],
        "server": ["server", "api", "endpoint", "http", "rest"],
        "client": ["client", "request", "call", "connect"],
        "database": ["database", "db", "sql", "query", "store"],
        "cache": ["cache", "store", "save", "memoize"],
        "queue": ["queue", "buffer", "enqueue", "dequeue"],
        "sort": ["sort", "order", "arrange", "rank"],
        "search": ["search", "find", "lookup", "query"],
        "filter": ["filter", "select", "pick", "where"],
        "map": ["map", "transform", "apply", "convert"],
        "reduce": ["reduce", "aggregate", "combine", "sum"],
        "encrypt": ["encrypt", "secure", "hash", "crypto"],
        "compress": ["compress", "zip", "pack", "reduce size"],
        "image": ["image", "picture", "photo", "visual"],
        "audio": ["audio", "sound", "music", "wav", "mp3"],
        "video": ["video", "movie", "mp4", "avi"],
        "text": ["text", "string", "word", "sentence"],
        "file": ["file", "read file", "write file", "io"],
        "network": ["network", "http", "socket", "tcp", "udp"],
        "gui": ["gui", "ui", "interface", "window", "button", "tkinter", "qt"],
        "cli": ["cli", "command", "argument", "option", "flag"],
        "web": ["web", "html", "css", "browser", "frontend"],
        "api": ["api", "endpoint", "rest", "graphql", "swagger"],
    }

    COMPLEXITY_INDICATORS = {
        TaskComplexity.ATOMIC: [
            "simple",
            "basic",
            "minimal",
            "tiny",
            "single function",
        ],
        TaskComplexity.SIMPLE: [
            "small",
            "easy",
            "straightforward",
            "one file",
        ],
        TaskComplexity.MODERATE: [
            "medium",
            "moderate",
            "standard",
            "typical",
            "multiple functions",
        ],
        TaskComplexity.COMPLEX: [
            "complex",
            "advanced",
            "large",
            "full",
            "complete",
            "comprehensive",
            "multiple modules",
            "architecture",
            "system",
        ],
    }

    def __init__(self) -> None:
        self._cache: dict[str, ProgrammingIntent] = {}

    def parse(self, user_request: str) -> ProgrammingIntent:
        user_request = user_request.strip()

        if not user_request:
            return ProgrammingIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                raw_request=user_request,
            )

        if user_request in self._cache:
            return self._cache[user_request]

        intent_type = self._detect_intent_type(user_request)
        language = self._detect_language(user_request)
        task_name = self._extract_task_name(user_request, intent_type)
        description = self._extract_description(user_request)
        requirements = self._extract_requirements(user_request)
        inputs = self._extract_inputs(user_request)
        outputs = self._extract_outputs(user_request)
        constraints = self._extract_constraints(user_request)
        complexity = self._detect_complexity(user_request)
        confidence = self._calculate_confidence(
            intent_type,
            language,
            task_name,
            user_request,
        )

        intent = ProgrammingIntent(
            intent_type=intent_type,
            language=language,
            task_name=task_name,
            description=description,
            requirements=requirements,
            inputs=inputs,
            outputs=outputs,
            constraints=constraints,
            complexity=complexity,
            confidence=confidence,
            raw_request=user_request,
        )

        self._cache[user_request] = intent
        return intent

    def _detect_intent_type(self, request: str) -> IntentType:
        lower_request = request.lower()

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, lower_request, re.IGNORECASE):
                        return intent_type
                except re.error:
                    continue

        if any(
            keyword in lower_request
            for keyword in ["write", "create", "build", "implement", "develop", "make"]
        ):
            return IntentType.WRITE_PROGRAM

        return IntentType.UNKNOWN

    def _detect_language(self, request: str) -> ProgrammingLanguage:
        lower_request = request.lower()

        for language, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower_request, re.IGNORECASE):
                    return language

        return ProgrammingLanguage.PYTHON

    def _extract_task_name(self, request: str, intent_type: IntentType) -> str:
        lower_request = request.lower()

        for feature_name, keywords in self.FEATURE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in lower_request:
                    return feature_name.replace("_", " ")

        if intent_type == IntentType.WRITE_PROGRAM:
            match = re.search(
                r"(?:program|app|application|tool|utility)\s+(?:called\s+)?['\"]?(\w+)['\"]?",
                lower_request,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

            match = re.search(
                r"(?:for|to)\s+(\w+)",
                lower_request,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

        if intent_type in [IntentType.WRITE_FUNCTION, IntentType.WRITE_CLASS]:
            match = re.search(
                r"(?:function|method|class)\s+(?:called\s+)?['\"]?(\w+)['\"]?",
                lower_request,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

            match = re.search(
                r"(?:for|to)\s+(\w+)",
                lower_request,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

        return "unnamed_task"

    def _extract_description(self, request: str) -> str:
        description_parts = []

        lower_request = request.lower()

        action_match = re.search(
            r"(?:write|create|develop|build|implement|make|generate)\s+(?:a\s+)?(?:new\s+)?(.+?)(?:\s+that|\s+to|\s+for|\s+with|\s+in)",
            lower_request,
            re.IGNORECASE,
        )
        if action_match:
            description_parts.append(action_match.group(1).strip())

        purpose_match = re.search(
            r"(?:that|to|for)\s+(.+?)(?:\s+with|\s+in|\s+using|\s*$)",
            lower_request,
            re.IGNORECASE,
        )
        if purpose_match:
            description_parts.append(purpose_match.group(1).strip())

        if description_parts:
            return " ".join(description_parts)

        return request

    def _extract_requirements(self, request: str) -> list[str]:
        requirements = []

        lower_request = request.lower()

        capability_patterns = [
            r"(?:should|must|needs\s+to|have\s+to)\s+(.+?)(?:\s+and|\s*$)",
            r"(?:support|handle|process|work\s+with)\s+(.+?)(?:\s+and|\s*$)",
            r"(?:features?|capabilities?):\s*(.+?)(?:\s*$)",
        ]

        for pattern in capability_patterns:
            matches = re.findall(pattern, lower_request, re.IGNORECASE)
            for match in matches:
                requirement = match.strip()
                if requirement and len(requirement) > 3:
                    requirements.append(requirement)

        return requirements

    def _extract_inputs(self, request: str) -> list[str]:
        inputs = []

        lower_request = request.lower()

        input_patterns = [
            r"input[:\s]+(.+?)(?:\s|$)",
            r"argument[:\s]+(.+?)(?:\s|$)",
            r"parameter[:\s]+(.+?)(?:\s|$)",
            r"take\s+(.+?)\s+as\s+input",
            r"accept\s+(.+?)\s+as\s+(?:input|argument|parameter)",
            r"from\s+(.+?)\s+(?:file|source)",
        ]

        for pattern in input_patterns:
            matches = re.findall(pattern, lower_request, re.IGNORECASE)
            for match in matches:
                input_item = match.strip()
                if input_item and len(input_item) > 2:
                    inputs.append(input_item)

        if "takes" in lower_request or "input" in lower_request:
            words = lower_request.split()
            for i, word in enumerate(words):
                if word in ["takes", "input", "as"] and i + 1 < len(words):
                    potential_input = words[i + 1]
                    if potential_input not in ["input", "argument", "parameter", "the", "a", "an"]:
                        inputs.append(potential_input)

        return inputs

    def _extract_outputs(self, request: str) -> list[str]:
        outputs = []

        lower_request = request.lower()

        output_patterns = [
            r"output[:\s]+(.+?)(?:\s|$)",
            r"result[:\s]+(.+?)(?:\s|$)",
            r"return[:\s]+(.+?)(?:\s|$)",
            r"returns\s+(.+?)\s+(?:as\s+)?(?:output|result)",
            r"produce\s+(.+?)\s+(?:as\s+)?(?:output|result)",
            r"generate\s+(.+?)\s+(?:as\s+)?(?:output|result)",
        ]

        for pattern in output_patterns:
            matches = re.findall(pattern, lower_request, re.IGNORECASE)
            for match in matches:
                output_item = match.strip()
                if output_item and len(output_item) > 2:
                    outputs.append(output_item)

        if "returns" in lower_request or "output" in lower_request or "result" in lower_request:
            words = lower_request.split()
            for i, word in enumerate(words):
                if word in ["returns", "output", "result"] and i + 1 < len(words):
                    potential_output = words[i + 1]
                    if potential_output not in [
                        "output",
                        "result",
                        "the",
                        "a",
                        "an",
                        "calculated",
                        "as",
                    ]:
                        outputs.append(potential_output)

        return outputs

    def _extract_constraints(self, request: str) -> list[str]:
        constraints = []

        lower_request = request.lower()

        constraint_patterns = [
            r"(?:constraint|limit|requirement):\s*(.+?)(?:\s*$)",
            r"(?:must\s+be|should\s+be|has\s+to\s+be)\s+(.+?)(?:\s*$)",
            r"(?:no\s+|don't\s+|avoid\s+)(.+?)(?:\s*$)",
            r"(?:under|within|less\s+than|maximum)\s+(\d+)\s*(.+?)(?:\s*$)",
        ]

        for pattern in constraint_patterns:
            matches = re.findall(pattern, lower_request, re.IGNORECASE)
            for match in matches:
                constraint = match.strip() if isinstance(match, str) else f"{match[0]} {match[1]}"
                if constraint and len(constraint) > 2:
                    constraints.append(constraint)

        return constraints

    def _detect_complexity(self, request: str) -> TaskComplexity:
        lower_request = request.lower()

        for complexity, indicators in self.COMPLEXITY_INDICATORS.items():
            for indicator in indicators:
                if indicator in lower_request:
                    return complexity

        word_count = len(request.split())

        if word_count < 10:
            return TaskComplexity.ATOMIC
        elif word_count < 20:
            return TaskComplexity.SIMPLE
        elif word_count < 40:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.COMPLEX

    def _calculate_confidence(
        self,
        intent_type: IntentType,
        language: ProgrammingLanguage,
        task_name: str,
        request: str,
    ) -> float:
        confidence = 0.0

        if intent_type != IntentType.UNKNOWN:
            confidence += 0.4

        if language != ProgrammingLanguage.UNKNOWN:
            confidence += 0.2

        if task_name and task_name != "unnamed_task":
            confidence += 0.2

        word_count = len(request.split())
        if word_count >= 5:
            confidence += 0.1
        if word_count >= 10:
            confidence += 0.1

        return min(confidence, 1.0)

    def suggest_clarifications(self, intent: ProgrammingIntent) -> list[str]:
        questions = []

        if intent.confidence < 0.5:
            questions.append("Could you provide more details about what you want to create?")

        if intent.intent_type == IntentType.UNKNOWN:
            questions.append(
                "What type of code do you want me to write (program, function, class)?"
            )

        if not intent.requirements:
            questions.append("What specific features or capabilities should this have?")

        if not intent.inputs and intent.intent_type in [
            IntentType.WRITE_PROGRAM,
            IntentType.WRITE_FUNCTION,
        ]:
            questions.append("What inputs or parameters should this accept?")

        if not intent.outputs and intent.intent_type in [
            IntentType.WRITE_PROGRAM,
            IntentType.WRITE_FUNCTION,
        ]:
            questions.append("What should the output or result be?")

        return questions
