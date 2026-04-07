"""
OpenLaoKe 自动补全系统
参考 OpenCode 的实现方式

特性：
1. `/` 触发技能/命令补全
2. `@` 触发文件/代理补全
3. 模糊搜索
4. 实时显示补全菜单
5. Tab/Enter 选择，Esc 关闭
"""

from __future__ import annotations

import os
import readline
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from openlaoke.commands.registry import get_all_commands
from openlaoke.core.skill_system import list_available_skills, load_skill


@dataclass
class AutocompleteOption:
    """补全选项"""

    display: str
    value: str | None = None
    description: str = ""
    is_skill: bool = False
    is_command: bool = False
    is_file: bool = False
    is_directory: bool = False
    on_select: Callable | None = None


class AutocompleteState:
    """补全状态"""

    def __init__(self):
        self.visible = False
        self.mode = ""  # "/" 或 "@"
        self.options: list[AutocompleteOption] = []
        self.selected = 0
        self.search_text = ""
        self.trigger_index = 0

    def reset(self):
        self.visible = False
        self.mode = ""
        self.options = []
        self.selected = 0
        self.search_text = ""
        self.trigger_index = 0


class AutocompleteManager:
    """自动补全管理器"""

    def __init__(self):
        self.state = AutocompleteState()
        self._commands_cache: list[AutocompleteOption] | None = None
        self._skills_cache: list[AutocompleteOption] | None = None
        self._cwd = os.getcwd()

    def _get_commands(self) -> list[AutocompleteOption]:
        """获取所有命令选项"""
        if self._commands_cache is not None:
            return self._commands_cache

        options = []
        seen = set()

        for cmd in get_all_commands():
            if cmd.hidden:
                continue

            cmd_name = cmd.name
            if cmd_name in seen:
                continue
            seen.add(cmd_name)

            options.append(
                AutocompleteOption(
                    display=f"/{cmd_name}",
                    value=cmd_name,
                    description=cmd.description,
                    is_command=True,
                )
            )

            for alias in cmd.aliases:
                if alias not in seen:
                    seen.add(alias)
                    options.append(
                        AutocompleteOption(
                            display=f"/{alias}",
                            value=alias,
                            description=f"Alias for /{cmd_name}",
                            is_command=True,
                        )
                    )

        self._commands_cache = sorted(options, key=lambda x: x.display)
        return self._commands_cache

    def _get_skills(self) -> list[AutocompleteOption]:
        """获取所有技能选项"""
        if self._skills_cache is not None:
            return self._skills_cache

        options = []

        for skill_name in list_available_skills():
            skill = load_skill(skill_name)
            if skill:
                desc = ""
                if skill.description:
                    # 截取描述前80个字符
                    desc = skill.description[:80]
                    if len(skill.description) > 80:
                        desc += "..."

                options.append(
                    AutocompleteOption(
                        display=f"/{skill_name}",
                        value=skill_name,
                        description=desc,
                        is_skill=True,
                    )
                )

        self._skills_cache = sorted(options, key=lambda x: x.display)
        return self._skills_cache

    def _get_slash_options(self) -> list[AutocompleteOption]:
        """获取所有 / 开头的选项（命令 + 技能）"""
        commands = self._get_commands()
        skills = self._get_skills()

        # 合并并去重
        all_options = {}
        for opt in commands + skills:
            if opt.display not in all_options:
                all_options[opt.display] = opt

        return sorted(all_options.values(), key=lambda x: x.display)

    def _fuzzy_match(
        self, query: str, options: list[AutocompleteOption]
    ) -> list[AutocompleteOption]:
        """模糊匹配"""
        if not query:
            return options

        query_lower = query.lower()
        scored = []

        for opt in options:
            display_lower = opt.display.lower()
            value_lower = (opt.value or "").lower()
            desc_lower = opt.description.lower()

            score = 0

            # 完全匹配开头得分最高
            if display_lower.startswith("/" + query_lower):
                score = 100
            # 包含查询字符串
            elif query_lower in display_lower:
                score = 80
            elif query_lower in value_lower:
                score = 60
            # 描述中包含
            elif query_lower in desc_lower:
                score = 40
            # 模糊匹配
            elif self._fuzzy_contains(query_lower, display_lower):
                score = 20

            if score > 0:
                scored.append((score, opt))

        # 按分数排序
        scored.sort(key=lambda x: (-x[0], x[1].display))
        return [opt for _, opt in scored[:10]]

    def _fuzzy_contains(self, query: str, text: str) -> bool:
        """模糊包含检查"""
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                query_idx += 1
        return query_idx == len(query)

    def start_completion(self, mode: str, cursor_pos: int, text: str):
        """开始补全"""
        self.state.visible = True
        self.state.mode = mode
        self.state.trigger_index = cursor_pos - 1  # 触发字符的位置

        # 获取搜索文本
        if mode == "/":
            # 提取 / 后面的文本
            search_text = text[1:cursor_pos]
            all_options = self._get_slash_options()
        else:  # @
            # 提取 @ 后面的文本
            at_pos = text.rfind("@", 0, cursor_pos)
            search_text = text[at_pos + 1 : cursor_pos]
            all_options = self._get_file_options(search_text)

        self.state.search_text = search_text
        self.state.options = self._fuzzy_match(search_text, all_options)
        self.state.selected = 0

    def update_search(self, cursor_pos: int, text: str):
        """更新搜索"""
        if not self.state.visible:
            return

        # 检查是否应该关闭补全
        trigger_pos = self.state.trigger_index

        # 光标移动到触发字符之前
        if cursor_pos <= trigger_pos:
            self.state.reset()
            return

        # 检查是否有空格（表示命令/技能名结束）
        text_between = text[trigger_pos:cursor_pos]
        if " " in text_between and self.state.mode == "/" and len(text_between.strip().split()) > 1:
            # 对于 / 命令，如果有空格表示命令结束，关闭补全
            self.state.reset()
            return

        # 更新搜索文本
        search_text = text[trigger_pos + 1 : cursor_pos]
        self.state.search_text = search_text

        # 重新过滤选项
        if self.state.mode == "/":
            all_options = self._get_slash_options()
        else:
            all_options = self._get_file_options(search_text)

        self.state.options = self._fuzzy_match(search_text, all_options)
        self.state.selected = 0

    def _get_file_options(self, query: str) -> list[AutocompleteOption]:
        """获取文件选项"""
        options = []

        try:
            cwd = Path(self._cwd)

            # 分离目录和文件名前缀
            if "/" in query:
                dir_part = query.rsplit("/", 1)[0]
                file_prefix = query.rsplit("/", 1)[1] if "/" in query else query
                search_dir = cwd / dir_part if dir_part else cwd
            else:
                search_dir = cwd
                file_prefix = query

            if not search_dir.exists():
                return options

            for item in sorted(search_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                if item.name.startswith("."):
                    continue

                if file_prefix and not item.name.lower().startswith(file_prefix.lower()):
                    continue

                is_dir = item.is_dir()
                display_name = item.name + ("/" if is_dir else "")

                options.append(
                    AutocompleteOption(
                        display=display_name,
                        value=display_name,
                        description=f"{'Directory' if is_dir else 'File'}",
                        is_file=not is_dir,
                        is_directory=is_dir,
                    )
                )
        except Exception:
            pass

        return options[:10]

    def move_selection(self, direction: int):
        """移动选择"""
        if not self.state.visible or not self.state.options:
            return

        self.state.selected += direction

        if self.state.selected < 0:
            self.state.selected = len(self.state.options) - 1
        elif self.state.selected >= len(self.state.options):
            self.state.selected = 0

    def get_selected(self) -> AutocompleteOption | None:
        """获取当前选中项"""
        if not self.state.visible or not self.state.options:
            return None

        if 0 <= self.state.selected < len(self.state.options):
            return self.state.options[self.state.selected]

        return None

    def get_completion_text(self) -> str | None:
        """获取补全文本"""
        selected = self.get_selected()
        if not selected:
            return None

        if self.state.mode == "/":
            # 对于斜杠命令，返回完整的命令名
            return selected.value or selected.display.lstrip("/")
        else:
            # 对于文件，返回文件名
            return selected.value or selected.display

    def get_display_lines(self, max_width: int = 60) -> list[str]:
        """获取显示行"""
        if not self.state.visible or not self.state.options:
            return []

        lines = []
        for i, opt in enumerate(self.state.options):
            prefix = "→ " if i == self.state.selected else "  "

            # 截断显示文本
            display = opt.display
            if len(display) > max_width - 20:
                display = display[: max_width - 23] + "..."

            # 添加描述
            if opt.description:
                desc = opt.description
                remaining = max_width - len(display) - 4
                if remaining > 10:
                    if len(desc) > remaining:
                        desc = desc[: remaining - 3] + "..."
                    line = f"{prefix}{display}  [dim]{desc}[/dim]"
                else:
                    line = f"{prefix}{display}"
            else:
                line = f"{prefix}{display}"

            lines.append(line)

        return lines


# 全局实例
_manager: AutocompleteManager | None = None


def get_autocomplete_manager() -> AutocompleteManager:
    """获取全局自动补全管理器"""
    global _manager
    if _manager is None:
        _manager = AutocompleteManager()
    return _manager


def setup_readline_completion():
    """设置 readline 的 Tab 补全"""
    manager = get_autocomplete_manager()

    def complete(text: str, state: int):
        if state == 0:
            # 第一次调用，生成补全列表
            manager.state.reset()

            # 检查是否以 / 开头
            if text.startswith("/"):
                manager.start_completion("/", len(text), text)

        # 返回补全项
        if manager.state.visible and manager.state.options and state < len(manager.state.options):
            opt = manager.state.options[state]
            return opt.display

        return None

    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n")

    return manager
