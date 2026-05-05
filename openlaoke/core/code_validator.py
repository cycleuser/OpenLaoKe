"""Incremental code validation and auto-fix system.

Validates each function/step before proceeding, ensuring
small models produce correct code.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed_code: str | None = None


class CodeValidator:
    """Validates Python code incrementally."""

    def validate_syntax(self, code: str) -> ValidationResult:
        """Check Python syntax validity."""
        errors: list[str] = []
        warnings: list[str] = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Line {e.lineno}: {e.msg}")
            if e.text:
                errors.append(f"  {e.text.strip()}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_function(self, func_code: str) -> ValidationResult:
        """Validate a single function definition."""
        result = self.validate_syntax(func_code)

        if not result.is_valid:
            return result

        try:
            tree = ast.parse(func_code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.returns and "def " in func_code:
                        result.warnings.append(f"Function '{node.name}' missing return type hint")

                    if not ast.get_docstring(node):
                        result.warnings.append(f"Function '{node.name}' missing docstring")
        except Exception as e:
            result.errors.append(f"AST analysis failed: {e}")

        return result

    def auto_fix_syntax(self, code: str) -> str:
        """Attempt to auto-fix common syntax errors."""
        lines = code.split("\n")
        fixed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            fixed_line = line

            # Fix missing closing parentheses
            open_parens = line.count("(") - line.count(")")

            if open_parens > 0 and i + 1 < len(lines):
                # Look ahead for the rest
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith("#"):
                    # Merge with next line if it continues the expression
                    pass

            # Fix else statement
            if "else:" in line and "else" in line and not line.strip().startswith("else:"):
                # Ensure else has proper indentation
                indent = len(line) - len(line.lstrip())
                fixed_line = " " * indent + "else:\n"

            # Fix common patterns
            if "return x = " in line:
                # Fix return with assignment
                match = re.search(r"return\s+(\w+)\s*=\s*(.+)", line)
                if match:
                    var, value = match.groups()
                    indent = len(line) - len(line.lstrip())
                    fixed_line = " " * indent + f"{var} = {value}\n"
                    fixed_line += " " * indent + f"return {var}\n"

            fixed_lines.append(fixed_line)
            i += 1

        return "\n".join(fixed_lines)

    def validate_and_fix(self, code: str) -> tuple[str, ValidationResult]:
        """Validate code and attempt to fix errors."""
        result = self.validate_syntax(code)

        if result.is_valid:
            return code, result

        # Try auto-fix
        fixed_code = self.auto_fix_syntax(code)
        fixed_result = self.validate_syntax(fixed_code)

        if fixed_result.is_valid:
            return fixed_code, ValidationResult(
                is_valid=True,
                warnings=["Code was auto-fixed"],
                fixed_code=fixed_code,
            )

        return code, result


class IncrementalBuilder:
    """Build code incrementally with validation at each step."""

    def __init__(self) -> None:
        self.validator: CodeValidator = CodeValidator()
        self.code_parts: list[str] = []
        self.current_code = ""

    def add_imports(self, imports: str) -> ValidationResult:
        """Add import statements with validation."""
        result = self.validator.validate_syntax(imports)
        if result.is_valid:
            self.code_parts.append(imports)
            self._update_code()
        return result

    def add_function(self, func_code: str) -> ValidationResult:
        """Add a function with validation."""
        result = self.validator.validate_function(func_code)

        if not result.is_valid:
            # Try to fix
            fixed_code, fix_result = self.validator.validate_and_fix(func_code)

            if fix_result.is_valid:
                self.code_parts.append(fixed_code)
                self._update_code()
                return ValidationResult(
                    is_valid=True,
                    warnings=["Function was auto-fixed"],
                )

        if result.is_valid:
            self.code_parts.append(func_code)
            self._update_code()

        return result

    def add_main_block(self, main_code: str) -> ValidationResult:
        """Add main execution block with validation."""
        result = self.validator.validate_syntax(main_code)

        if result.is_valid:
            self.code_parts.append(main_code)
            self._update_code()

        return result

    def _update_code(self) -> None:
        """Update current code from parts."""
        self.current_code = "\n\n".join(self.code_parts)

    def get_final_code(self) -> str:
        """Get the final validated code."""
        return self.current_code

    def validate_final(self) -> ValidationResult:
        """Validate the complete code."""
        return self.validator.validate_syntax(self.current_code)


class ExecutionValidator:
    """Validate code execution step by step."""

    def test_imports(self, code: str) -> ValidationResult:
        """Test if imports work."""
        import_code = "\n".join(
            [line for line in code.split("\n") if line.strip().startswith(("import ", "from "))]
        )

        if not import_code:
            return ValidationResult(is_valid=True)

        try:
            exec(import_code, {})
            return ValidationResult(is_valid=True)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Import error: {e}"],
            )

    def test_syntax_with_python(self, code: str) -> ValidationResult:
        """Test syntax using Python interpreter."""
        temp_file = Path("/tmp/test_code.py")
        temp_file.write_text(code)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(temp_file)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return ValidationResult(is_valid=True)
            else:
                errors = result.stderr.strip().split("\n")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                )
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_execution(self, code: str, timeout: int = 5) -> ValidationResult:
        """Test if code executes without errors."""
        temp_file = Path("/tmp/test_exec.py")
        temp_file.write_text(code)

        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return ValidationResult(
                    is_valid=True,
                    warnings=[result.stdout] if result.stdout else [],
                )
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[result.stderr] if result.stderr else ["Execution failed"],
                )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                is_valid=False,
                errors=[f"Execution timeout ({timeout}s)"],
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Execution error: {e}"],
            )
        finally:
            if temp_file.exists():
                temp_file.unlink()


def create_validated_code(
    parts: list[str], validate_each: bool = True
) -> tuple[str, ValidationResult]:
    """Create code from parts with incremental validation."""
    builder = IncrementalBuilder()

    all_errors = []
    all_warnings = []

    for i, part in enumerate(parts):
        if validate_each:
            if "import " in part or "from " in part:
                result = builder.add_imports(part)
            elif "def " in part:
                result = builder.add_function(part)
            else:
                result = builder.add_main_block(part)

            if not result.is_valid:
                all_errors.extend([f"Part {i}: {e}" for e in result.errors])
                # Try to continue anyway
                builder.code_parts.append(part)
                builder._update_code()
            else:
                all_warnings.extend(result.warnings)

    final_code = builder.get_final_code()
    final_result = builder.validate_final()

    return final_code, ValidationResult(
        is_valid=final_result.is_valid and len(all_errors) == 0,
        errors=final_result.errors + all_errors,
        warnings=all_warnings,
        fixed_code=final_code if final_result.is_valid else None,
    )
