"""
REPL with interactive autocomplete

模仿 OpenCode 的补全行为：
- 输入 / 触发技能/命令补全
- 输入 @ 触发文件补全
- Tab 循环选择
- Enter 确认选择
- Esc 取消
- 实时显示补全菜单
"""

from __future__ import annotations

import os
import sys
import termios
import tty

from rich.console import Console

from openlaoke.core.autocomplete import get_autocomplete_manager


class InteractiveInput:
    """交互式输入，支持实时补全"""

    def __init__(self, console: Console):
        self.console = console
        self.manager = get_autocomplete_manager()
        self._buffer = ""
        self._cursor = 0
        self._prompt = ""
        self._history: list[str] = []
        self._history_index = -1

    def read_line(self, prompt: str = "") -> str:
        """读取一行输入，支持实时补全"""
        self._buffer = ""
        self._cursor = 0
        self._prompt = prompt
        self.manager.state.reset()

        # 打印提示符
        self.console.print(prompt, end="")

        # 设置终端为原始模式
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)

            while True:
                ch = sys.stdin.read(1)

                # 处理特殊按键
                if ch == "\x1b":  # ESC 序列
                    # 读取接下来的字符
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        ch3 = sys.stdin.read(1)
                        if ch3 == "A":  # 上箭头
                            self._history_up()
                        elif ch3 == "B":  # 下箭头
                            self._history_down()
                        elif ch3 == "C":  # 右箭头
                            self._cursor_right()
                        elif ch3 == "D":  # 左箭头
                            self._cursor_left()
                        elif ch3 == "3":  # Delete
                            sys.stdin.read(1)  # 读取 ~
                            self._delete()
                    else:
                        # ESC 键 - 关闭补全菜单
                        if self.manager.state.visible:
                            self.manager.state.reset()
                            self._refresh_line()

                elif ch == "\r" or ch == "\n":  # Enter
                    if self.manager.state.visible:
                        # 选择当前补全项
                        self._select_completion()
                    else:
                        # 结束输入
                        self.console.print()
                        break

                elif ch == "\t":  # Tab
                    self._handle_tab()

                elif ch == "\x7f" or ch == "\x08":  # Backspace
                    self._backspace()

                elif ch == "\x03":  # Ctrl+C
                    self.console.print("^C")
                    raise KeyboardInterrupt()

                elif ch == "\x04":  # Ctrl+D
                    raise EOFError()

                elif ch.isprintable():
                    self._insert_char(ch)

                # 更新补全
                self._update_completion()

                # 刷新显示
                self._refresh_line()

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        # 添加到历史
        if self._buffer.strip():
            self._history.append(self._buffer)

        return self._buffer

    def _refresh_line(self):
        """刷新当前行显示"""
        # 清除当前行
        self.console.print("\r\033[K", end="")

        # 打印提示符和缓冲区
        self.console.print(f"{self._prompt}{self._buffer}", end="")

        # 移动光标到正确位置
        if self._cursor < len(self._buffer):
            # 计算需要移动的位置
            move_left = len(self._buffer) - self._cursor
            self.console.print(f"\033[{move_left}D", end="")

        # 显示补全菜单
        if self.manager.state.visible and self.manager.state.options:
            self._show_completion_menu()

        sys.stdout.flush()

    def _show_completion_menu(self):
        """显示补全菜单"""
        self.console.print("\n\033[K", end="")

        options = self.manager.state.options
        selected = self.manager.state.selected

        # 显示最多10个选项
        for i, opt in enumerate(options[:10]):
            if i == selected:
                line = f"  → [bold cyan]{opt.display}[/bold cyan]"
            else:
                line = f"    {opt.display}"

            if opt.description:
                line += f" [dim]- {opt.description[:40]}[/dim]"

            self.console.print(f"\033[K{line}")

        # 移动光标回输入行
        lines_up = min(len(options), 10) + 1
        self.console.print(f"\033[{lines_up}A\r", end="")

        # 重新打印输入行
        self.console.print(f"{self._prompt}{self._buffer}", end="")

        if self._cursor < len(self._buffer):
            move_left = len(self._buffer) - self._cursor
            self.console.print(f"\033[{move_left}D", end="")

    def _insert_char(self, ch: str):
        """插入字符"""
        self._buffer = self._buffer[: self._cursor] + ch + self._buffer[self._cursor :]
        self._cursor += 1

    def _backspace(self):
        """删除前一个字符"""
        if self._cursor > 0:
            self._buffer = self._buffer[: self._cursor - 1] + self._buffer[self._cursor :]
            self._cursor -= 1

    def _delete(self):
        """删除当前字符"""
        if self._cursor < len(self._buffer):
            self._buffer = self._buffer[: self._cursor] + self._buffer[self._cursor + 1 :]

    def _cursor_left(self):
        """光标左移"""
        if self._cursor > 0:
            self._cursor -= 1

    def _cursor_right(self):
        """光标右移"""
        if self._cursor < len(self._buffer):
            self._cursor += 1

    def _handle_tab(self):
        """处理 Tab 键"""
        if self.manager.state.visible:
            # 循环选择下一个
            self.manager.move_selection(1)
        elif self._buffer.startswith("/"):
            # 开始补全
            self.manager.start_completion("/", self._cursor, self._buffer)

    def _update_completion(self):
        """更新补全状态"""
        if self.manager.state.visible:
            self.manager.update_search(self._cursor, self._buffer)
        elif self._buffer.startswith("/") and " " not in self._buffer:
            # 自动触发补全
            self.manager.start_completion("/", self._cursor, self._buffer)

    def _select_completion(self):
        """选择补全项"""
        text = self.manager.get_completion_text()
        if text:
            # 替换整个命令
            self._buffer = "/" + text + " "
            self._cursor = len(self._buffer)

        self.manager.state.reset()

    def _history_up(self):
        """历史记录上翻"""
        if self._history and self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._buffer = self._history[-(self._history_index + 1)]
            self._cursor = len(self._buffer)

    def _history_down(self):
        """历史记录下翻"""
        if self._history_index > 0:
            self._history_index -= 1
            self._buffer = self._history[-(self._history_index + 1)]
            self._cursor = len(self._buffer)
        elif self._history_index == 0:
            self._history_index = -1
            self._buffer = ""
            self._cursor = 0


def simple_input_with_completion(prompt: str, console: Console) -> str:
    """简单的带补全的输入（使用 readline）"""
    from openlaoke.core.autocomplete import setup_readline_completion

    manager = setup_readline_completion()

    # 设置当前工作目录
    manager._cwd = os.getcwd()

    try:
        result = input(prompt)
        return result
    except EOFError:
        return ""
