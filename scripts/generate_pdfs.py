#!/usr/bin/env python3
"""Generate PDF from project code and documentation with Unicode support."""

from __future__ import annotations

import os

from fpdf import FPDF


class PDFGenerator(FPDF):
    """Custom PDF generator with Unicode support."""

    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        # Add Unicode font support
        try:
            # Try to use system fonts that support Unicode
            self.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
            self.add_font(
                "DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True
            )
            self.add_font(
                "DejaVuMono", "", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", uni=True
            )
            self.add_font(
                "DejaVuMono",
                "B",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                uni=True,
            )
            self.has_unicode_font = True
        except:
            # Fallback to built-in fonts
            self.has_unicode_font = False

    def header(self) -> None:
        """Add header to each page."""
        if self.page_no() > 1:
            if self.has_unicode_font:
                self.set_font("DejaVu", "", 8)
            else:
                self.set_font("Courier", "", 8)
            self.set_text_color(128, 128, 128)
            self.cell(
                0,
                10,
                f"OpenLaoKe Project - Page {self.page_no()}",
                0,
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )

    def footer(self) -> None:
        """Add footer to each page."""
        self.set_y(-15)
        if self.has_unicode_font:
            self.set_font("DejaVu", "", 8)
        else:
            self.set_font("Courier", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Generated: 2025", 0, align="C")

    def clean_text(self, text: str) -> str:
        """Clean text to ensure it's compatible with fonts."""
        if not text:
            return ""
        # Replace special Unicode characters that might cause issues
        replacements = {
            "\u2713": "[OK]",  # checkmark
            "\u2717": "[X]",  # cross
            "\u2192": "->",  # arrow right
            "\u2190": "<-",  # arrow left
            "\u2022": "*",  # bullet
            "\u2014": "--",  # em dash
            "\u2013": "-",  # en dash
            "\u25cf": "*",  # black circle
            "\u25cb": "o",  # white circle
            "\u2550": "=",  # box drawing
            "\u2551": "|",  # box drawing
            "\u2554": "+",  # box drawing
            "\u2557": "+",  # box drawing
            "\u255a": "+",  # box drawing
            "\u255d": "+",  # box drawing
            "\u2500": "-",  # box drawing horizontal
            "\u2502": "|",  # box drawing vertical
            "\u256c": "+",  # box drawing cross
            "\u2555": "+",  # box drawing
            "\u2556": "+",  # box drawing
            "\u255c": "+",  # box drawing
            "\u255b": "+",  # box drawing
            "\u255e": "+",  # box drawing
            "\u255f": "+",  # box drawing
            "\u2560": "+",  # box drawing
            "\u2561": "+",  # box drawing
            "\u2562": "+",  # box drawing
            "\u2563": "+",  # box drawing
            "\u2564": "+",  # box drawing
            "\u2565": "+",  # box drawing
            "\u2566": "+",  # box drawing
            "\u2567": "+",  # box drawing
            "\u2568": "+",  # box drawing
            "\u2569": "+",  # box drawing
            "\u256a": "+",  # box drawing
            "\u256b": "+",  # box drawing
            "\u29c9": "[]",  # box drawing
            "\u26a1": "[!]",  # lightning
            "\u274c": "[X]",  # cross mark
            "\u2705": "[OK]",  # check mark button
            "\ud83c\udf89": "[celebrate]",  # party popper
            "\ud83c\udf8a": "[celebrate]",  # confetti ball
            "\ud83c\udf88": "[balloon]",  # balloon
            "\ud83d\ude80": "[rocket]",  # rocket
            "\ud83c\udfaf": "[target]",  # target
            "\ud83d\udcf1": "[phone]",  # mobile phone
            "\ud83d\udcda": "[books]",  # books
            "\ud83d\udcdd": "[memo]",  # memo
            "\ud83d\udcbe": "[floppy]",  # floppy disk
            "\ud83d\udcc1": "[folder]",  # folder
            "\ud83d\udd12": "[lock]",  # lock
            "\ud83d\udd13": "[unlock]",  # unlock
            "\ud83c\udfb2": "[die]",  # game die
            "\u2b50": "[*]",  # star
            "\ud83d\udc9a": "[heart]",  # green heart
            "\ud83d\udc99": "[heart]",  # blue heart
            "\ud83d\udc9c": "[heart]",  # purple heart
            "\ud83d\udc9b": "[heart]",  # yellow heart
            "\u2764": "[heart]",  # heart
            "\u25b6": ">",  # play button
            "\u25b8": ">",  # small play
            "\u25aa": ".",  # small square
            "\u25fc": "#",  # black square
            "\u25aa\ufe0f": ".",  # small square
            "\ud83d\udce4": "[mail]",  # outbox
            "\ud83d\udce5": "[mail]",  # inbox
            "\ud83d\udccb": "[clipboard]",  # clipboard
            "\ud83d\udcbc": "[briefcase]",  # briefcase
            "\ud83d\udcca": "[chart]",  # chart
            "\ud83d\udcc8": "[chart]",  # chart up
            "\ud83d\udcc9": "[chart]",  # chart down
            "\u270f": "[pencil]",  # pencil
            "\u2712": "[pencil]",  # pencil
            "\ud83d\udd8a": "[pencil]",  # pencil
            "\ud83d\udd8b": "[pen]",  # pen
            "\ud83d\udccb": "[clipboard]",  # clipboard
            "\ud83d\udcc4": "[page]",  # page
            "\ud83d\udcc3": "[page]",  # page
            "\ud83d\udcdd": "[memo]",  # memo
            "\ud83d\udcd6": "[book]",  # open book
            "\ud83d\udcda": "[books]",  # books
            "\ud83d\udcd3": "[notebook]",  # notebook
            "\ud83d\udcd2": "[book]",  # orange book
            "\ud83d\udcd5": "[book]",  # closed book
            "\ud83d\udcd9": "[bookmark]",  # bookmark
            "\ud83d\udcd1": "[bookmark]",  # bookmark tabs
            "\ud83d\udccc": "[pin]",  # pushpin
            "\ud83d\udccd": "[pin]",  # round pushpin
            "\ud83d\udce6": "[package]",  # package
            "\ud83d\udce7": "[mail]",  # e-mail
            "\ud83d\udce8": "[mail]",  # incoming envelope
            "\ud83d\udce9": "[mail]",  # envelope with arrow
            "\ud83d\udcea": "[mail]",  # closed mailbox
            "\ud83d\udceb": "[mail]",  # open mailbox
            "\ud83d\udcec": "[mail]",  # mailbox
            "\ud83d\udced": "[mail]",  # mailbox with flag
            "\ud83d\udcee": "[post]",  # postbox
            "\ud83d\udcef": "[horn]",  # postal horn
            "\ud83d\udcf0": "[news]",  # newspaper
            "\ud83d\udcf1": "[phone]",  # mobile phone
            "\ud83d\udcf2": "[phone]",  # mobile phone with arrow
            "\ud83d\udcf3": "[phone]",  # vibration mode
            "\ud83d\udcf4": "[phone]",  # mobile phone off
            "\ud83d\udcf7": "[camera]",  # camera
            "\ud83d\udcf9": "[video]",  # video camera
            "\ud83d\udcfa": "[tv]",  # television
            "\ud83d\udcfb": "[radio]",  # radio
            "\ud83d\udcfc": "[video]",  # video cassette
            "\ud83d\udd0a": "[sound]",  # speaker high
            "\ud83d\udd0b": "[battery]",  # battery
            "\ud83d\udd0c": "[plug]",  # electric plug
            "\ud83d\udd0d": "[search]",  # left magnifier
            "\ud83d\udd0e": "[search]",  # right magnifier
            "\ud83d\udd0f": "[lock]",  # lock with ink pen
            "\ud83d\udd10": "[lock]",  # closed lock with key
            "\ud83d\udd11": "[key]",  # key
            "\ud83d\udd12": "[lock]",  # lock
            "\ud83d\udd13": "[unlock]",  # open lock
            "\ud83d\udd14": "[bell]",  # bell
            "\ud83d\udd15": "[bell]",  # bell with slash
            "\ud83d\udd16": "[bookmark]",  # bookmark
            "\ud83d\udd17": "[link]",  # link symbol
            "\ud83d\udd18": "[radio]",  # radio button
            "\ud83d\udd19": "[back]",  # back arrow
            "\ud83d\udd1a": "[end]",  # end arrow
            "\ud83d\udd1b": "[on]",  # on arrow
            "\ud83d\udd1c": "[soon]",  # soon arrow
            "\ud83d\udd1d": "[top]",  # top arrow
            "\ud83d\udd1e": "[no]",  # no entry
            "\ud83d\udd1f": "[keycap]",  # keycap ten
            "\ud83d\udd20": "[keycap]",  # keycap one
            "\ud83d\udd21": "[keycap]",  # keycap two
            "\ud83d\udd22": "[keycap]",  # keycap three
            "\ud83d\udd23": "[keycap]",  # keycap four
            "\ud83d\udd24": "[keycap]",  # keycap five
            "\ud83d\udd25": "[fire]",  # fire
            "\ud83d\udd26": "[flash]",  # flashlight
            "\ud83d\udd27": "[wrench]",  # wrench
            "\ud83d\udd28": "[hammer]",  # hammer
            "\ud83d\udd29": "[pick]",  # pick
            "\ud83d\udd2a": "[hammer]",  # hammer and pick
            "\ud83d\udd2b": "[gun]",  # pistol
            "\ud83d\udd2c": "[microscope]",  # microscope
            "\ud83d\udd2d": "[telescope]",  # telescope
            "\ud83d\udd2e": "[crystal]",  # crystal ball
            "\ud83d\udd2f": "[diya]",  # diya lamp
            "\ud83d\udd30": "[bow]",  # bow and arrow
            "\ud83d\udd31": "[trident]",  # trident emblem
            "\ud83d\udd32": "[arrow]",  # black arrow up
            "\ud83d\udd33": "[arrow]",  # black arrow down
            "\ud83d\udd34": "[circle]",  # red circle
            "\ud83d\udd35": "[circle]",  # blue circle
        }

        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        # Remove any remaining non-ASCII characters except common ones
        if not self.has_unicode_font:
            # Only keep printable ASCII
            text = "".join(
                char if ord(char) < 128 and char.isprintable() or char in "\n\r\t" else "?"
                for char in text
            )

        return text

    def add_title_page(self, title: str, subtitle: str) -> None:
        """Add title page."""
        self.add_page()
        if self.has_unicode_font:
            self.set_font("DejaVu", "B", 24)
        else:
            self.set_font("Helvetica", "B", 24)
        self.set_text_color(0, 0, 0)
        self.ln(80)
        self.cell(0, 20, title, 0, new_x="LMARGIN", new_y="NEXT", align="C")
        if self.has_unicode_font:
            self.set_font("DejaVu", "", 14)
        else:
            self.set_font("Helvetica", "", 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, subtitle, 0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(20)
        if self.has_unicode_font:
            self.set_font("DejaVuMono", "", 10)
        else:
            self.set_font("Courier", "", 10)
        self.cell(
            0, 10, "Generated from OpenLaoKe Project", 0, new_x="LMARGIN", new_y="NEXT", align="C"
        )

    def add_file_header(self, filepath: str) -> None:
        """Add file header."""
        self.add_page()
        if self.has_unicode_font:
            self.set_font("DejaVu", "B", 12)
        else:
            self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 100, 200)
        clean_path = self.clean_text(filepath)
        self.cell(0, 10, f"File: {clean_path}", 0, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 100, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def add_code_content(self, content: str) -> None:
        """Add code content with proper formatting."""
        if self.has_unicode_font:
            self.set_font("DejaVuMono", "", 8)
        else:
            self.set_font("Courier", "", 8)
        self.set_text_color(0, 0, 0)

        # Clean the content
        content = self.clean_text(content)
        lines = content.split("\n")

        for line in lines:
            # Handle long lines - wrap at 95 characters
            while len(line) > 95:
                self.cell(0, 4, line[:95], 0, new_x="LMARGIN", new_y="NEXT")
                line = "    " + line[95:]
            if line:
                self.cell(0, 4, line, 0, new_x="LMARGIN", new_y="NEXT")

    def add_markdown_content(self, content: str) -> None:
        """Add markdown content with basic formatting."""
        if self.has_unicode_font:
            self.set_font("DejaVu", "", 10)
        else:
            self.set_font("Helvetica", "", 10)
        self.set_text_color(0, 0, 0)

        # Clean the content
        content = self.clean_text(content)
        lines = content.split("\n")

        for line in lines:
            # Handle headers
            if line.startswith("# "):
                if self.has_unicode_font:
                    self.set_font("DejaVu", "B", 16)
                else:
                    self.set_font("Helvetica", "B", 16)
                self.ln(5)
                self.cell(0, 8, line[2:], 0, new_x="LMARGIN", new_y="NEXT")
                if self.has_unicode_font:
                    self.set_font("DejaVu", "", 10)
                else:
                    self.set_font("Helvetica", "", 10)
            elif line.startswith("## "):
                if self.has_unicode_font:
                    self.set_font("DejaVu", "B", 14)
                else:
                    self.set_font("Helvetica", "B", 14)
                self.ln(3)
                self.cell(0, 7, line[3:], 0, new_x="LMARGIN", new_y="NEXT")
                if self.has_unicode_font:
                    self.set_font("DejaVu", "", 10)
                else:
                    self.set_font("Helvetica", "", 10)
            elif line.startswith("### "):
                if self.has_unicode_font:
                    self.set_font("DejaVu", "B", 12)
                else:
                    self.set_font("Helvetica", "B", 12)
                self.ln(2)
                self.cell(0, 6, line[4:], 0, new_x="LMARGIN", new_y="NEXT")
                if self.has_unicode_font:
                    self.set_font("DejaVu", "", 10)
                else:
                    self.set_font("Helvetica", "", 10)
            elif line.startswith("**") and line.endswith("**"):
                if self.has_unicode_font:
                    self.set_font("DejaVu", "B", 10)
                else:
                    self.set_font("Helvetica", "B", 10)
                self.cell(0, 5, line.strip("*"), 0, new_x="LMARGIN", new_y="NEXT")
                if self.has_unicode_font:
                    self.set_font("DejaVu", "", 10)
                else:
                    self.set_font("Helvetica", "", 10)
            elif line.strip() == "":
                self.ln(3)
            else:
                # Regular text with wrapping
                self.multi_cell(0, 5, line)


def collect_python_files(root_dir: str) -> list[str]:
    """Collect all Python files from project."""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden and cache directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ["__pycache__", "node_modules", "venv", ".git", "pdf_output"]
        ]
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                python_files.append(filepath)
    return sorted(python_files)


def collect_documentation_files(root_dir: str) -> list[str]:
    """Collect all documentation files from project."""
    doc_files = []
    priority_files = [
        "README.md",
        "README_CN.md",
        "汇报.md",
        "AGENTS.md",
    ]

    # Add priority files first
    for priority in priority_files:
        priority_path = os.path.join(root_dir, priority)
        if os.path.exists(priority_path):
            doc_files.append(priority_path)

    # Then add other docs
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d
            not in ["__pycache__", ".git", ".pytest_cache", "node_modules", "venv", "pdf_output"]
        ]
        for file in files:
            if file.endswith(".md") or file.endswith(".txt") or file.endswith(".rst"):
                filepath = os.path.join(root, file)
                if filepath not in doc_files and not any(
                    x in filepath for x in [".egg-info", "__pycache__"]
                ):
                    doc_files.append(filepath)

    return doc_files


def generate_code_pdf(root_dir: str, output_path: str) -> None:
    """Generate PDF from Python code files."""
    pdf = PDFGenerator()
    pdf.add_title_page("OpenLaoKe Project", "Complete Source Code Documentation")

    python_files = collect_python_files(root_dir)
    total_files = len(python_files)
    print(f"Found {total_files} Python files")

    # Add table of contents (limited to first 100)
    pdf.add_page()
    if pdf.has_unicode_font:
        pdf.set_font("DejaVu", "B", 14)
    else:
        pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Table of Contents", 0, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    if pdf.has_unicode_font:
        pdf.set_font("DejaVuMono", "", 9)
    else:
        pdf.set_font("Courier", "", 9)

    for i, filepath in enumerate(python_files[:100], 1):
        rel_path = os.path.relpath(filepath, root_dir)
        clean_path = pdf.clean_text(rel_path)
        pdf.cell(0, 5, f"{i}. {clean_path}", 0, new_x="LMARGIN", new_y="NEXT")

    # Add files content
    processed = 0
    errors = 0
    for i, filepath in enumerate(python_files):
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if not content.strip():
                continue

            rel_path = os.path.relpath(filepath, root_dir)
            clean_path = pdf.clean_text(rel_path)
            pdf.add_file_header(f"[{i + 1}/{total_files}] {clean_path}")
            pdf.add_code_content(content)
            processed += 1

            if (i + 1) % 50 == 0:
                print(f"Processed {i + 1}/{total_files} files...")

        except Exception as e:
            errors += 1
            print(f"Error processing {filepath}: {e}")
            continue

    pdf.output(output_path)
    print(f"\nCode PDF generated: {output_path}")
    print(f"Files processed: {processed}/{total_files}")
    print(f"Errors: {errors}")


def generate_docs_pdf(root_dir: str, output_path: str) -> None:
    """Generate PDF from documentation files."""
    pdf = PDFGenerator()
    pdf.add_title_page("OpenLaoKe Project", "Documentation Collection")

    doc_files = collect_documentation_files(root_dir)
    total_files = len(doc_files)
    print(f"Found {total_files} documentation files")

    # Add files content
    processed = 0
    errors = 0
    for i, filepath in enumerate(doc_files):
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if not content.strip():
                continue

            rel_path = os.path.relpath(filepath, root_dir)
            clean_path = pdf.clean_text(rel_path)
            pdf.add_file_header(f"[{i + 1}/{total_files}] {clean_path}")
            pdf.add_markdown_content(content)
            processed += 1

            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{total_files} files...")

        except Exception as e:
            errors += 1
            print(f"Error processing {filepath}: {e}")
            continue

    pdf.output(output_path)
    print(f"\nDocumentation PDF generated: {output_path}")
    print(f"Files processed: {processed}/{total_files}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    root_dir = "/Users/fred/Documents/GitHub/cycleuser/OpenLaoKe"
    output_dir = os.path.join(root_dir, "pdf_output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("PDF Generation Script for OpenLaoKe Project")
    print("=" * 60)

    print("\n1. Generating Code PDF...")
    print("-" * 60)
    generate_code_pdf(root_dir, os.path.join(output_dir, "OpenLaoKe_Source_Code.pdf"))

    print("\n2. Generating Documentation PDF...")
    print("-" * 60)
    generate_docs_pdf(root_dir, os.path.join(output_dir, "OpenLaoKe_Documentation.pdf"))

    print("\n" + "=" * 60)
    print("Done! PDF files saved to:", output_dir)
    print("=" * 60)
