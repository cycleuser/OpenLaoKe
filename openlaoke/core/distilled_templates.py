"""Comprehensive distilled prompt templates for local small models.

Covers 100+ templates across 50+ categories with multi-language triggers (CN/EN/JP/KR/FR/DE/ES/RU).
Each template contains high-quality Q&A examples for few-shot injection.
Designed so that ANY small model with tool calling can follow guidelines to complete tasks.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

DISTILLED_TEMPLATES_PATH = os.path.expanduser("~/.openlaoke/distilled_templates.json")


@dataclass
class DistilledExample:
    """A single Q&A example for a template."""

    question: str
    answer: str


@dataclass
class DistilledTemplate:
    """A template with triggers and few-shot examples."""

    category: str
    triggers: list[str]
    examples: list[DistilledExample]
    max_examples: int = 2


@dataclass
class DistilledTemplateManager:
    """Manages distilled prompt templates for local models."""

    templates: dict[str, DistilledTemplate] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.templates:
            self._load_defaults()
        self._load_user_templates()

    def _load_defaults(self) -> None:
        defaults = _get_default_templates()
        for tid, tdata in defaults.items():
            examples = [DistilledExample(question=e["q"], answer=e["a"]) for e in tdata["examples"]]
            self.templates[tid] = DistilledTemplate(
                category=tdata["category"],
                triggers=tdata["triggers"],
                examples=examples,
                max_examples=tdata.get("max_examples", 2),
            )

    def _load_user_templates(self) -> None:
        if not os.path.exists(DISTILLED_TEMPLATES_PATH):
            return
        try:
            with open(DISTILLED_TEMPLATES_PATH) as f:
                data = json.load(f)
            for tid, tdata in data.get("templates", {}).items():
                if tid in self.templates:
                    continue
                examples = [
                    DistilledExample(question=e["q"], answer=e["a"])
                    for e in tdata.get("examples", [])
                ]
                self.templates[tid] = DistilledTemplate(
                    category=tdata.get("category", "custom"),
                    triggers=tdata.get("triggers", []),
                    examples=examples,
                    max_examples=tdata.get("max_examples", 2),
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def save_user_templates(self) -> None:
        os.makedirs(os.path.dirname(DISTILLED_TEMPLATES_PATH), exist_ok=True)
        data: dict[str, dict[str, dict[str, Any]]] = {"templates": {}}
        for tid, tmpl in self.templates.items():
            if tid.startswith("user_"):
                data["templates"][tid] = {
                    "category": tmpl.category,
                    "triggers": tmpl.triggers,
                    "examples": [{"q": e.question, "a": e.answer} for e in tmpl.examples],
                    "max_examples": tmpl.max_examples,
                }
        with open(DISTILLED_TEMPLATES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def match_templates(self, user_input: str) -> list[DistilledTemplate]:
        """Find templates matching the user input using semantic analysis."""
        text = user_input.lower()
        words = set(text.split())
        matches = []
        matched_ids = set()

        # Phase 1: Exact trigger match (score=100)
        for tid, tmpl in self.templates.items():
            for trigger in tmpl.triggers:
                if trigger.lower() in text:
                    if tid not in matched_ids:
                        matches.append((100, tid, tmpl))
                        matched_ids.add(tid)
                    break

        # Phase 2: Word-level partial match (score=10-90)
        if len(matches) < 3:
            for tid, tmpl in self.templates.items():
                if tid in matched_ids:
                    continue
                score = 0
                for trigger in tmpl.triggers:
                    trigger_words = set(trigger.lower().split())
                    overlap = words & trigger_words
                    if overlap:
                        score += len(overlap) * 10
                if score > 0:
                    matches.append((score, tid, tmpl))
                    matched_ids.add(tid)

        # Phase 3: Category keyword fallback (score=5)
        if len(matches) < 3:
            cat_kw = {
                "algorithm": [
                    "算法",
                    "复杂度",
                    "时间复杂度",
                    "空间复杂度",
                    "优化",
                    "性能",
                    "アルゴリズム",
                    "알고리즘",
                    "algorithme",
                    "algorithmus",
                    "algoritmo",
                    "алгоритм",
                ],
                "file_operations": [
                    "文件",
                    "路径",
                    "目录",
                    "folder",
                    "path",
                    "directory",
                    "ファイル",
                    "파일",
                    "fichier",
                    "datei",
                    "archivo",
                    "файл",
                ],
                "text_processing": [
                    "文本",
                    "字符串",
                    "string",
                    "split",
                    "join",
                    "替换",
                    "正则",
                    "テキスト",
                    "텍스트",
                    "texte",
                    "text",
                    "texto",
                    "текст",
                ],
                "git_operations": [
                    "版本",
                    "回滚",
                    "revert",
                    "stash",
                    "tag",
                    "rebase",
                    "冲突",
                    "git",
                    "バージョン",
                    "버전",
                    "version",
                    "버전",
                ],
                "network": [
                    "socket",
                    "tcp",
                    "udp",
                    "websocket",
                    "长连接",
                    "网络",
                    "ネットワーク",
                    "네트워크",
                    "réseau",
                    "netzwerk",
                    "red",
                    "сеть",
                ],
                "database": [
                    "数据库",
                    "表",
                    "table",
                    "orm",
                    "sqlalchemy",
                    "mongo",
                    "redis",
                    "データベース",
                    "데이터베이스",
                    "base de données",
                    "datenbank",
                    "base de datos",
                    "база данных",
                ],
                "testing": [
                    "测试",
                    "mock",
                    "fixture",
                    "覆盖率",
                    "coverage",
                    "pytest",
                    "テスト",
                    "테스트",
                    "test",
                    "тест",
                ],
                "error_handling": [
                    "排查",
                    "定位",
                    "traceback",
                    "堆栈",
                    "异常处理",
                    "エラー",
                    "에러",
                    "erreur",
                    "fehler",
                    "error",
                    "ошибка",
                ],
                "oop": [
                    "设计模式",
                    "pattern",
                    "单例",
                    "工厂",
                    "观察者",
                    "策略",
                    "类",
                    "クラス",
                    "클래스",
                    "classe",
                    "klasse",
                    "clase",
                    "класс",
                ],
                "python_basics": [
                    "基础",
                    "入门",
                    "语法",
                    "syntax",
                    "builtin",
                    "内置",
                    "基本",
                    "basics",
                    "基本",
                    "основы",
                ],
                "python_advanced": [
                    "元类",
                    "metaclass",
                    "描述符",
                    "descriptor",
                    "反射",
                    "高度",
                    "advanced",
                    "高度",
                    "продвинутый",
                ],
                "shell": [
                    "脚本",
                    "bash",
                    "shell",
                    "自动化",
                    "cron",
                    "定时",
                    "命令",
                    "スクリプト",
                    "스크립트",
                    "script",
                    "скрипт",
                ],
                "configuration": [
                    "配置",
                    "yaml",
                    "toml",
                    "ini",
                    "settings",
                    "env",
                    "設定",
                    "설정",
                    "configuration",
                    "konfiguration",
                    "configuración",
                    "конфигурация",
                ],
                "security": [
                    "加密",
                    "解密",
                    "hash",
                    "密码",
                    "password",
                    "token",
                    "jwt",
                    "安全",
                    "セキュリティ",
                    "보안",
                    "sécurité",
                    "sicherheit",
                    "seguridad",
                    "безопасность",
                ],
                "datetime": [
                    "日期",
                    "时间",
                    "时区",
                    "timestamp",
                    "格式化日期",
                    "日付",
                    "날짜",
                    "date",
                    "datum",
                    "fecha",
                    "дата",
                ],
                "performance": [
                    "性能",
                    "profile",
                    "基准",
                    "benchmark",
                    "内存泄漏",
                    "优化",
                    "パフォーマンス",
                    "성능",
                    "performance",
                    "leistung",
                    "rendimiento",
                    "производительность",
                ],
                "code_quality": [
                    "规范",
                    "pep8",
                    "格式化",
                    "lint",
                    "代码审查",
                    "review",
                    "品質",
                    "품질",
                    "qualité",
                    "qualität",
                    "calidad",
                    "качество",
                ],
                "debugging": [
                    "断点",
                    "breakpoint",
                    "调试器",
                    "debugger",
                    "单步",
                    "デバッグ",
                    "디버깅",
                    "débogage",
                    "debuggen",
                    "depuración",
                    "отладка",
                ],
                "devops": [
                    "部署",
                    "deploy",
                    "ci",
                    "cd",
                    "pipeline",
                    "流水线",
                    "容器",
                    "デプロイ",
                    "배포",
                    "déploiement",
                    "bereitstellung",
                    "despliegue",
                    "развертывание",
                ],
                "package_management": [
                    "依赖",
                    "requirement",
                    "virtualenv",
                    "venv",
                    "conda",
                    "虚拟环境",
                    "パッケージ",
                    "패키지",
                    "paquet",
                    "paket",
                    "paquete",
                    "пакет",
                ],
                "cli_dev": [
                    "命令行",
                    "argparse",
                    "click",
                    "参数解析",
                    "subcommand",
                    "cli",
                    "コマンド",
                    "명령어",
                    "commande",
                    "befehl",
                    "comando",
                    "команда",
                ],
                "web_dev": [
                    "flask",
                    "fastapi",
                    "django",
                    "路由",
                    "route",
                    "endpoint",
                    "web",
                    "ウェブ",
                    "웹",
                    "web",
                    "веб",
                ],
                "data_science": [
                    "pandas",
                    "numpy",
                    "dataframe",
                    "数组",
                    "矩阵",
                    "数据",
                    "データ",
                    "데이터",
                    "données",
                    "daten",
                    "datos",
                    "данные",
                ],
                "machine_learning": [
                    "机器学习",
                    "训练",
                    "模型",
                    "训练集",
                    "测试集",
                    "accuracy",
                    "ml",
                    "機械学習",
                    "머신러닝",
                    "apprentissage",
                    "maschinenlernen",
                    "aprendizaje",
                    "машинное обучение",
                ],
                "math_stats": [
                    "数学",
                    "统计",
                    "概率",
                    "公式",
                    "计算",
                    "mean",
                    "average",
                    "数学",
                    "수학",
                    "math",
                    "mathematik",
                    "matemáticas",
                    "математика",
                ],
                "code_explanation": [
                    "解释",
                    "说明",
                    "什么意思",
                    "what does",
                    "how does",
                    "説明",
                    "설명",
                    "explication",
                    "erklärung",
                    "explicación",
                    "объяснение",
                ],
                "code_review": [
                    "优化建议",
                    "改进",
                    "better way",
                    "更优雅",
                    "best practice",
                    "レビュー",
                    "리뷰",
                    "revue",
                    "überprüfung",
                    "revisión",
                    "обзор",
                ],
                "system_info": [
                    "系统信息",
                    "platform",
                    "cpu",
                    "内存",
                    "memory",
                    "disk",
                    "操作系统",
                    "システム",
                    "시스템",
                    "système",
                    "system",
                    "sistema",
                    "система",
                ],
                "system_commands": [
                    "系统命令",
                    "system command",
                    "进程",
                    "process",
                    "服务",
                    "service",
                    "用户",
                    "user",
                    "日志",
                    "log",
                    "磁盘",
                    "disk",
                    "网络",
                    "network",
                ],
                "shell_scripting": [
                    "shell脚本",
                    "shell script",
                    "循环",
                    "loop",
                    "函数",
                    "function",
                    "条件",
                    "condition",
                    "数组",
                    "array",
                ],
                "tool_calling": [
                    "工具调用",
                    "tool call",
                    "bash",
                    "read",
                    "write",
                    "edit",
                    "glob",
                    "grep",
                    "工具使用",
                    "tool use",
                ],
            }
            for tid, tmpl in self.templates.items():
                if tid in matched_ids:
                    continue
                cat = tmpl.category.lower()
                for kw in cat_kw.get(cat, []):
                    if kw in text:
                        matches.append((5, tid, tmpl))
                        matched_ids.add(tid)
                        break

        matches.sort(key=lambda x: (-x[0], x[1]))
        return [m[2] for m in matches]

    def build_context(self, user_input: str, max_tokens: int = 200) -> str:
        """Build few-shot context from matching templates."""
        matched = self.match_templates(user_input)
        if not matched:
            return ""

        parts = []
        used_tokens = 0
        for tmpl in matched:
            for example in tmpl.examples[: tmpl.max_examples]:
                entry = f"Q: {example.question}\nA: {example.answer}"
                entry_tokens = len(entry) // 3
                if used_tokens + entry_tokens > max_tokens:
                    break
                parts.append(entry)
                used_tokens += entry_tokens
            if used_tokens >= max_tokens:
                break

        if not parts:
            return ""

        return "\n\n".join(["## Reference Examples"] + parts)

    def add_template(
        self,
        template_id: str,
        category: str,
        triggers: list[str],
        examples: list[dict[str, str]],
    ) -> None:
        """Add a new user-generated template."""
        distilled_examples = [DistilledExample(question=e["q"], answer=e["a"]) for e in examples]
        self.templates[template_id] = DistilledTemplate(
            category=category,
            triggers=triggers,
            examples=distilled_examples,
            max_examples=2,
        )
        self.save_user_templates()

    def list_templates(self) -> list[dict[str, Any]]:
        """List all templates."""
        result = []
        for tid, tmpl in self.templates.items():
            result.append(
                {
                    "id": tid,
                    "category": tmpl.category,
                    "triggers": tmpl.triggers,
                    "example_count": len(tmpl.examples),
                    "source": "built-in" if not tid.startswith("user_") else "user",
                }
            )
        return result

    def remove_template(self, template_id: str) -> bool:
        """Remove a user-generated template."""
        if template_id.startswith("user_") and template_id in self.templates:
            del self.templates[template_id]
            self.save_user_templates()
            return True
        return False


def _get_default_templates() -> dict[str, Any]:
    """Return comprehensive pre-populated templates covering all common scenarios."""
    return {
        # === 系统命令：系统信息 ===
        "sys_os_info": {
            "category": "system_commands",
            "triggers": [
                "系统信息",
                "system info",
                "os info",
                "操作系统",
                "uname",
                "hostname",
                "whoami",
                "id",
                "cat /etc/os-release",
                "lsb_release",
                "sw_vers",
                "システム情報",
                "시스템 정보",
                "informations système",
                "systeminformationen",
                "información del sistema",
                "информация о системе",
            ],
            "examples": [
                {
                    "q": "查看当前操作系统信息",
                    "a": '# Linux\nuname -a                  # 完整系统信息\ncat /etc/os-release     # 发行版详情\nhostname                # 主机名\nwhoami && id            # 当前用户和组\n\n# macOS\nsw_vers                 # macOS版本\n\n# 跨平台\npython3 -c "import platform; print(platform.system(), platform.release(), platform.machine())"',
                },
            ],
        },
        "sys_process": {
            "category": "system_commands",
            "triggers": [
                "进程",
                "process",
                "ps",
                "top",
                "htop",
                "kill",
                "pkill",
                "pgrep",
                "nice",
                "renice",
                "nohup",
                "后台",
                "background",
                "fg",
                "bg",
                "jobs",
                "プロセス",
                "프로세스",
                "processus",
                "prozess",
                "proceso",
                "процесс",
            ],
            "examples": [
                {
                    "q": "查看和管理进程",
                    "a": "ps aux | grep python      # 查找Python进程\ntop -u $USER             # 查看当前用户进程\nkill -9 <PID>            # 强制终止进程\npkill -f 'python app.py' # 按名称终止\npgrep -a python          # 查找Python进程PID\n\n# 后台运行\nnohup python app.py > app.log 2>&1 &\njobs                     # 查看后台任务\nfg %1                    # 恢复到前台",
                },
            ],
        },
        "sys_network": {
            "category": "system_commands",
            "triggers": [
                "网络",
                "network",
                "ip",
                "ifconfig",
                "netstat",
                "ss",
                "ping",
                "traceroute",
                "curl",
                "wget",
                "nc",
                "nmap",
                "dig",
                "nslookup",
                "ネットワーク",
                "네트워크",
                "réseau",
                "netzwerk",
                "red",
                "сеть",
            ],
            "examples": [
                {
                    "q": "网络诊断和连接测试",
                    "a": "ip addr show             # 查看IP地址（Linux）\nifconfig                 # 查看IP地址（macOS）\nss -tlnp                 # 查看监听端口\nping -c 4 google.com     # 测试连通性\ncurl -I https://api.example.com  # 检查HTTP响应\nwget -qO- ifconfig.me    # 查看公网IP\ndig example.com          # DNS查询\nnc -zv localhost 8080    # 测试端口",
                },
            ],
        },
        "sys_disk": {
            "category": "system_commands",
            "triggers": [
                "磁盘",
                "disk",
                "df",
                "du",
                "lsblk",
                "fdisk",
                "mount",
                "umount",
                "rsync",
                "dd",
                "磁盘空间",
                "disk space",
                "存储",
                "storage",
                "ディスク",
                "디스크",
                "disque",
                "festplatte",
                "disco",
                "диск",
            ],
            "examples": [
                {
                    "q": "磁盘管理和空间检查",
                    "a": "df -h                    # 磁盘使用概况\ndu -sh ./*               # 当前目录各文件大小\ndu -sh /var/log          # 特定目录大小\nlsblk                    # 块设备列表\n\n# 查找大文件\nfind / -type f -size +100M 2>/dev/null\n\n# 同步文件\nrsync -avz src/ dest/\n\n# 清理\njournalctl --vacuum-time=7d  # 清理旧日志",
                },
            ],
        },
        "sys_users": {
            "category": "system_commands",
            "triggers": [
                "用户",
                "user",
                "useradd",
                "usermod",
                "userdel",
                "passwd",
                "groupadd",
                "groups",
                "sudo",
                "visudo",
                "who",
                "w",
                "last",
                "ユーザー",
                "사용자",
                "utilisateur",
                "benutzer",
                "usuario",
                "пользователь",
            ],
            "examples": [
                {
                    "q": "用户和权限管理",
                    "a": "whoami && id             # 当前用户信息\nusers / who / w          # 在线用户\nsudo useradd -m -s /bin/bash newuser\nsudo passwd newuser      # 设置密码\nsudo usermod -aG sudo newuser  # 添加sudo权限\nsudo userdel -r olduser  # 删除用户及家目录\ngroups username          # 查看用户组",
                },
            ],
        },
        "sys_services": {
            "category": "system_commands",
            "triggers": [
                "服务",
                "service",
                "systemctl",
                "journalctl",
                "crontab",
                "at",
                "启动",
                "stop",
                "restart",
                "enable",
                "disable",
                "status",
                "サービス",
                "서비스",
                "service",
                "dienst",
                "servicio",
                "сервис",
            ],
            "examples": [
                {
                    "q": "服务管理和定时任务",
                    "a": "systemctl status nginx     # 查看服务状态\nsudo systemctl start nginx\nsudo systemctl stop nginx\nsudo systemctl restart nginx\nsudo systemctl enable nginx  # 开机自启\njournalctl -u nginx -f     # 实时查看服务日志\n\n# 定时任务\ncrontab -e                 # 编辑定时任务\n# 每天凌晨2点执行\n0 2 * * * /path/to/script.sh\ncrontab -l                 # 查看定时任务",
                },
            ],
        },
        "sys_logs": {
            "category": "system_commands",
            "triggers": [
                "日志",
                "log",
                "journalctl",
                "dmesg",
                "tail",
                "grep",
                "logrotate",
                "var/log",
                "syslog",
                "messages",
                "auth.log",
                "kern.log",
                "ログ",
                "로그",
                "journal",
                "protokoll",
                "registro",
                "лог",
            ],
            "examples": [
                {
                    "q": "日志查看和分析",
                    "a": "journalctl -xe             # 最近错误\njournalctl -u nginx --since today  # 今日nginx日志\njournalctl -k              # 内核日志\ntail -f /var/log/syslog    # 实时跟踪日志\ngrep -i error /var/log/syslog  # 搜索错误\ndmesg | tail -20           # 最近内核消息\n\n# 日志轮转配置\n/etc/logrotate.d/          # 轮转配置目录\nlogrotate -f /etc/logrotate.conf  # 强制轮转",
                },
            ],
        },
        "sys_security": {
            "category": "system_commands",
            "triggers": [
                "安全",
                "security",
                "chmod",
                "chown",
                "chgrp",
                "umask",
                "iptables",
                "ufw",
                "firewall",
                "fail2ban",
                "ssh",
                "ssh-keygen",
                "selinux",
                "セキュリティ",
                "보안",
                "sécurité",
                "sicherheit",
                "seguridad",
                "безопасность",
            ],
            "examples": [
                {
                    "q": "系统安全和防火墙配置",
                    "a": "chmod 600 ~/.ssh/id_rsa    # 私钥权限\nchmod 755 /var/www         # 目录权限\nchown www-data:www-data /var/www  # 更改所有者\n\n# 防火墙\nsudo ufw enable            # 启用防火墙\nsudo ufw allow 22/tcp      # 允许SSH\nsudo ufw allow 80,443/tcp  # 允许HTTP/HTTPS\nsudo ufw status            # 查看状态\n\n# SSH安全\nssh-keygen -t ed25519      # 生成密钥\nssh-copy-id user@host      # 复制公钥",
                },
            ],
        },
        "sys_package": {
            "category": "system_commands",
            "triggers": [
                "包管理",
                "package",
                "apt",
                "yum",
                "dnf",
                "pacman",
                "brew",
                "snap",
                "flatpak",
                "install",
                "remove",
                "update",
                "upgrade",
                "パッケージ",
                "패키지",
                "paquet",
                "paket",
                "paquete",
                "пакет",
            ],
            "examples": [
                {
                    "q": "软件包管理命令",
                    "a": "# Debian/Ubuntu\nsudo apt update && sudo apt upgrade\nsudo apt install <pkg>\nsudo apt remove <pkg>\n\n# RHEL/CentOS\nsudo dnf install <pkg>\nsudo dnf remove <pkg>\n\n# macOS\nbrew install <pkg>\nbrew upgrade\nbrew list\n\n# 查找包\napt search <keyword>\ndnf search <keyword>\nbrew search <keyword>",
                },
            ],
        },
        # === Shell脚本：基础 ===
        "shell_basics": {
            "category": "shell_scripting",
            "triggers": [
                "shell脚本",
                "shell script",
                "bash script",
                "shebang",
                "#!/bin/bash",
                "变量",
                "variable",
                "引号",
                "quote",
                "注释",
                "comment",
                "シェルスクリプト",
                "셸 스크립트",
                "script shell",
                "shell-skript",
                "script de shell",
                "шелл-скрипт",
            ],
            "examples": [
                {
                    "q": "Shell脚本基础写法",
                    "a": '#!/bin/bash\n# 脚本基础示例\n\n# 变量（无需$声明）\nNAME="World"\nCOUNT=10\n\n# 引号区别\necho "Hello $NAME"    # 双引号：变量展开\necho \'Hello $NAME\'     # 单引号：字面量\n\n# 命令替换\nTODAY=$(date +%Y-%m-%d)\nFILES=$(ls *.txt)\n\n# 特殊变量\n# $0=脚本名 $1=参数1 $#参数个数 $@所有参数 $?上个命令退出码',
                },
            ],
        },
        "shell_conditionals": {
            "category": "shell_scripting",
            "triggers": [
                "条件",
                "conditional",
                "if",
                "else",
                "elif",
                "case",
                "test",
                "[[",
                "[]",
                "比较",
                "compare",
                "字符串比较",
                "数字比较",
                "条件分岐",
                "조건문",
                "conditionnelle",
                "bedingung",
                "condicional",
                "условие",
            ],
            "examples": [
                {
                    "q": "Shell条件判断写法",
                    "a": '# 数字比较: -eq -ne -lt -le -gt -ge\nif [ $COUNT -gt 5 ]; then\n    echo "大于5"\nelif [ $COUNT -eq 5 ]; then\n    echo "等于5"\nelse\n    echo "小于5"\nfi\n\n# 字符串: = != -z(空) -n(非空)\nif [[ "$NAME" == "World" ]]; then\n    echo "匹配"\nfi\n\n# 文件: -e存在 -f文件 -d目录 -r可读 -w可写 -x可执行\nif [[ -f "/etc/passwd" ]]; then\n    echo "文件存在"\nfi\n\n# case语句\ncase $1 in\n    start) echo "启动" ;;\n    stop)  echo "停止" ;;\n    *)     echo "用法: $0 {start|stop}" ;;\nesac',
                },
            ],
        },
        "shell_loops": {
            "category": "shell_scripting",
            "triggers": [
                "循环",
                "loop",
                "for",
                "while",
                "until",
                "break",
                "continue",
                "遍历",
                "iterate",
                "范围",
                "range",
                "seq",
                "ループ",
                "반복문",
                "boucle",
                "schleife",
                "bucle",
                "цикл",
            ],
            "examples": [
                {
                    "q": "Shell循环写法",
                    "a": '# for循环\nfor i in {1..10}; do\n    echo $i\ndone\n\nfor file in *.txt; do\n    echo "处理: $file"\ndone\n\nfor i in $(seq 1 100); do\n    echo $i\ndone\n\n# while循环\nwhile read -r line; do\n    echo "$line"\ndone < input.txt\n\n# C风格for\nfor ((i=0; i<10; i++)); do\n    echo $i\ndone\n\n# until循环\nCOUNT=0\nuntil [ $COUNT -ge 5 ]; do\n    echo $COUNT\n    ((COUNT++))\ndone',
                },
            ],
        },
        "shell_functions": {
            "category": "shell_scripting",
            "triggers": [
                "函数",
                "function",
                "参数",
                "parameter",
                "返回值",
                "return",
                "作用域",
                "scope",
                "local",
                "全局",
                "global",
                "関数",
                "함수",
                "fonction",
                "funktion",
                "función",
                "функция",
            ],
            "examples": [
                {
                    "q": "Shell函数定义和使用",
                    "a": '# 定义函数\nlog_msg() {\n    local level="$1"    # 局部变量\n    local msg="$2"\n    echo "[$(date +\'%H:%M:%S\')] [$level] $msg"\n}\n\n# 调用\nlog_msg "INFO" "脚本开始"\nlog_msg "ERROR" "出错了"\n\n# 返回值（只能是0-255）\ncheck_file() {\n    [[ -f "$1" ]]\n    return $?  # 0=成功, 1=失败\n}\n\nif check_file "/etc/passwd"; then\n    echo "文件存在"\nfi\n\n# 位置参数\nmy_func() {\n    echo "函数名: $0"\n    echo "参数1: $1"\n    echo "所有参数: $@"\n    echo "参数个数: $#"\n}',
                },
            ],
        },
        "shell_text_processing": {
            "category": "shell_scripting",
            "triggers": [
                "文本处理",
                "text processing",
                "awk",
                "sed",
                "grep",
                "cut",
                "sort",
                "uniq",
                "tr",
                "wc",
                "paste",
                "join",
                "head",
                "tail",
                "テキスト処理",
                "텍스트 처리",
                "traitement de texte",
                "textverarbeitung",
                "procesamiento de texto",
                "обработка текста",
            ],
            "examples": [
                {
                    "q": "Shell文本处理命令",
                    "a": "# grep: 搜索\ngrep -r \"pattern\" .     # 递归搜索\ngrep -i \"error\" log.txt  # 忽略大小写\ngrep -v \"debug\" log.txt  # 反向匹配\ngrep -c \"error\" log.txt  # 计数\n\n# awk: 列处理\nawk '{print $1, $3}' file.csv\nawk -F',' '{print $2}' file.csv\nawk '$3 > 100 {print $1}' file.csv\n\n# sed: 行处理/替换\nsed 's/old/new/g' file.txt\nsed -i 's/old/new/g' file.txt  # 原地替换\nsed -n '10,20p' file.txt       # 打印10-20行\n\n# 管道组合\ncat access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -10",
                },
            ],
        },
        "shell_error_handling": {
            "category": "shell_scripting",
            "triggers": [
                "错误处理",
                "error handling",
                "set -e",
                "set -u",
                "set -o pipefail",
                "trap",
                "退出码",
                "exit code",
                "调试",
                "debug",
                "set -x",
                "エラー処理",
                "오류 처리",
                "gestion d'erreurs",
                "fehlerbehandlung",
                "manejo de errores",
                "обработка ошибок",
            ],
            "examples": [
                {
                    "q": "Shell脚本错误处理最佳实践",
                    "a": '#!/bin/bash\nset -euo pipefail  # 遇错退出/未定义变量报错/管道失败传递\n\n# 错误处理函数\nerror_handler() {\n    echo "错误: 第 $1 行，退出码 $2"\n    exit "$2"\n}\ntrap \'error_handler $LINENO $?\' ERR\n\n# 可选错误处理\ncommand_that_might_fail || echo "命令失败，继续执行"\n\n# 检查命令是否存在\nif ! command -v docker &>/dev/null; then\n    echo "docker未安装"\n    exit 1\nfi\n\n# 调试模式\nset -x  # 打印执行的命令\n# set +x  # 关闭调试',
                },
            ],
        },
        "shell_io_redirection": {
            "category": "shell_scripting",
            "triggers": [
                "重定向",
                "redirection",
                "管道",
                "pipe",
                "stdin",
                "stdout",
                "stderr",
                ">",
                ">>",
                "2>",
                "&>",
                "|",
                "here-doc",
                "here-string",
                "入出力",
                "입출력",
                "redirection",
                "umleitung",
                "redirección",
                "перенаправление",
            ],
            "examples": [
                {
                    "q": "Shell输入输出重定向",
                    "a": '# 标准输出重定向\necho "hello" > output.txt     # 覆盖\necho "world" >> output.txt    # 追加\n\n# 标准错误重定向\ncommand 2> error.log           # 错误到文件\ncommand > output.txt 2>&1      # 标准+错误到同一文件\ncommand &> all.log             # 简写（bash）\n\n# 丢弃输出\ncommand > /dev/null 2>&1\n\n# 管道\ncat file.txt | grep pattern | wc -l\n\n# Here-document\ncat << EOF > config.txt\nkey1=value1\nkey2=value2\nEOF\n\n# Here-string\ngrep "pattern" <<< "$VARIABLE"',
                },
            ],
        },
        "shell_arrays": {
            "category": "shell_scripting",
            "triggers": [
                "数组",
                "array",
                "关联数组",
                "associative array",
                "declare -a",
                "declare -A",
                "数组遍历",
                "array iteration",
                "配列",
                "배열",
                "tableau",
                "array",
                "matriz",
                "массив",
            ],
            "examples": [
                {
                    "q": "Shell数组使用",
                    "a": '# 普通数组\nFRUITS=("apple" "banana" "cherry")\necho ${FRUITS[0]}        # apple\necho ${FRUITS[@]}        # 所有元素\necho ${#FRUITS[@]}       # 长度\n\n# 遍历\nfor fruit in "${FRUITS[@]}"; do\n    echo "$fruit"\ndone\n\n# 添加/删除\nFRUITS+=("date")\nunset FRUITS[1]\n\n# 关联数组（bash 4+）\ndeclare -A COLORS\nCOLORS[red]="#ff0000"\nCOLORS[green]="#00ff00"\n\nfor key in "${!COLORS[@]}"; do\n    echo "$key -> ${COLORS[$key]}"\ndone',
                },
            ],
        },
        "shell_string_manipulation": {
            "category": "shell_scripting",
            "triggers": [
                "字符串操作",
                "string manipulation",
                "截取",
                "substring",
                "替换",
                "replace",
                "长度",
                "length",
                "分割",
                "split",
                "拼接",
                "concatenate",
                "文字列操作",
                "문자열 조작",
                "manipulation de chaîne",
                "zeichenketten",
                "manipulación de cadenas",
                "манипуляция строками",
            ],
            "examples": [
                {
                    "q": "Shell字符串操作",
                    "a": 'STR="Hello World"\n\n# 长度\necho ${#STR}              # 11\n\n# 截取\necho ${STR:0:5}           # Hello\necho ${STR:6}             # World\necho ${STR: -5}           # World（注意空格）\n\n# 替换\necho ${STR/World/Bash}    # Hello Bash\necho ${STR//l/L}          # HeLLo WorLd（全部）\n\n# 删除模式\necho ${STR#Hello}         #  World（最短前缀）\necho ${STR##*o}           # rld（最长前缀）\necho ${STR%World}         # Hello （最短后缀）\necho ${STR%%o*}           # Hell（最长后缀）\n\n# 大小写\necho ${STR,,}             # hello world\necho ${STR^^}             # HELLO WORLD',
                },
            ],
        },
        "shell_math": {
            "category": "shell_scripting",
            "triggers": [
                "数学运算",
                "math",
                "arithmetic",
                "计算",
                "calculate",
                "expr",
                "$(( ))",
                "bc",
                "浮点",
                "float",
                "随机数",
                "random",
                "数学演算",
                "수학 연산",
                "calcul mathématique",
                "mathematik",
                "cálculo matemático",
                "математические вычисления",
            ],
            "examples": [
                {
                    "q": "Shell数学运算",
                    "a": '# 整数运算\necho $((2 + 3))           # 5\necho $((10 / 3))          # 3\necho $((2 ** 10))         # 1024\n\nCOUNT=5\n((COUNT++))\necho $COUNT               # 6\n\n# 浮点运算（bc）\necho "scale=2; 10 / 3" | bc  # 3.33\necho "3.14 * 2" | bc          # 6.28\n\n# 随机数\necho $RANDOM              # 0-32767\necho $((RANDOM % 100))    # 0-99\n\n# 比较\necho $((5 > 3))           # 1（真）\necho $((5 < 3))           # 0（假）',
                },
            ],
        },
        # === 工具调用策略 ===
        "tool_bash": {
            "category": "tool_calling",
            "triggers": [
                "bash工具",
                "bash tool",
                "执行命令",
                "run command",
                "shell命令",
                "终端命令",
                "terminal command",
                "运行",
                "execute",
                "bashツール",
                "bash 도구",
                "outil bash",
                "bash-tool",
                "herramienta bash",
                "инструмент bash",
            ],
            "examples": [
                {
                    "q": "什么时候使用Bash工具",
                    "a": "使用Bash工具的场景：\n1. 执行系统命令（ls, git, pip等）\n2. 运行脚本或程序\n3. 安装依赖\n4. 检查文件/目录\n5. 网络请求（curl）\n\n避免使用Bash的场景：\n1. 读取文件内容 → 用Read工具\n2. 写入文件内容 → 用Write工具\n3. 查找文件 → 用Glob工具\n4. 搜索代码 → 用Grep工具\n\n最佳实践：\n- 命令要具体明确\n- 使用绝对路径避免歧义\n- 复杂操作拆分为多个步骤",
                },
            ],
        },
        "tool_read": {
            "category": "tool_calling",
            "triggers": [
                "read工具",
                "read tool",
                "读取文件",
                "read file",
                "查看文件",
                "文件内容",
                "file content",
                "打开文件",
                "open file",
                "readツール",
                "read 도구",
                "outil read",
                "read-tool",
                "herramienta read",
                "инструмент read",
            ],
            "examples": [
                {
                    "q": "什么时候使用Read工具",
                    "a": "使用Read工具的场景：\n1. 查看文件内容（代码、配置、文档）\n2. 理解现有代码结构\n3. 检查配置文件\n4. 阅读错误日志\n\nRead工具参数：\n- file_path: 文件路径（必需）\n- offset: 起始行号（可选，默认1）\n- limit: 读取行数（可选，默认2000）\n\n最佳实践：\n- 大文件指定offset/limit避免超上下文\n- 先读关键部分再决定下一步\n- 结合Grep搜索特定内容",
                },
            ],
        },
        "tool_write": {
            "category": "tool_calling",
            "triggers": [
                "write工具",
                "write tool",
                "写入文件",
                "write file",
                "创建文件",
                "create file",
                "保存文件",
                "save file",
                "生成文件",
                "generate file",
                "writeツール",
                "write 도구",
                "outil write",
                "write-tool",
                "herramienta write",
                "инструмент write",
            ],
            "examples": [
                {
                    "q": "什么时候使用Write工具",
                    "a": "使用Write工具的场景：\n1. 创建新文件\n2. 完全重写文件内容\n3. 生成配置文件\n4. 创建脚本或文档\n\nWrite工具参数：\n- file_path: 文件路径（必需）\n- content: 文件内容（必需）\n\n最佳实践：\n- 写入前先Read了解现有内容\n- 确保目录存在\n- 大文件考虑分块写入\n- 注意文件编码（UTF-8）",
                },
            ],
        },
        "tool_edit": {
            "category": "tool_calling",
            "triggers": [
                "edit工具",
                "edit tool",
                "编辑文件",
                "edit file",
                "修改文件",
                "modify file",
                "替换",
                "replace",
                "查找替换",
                "find replace",
                "editツール",
                "edit 도구",
                "outil edit",
                "edit-tool",
                "herramienta edit",
                "инструмент edit",
            ],
            "examples": [
                {
                    "q": "什么时候使用Edit工具",
                    "a": "使用Edit工具的场景：\n1. 修改文件的部分内容\n2. 修复bug或更新代码\n3. 添加/删除函数或代码块\n\nEdit工具参数：\n- file_path: 文件路径（必需）\n- old_string: 要替换的内容（必需，必须唯一匹配）\n- new_string: 替换后的内容（必需）\n\n最佳实践：\n- old_string要足够长以确保唯一匹配\n- 先Read确认要修改的内容\n- 小改动优先用Edit而非Write\n- 如果old_string不唯一，提供更多上下文",
                },
            ],
        },
        "tool_glob_grep": {
            "category": "tool_calling",
            "triggers": [
                "glob工具",
                "glob tool",
                "grep工具",
                "grep tool",
                "查找文件",
                "find file",
                "搜索代码",
                "search code",
                "文件搜索",
                "file search",
                "代码搜索",
                "code search",
                "模式匹配",
                "pattern match",
                "globツール",
                "grepツール",
                "glob/grep 도구",
                "outil glob/grep",
            ],
            "examples": [
                {
                    "q": "什么时候使用Glob和Grep工具",
                    "a": "Glob工具（查找文件）：\n- 按文件名模式搜索\n- 支持通配符 *.py, **/*.js\n- 自动忽略.gitignore中的文件\n- 示例: **/*.py 查找所有Python文件\n\nGrep工具（搜索内容）：\n- 在文件中搜索文本模式\n- 支持正则表达式\n- 跨文件搜索\n- 示例: def .*: 查找所有函数定义\n\n最佳实践：\n- 先用Glob定位文件\n- 再用Grep搜索内容\n- 结合使用提高效率",
                },
            ],
        },
        # === 算法与数据结构 (10) ===
        "code_sort": {
            "category": "algorithm",
            "triggers": [
                "sort",
                "排序",
                "快速排序",
                "quicksort",
                "冒泡",
                "bubblesort",
                "归并",
                "mergesort",
                "插入排序",
                "insertion",
                "选择排序",
                "selection",
                "堆排序",
                "heapsort",
                "希尔排序",
                "shellsort",
            ],
            "examples": [
                {
                    "q": "用Python写一个快速排序",
                    "a": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
                },
                {
                    "q": "Python list sort in place",
                    "a": "arr.sort()  # sorts in place, O(n log n)\n# or\nsorted_arr = sorted(arr)  # returns new list",
                },
            ],
        },
        "code_search": {
            "category": "algorithm",
            "triggers": [
                "search",
                "查找",
                "搜索",
                "二分",
                "binary search",
                "线性查找",
                "linear search",
                "哈希表",
                "hash table",
                "双指针",
                "two pointer",
                "滑动窗口",
                "sliding window",
            ],
            "examples": [
                {
                    "q": "用Python写二分查找",
                    "a": "def binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1",
                },
            ],
        },
        "code_tree": {
            "category": "algorithm",
            "triggers": [
                "tree",
                "树",
                "二叉树",
                "binary tree",
                "遍历",
                "traversal",
                "前序",
                "preorder",
                "中序",
                "inorder",
                "后序",
                "postorder",
                "层序",
                "level order",
                "bfs",
                "dfs",
                "深度优先",
                "广度优先",
                "二叉搜索树",
                "bst",
                "平衡树",
                "avl",
                "红黑树",
            ],
            "examples": [
                {
                    "q": "Python二叉树前序遍历",
                    "a": "def preorder(root):\n    if not root:\n        return []\n    return [root.val] + preorder(root.left) + preorder(root.right)\n\n# 迭代版本\ndef preorder_iter(root):\n    if not root: return []\n    stack, result = [root], []\n    while stack:\n        node = stack.pop()\n        result.append(node.val)\n        if node.right: stack.append(node.right)\n        if node.left: stack.append(node.left)\n    return result",
                },
            ],
        },
        "code_graph": {
            "category": "algorithm",
            "triggers": [
                "graph",
                "图",
                "邻接表",
                "adjacency",
                "最短路径",
                "shortest path",
                "dijkstra",
                "bfs图",
                "dfs图",
                "拓扑排序",
                "topological",
                "最小生成树",
                "mst",
                "prim",
                "kruskal",
            ],
            "examples": [
                {
                    "q": "Python图的BFS遍历",
                    "a": "from collections import deque\ndef bfs(graph, start):\n    visited = set([start])\n    queue = deque([start])\n    while queue:\n        node = queue.popleft()\n        print(node)\n        for neighbor in graph[node]:\n            if neighbor not in visited:\n                visited.add(neighbor)\n                queue.append(neighbor)",
                },
            ],
        },
        "code_dp": {
            "category": "algorithm",
            "triggers": [
                "dp",
                "动态规划",
                "dynamic programming",
                "斐波那契",
                "fibonacci",
                "背包",
                "knapsack",
                "最长子序列",
                "longest subsequence",
                "编辑距离",
                "edit distance",
                "状态转移",
            ],
            "examples": [
                {
                    "q": "Python动态规划求斐波那契",
                    "a": "def fib(n):\n    if n <= 1: return n\n    dp = [0] * (n + 1)\n    dp[1] = 1\n    for i in range(2, n + 1):\n        dp[i] = dp[i-1] + dp[i-2]\n    return dp[n]\n\n# 空间优化\ndef fib_opt(n):\n    a, b = 0, 1\n    for _ in range(n): a, b = b, a + b\n    return a",
                },
            ],
        },
        "code_linked_list": {
            "category": "algorithm",
            "triggers": [
                "linked list",
                "链表",
                "反转链表",
                "reverse list",
                "环形链表",
                "cycle",
                "合并链表",
                "merge list",
            ],
            "examples": [
                {
                    "q": "Python反转链表",
                    "a": "def reverse_list(head):\n    prev = None\n    curr = head\n    while curr:\n        nxt = curr.next\n        curr.next = prev\n        prev = curr\n        curr = nxt\n    return prev",
                },
            ],
        },
        "code_stack_queue": {
            "category": "algorithm",
            "triggers": [
                "stack",
                "栈",
                "queue",
                "队列",
                "deque",
                "双端队列",
                "括号匹配",
                "parentheses",
                "单调栈",
                "monotonic",
                "优先队列",
                "priority queue",
                "heap",
                "堆",
            ],
            "examples": [
                {
                    "q": "Python栈实现括号匹配",
                    "a": "def is_valid(s):\n    stack = []\n    mapping = {')': '(', '}': '{', ']': '['}\n    for char in s:\n        if char in mapping:\n            if not stack or stack.pop() != mapping[char]:\n                return False\n        else:\n            stack.append(char)\n    return not stack",
                },
            ],
        },
        "code_hash": {
            "category": "algorithm",
            "triggers": [
                "hash",
                "哈希",
                "字典",
                "dict",
                "去重",
                "dedup",
                "两数之和",
                "two sum",
                "计数",
                "count",
                "频率",
                "frequency",
            ],
            "examples": [
                {
                    "q": "Python两数之和",
                    "a": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []",
                },
            ],
        },
        "code_recursion": {
            "category": "algorithm",
            "triggers": [
                "recursion",
                "递归",
                "回溯",
                "backtrack",
                "分治",
                "divide",
                "全排列",
                "permutation",
                "组合",
                "combination",
                "子集",
                "subset",
            ],
            "examples": [
                {
                    "q": "Python回溯求全排列",
                    "a": "def permute(nums):\n    result = []\n    def backtrack(path, remaining):\n        if not remaining:\n            result.append(path[:])\n            return\n        for i in range(len(remaining)):\n            backtrack(path + [remaining[i]], remaining[:i] + remaining[i+1:])\n    backtrack([], nums)\n    return result",
                },
            ],
        },
        "code_greedy": {
            "category": "algorithm",
            "triggers": [
                "greedy",
                "贪心",
                "区间",
                "interval",
                "活动选择",
                "霍夫曼",
                "huffman",
                "最小覆盖",
            ],
            "examples": [
                {
                    "q": "Python贪心算法区间合并",
                    "a": "def merge_intervals(intervals):\n    if not intervals: return []\n    intervals.sort(key=lambda x: x[0])\n    merged = [intervals[0]]\n    for start, end in intervals[1:]:\n        if start <= merged[-1][1]:\n            merged[-1][1] = max(merged[-1][1], end)\n        else:\n            merged.append([start, end])\n    return merged",
                },
            ],
        },
        # === 文件操作 (6) ===
        "file_read": {
            "category": "file_operations",
            "triggers": [
                "read file",
                "读取文件",
                "open file",
                "打开文件",
                "读文件",
                "file content",
                "文件内容",
                "readline",
                "readlines",
            ],
            "examples": [
                {
                    "q": "Python读取文件内容",
                    "a": "# 推荐方式：with语句自动关闭文件\nwith open('file.txt', 'r', encoding='utf-8') as f:\n    content = f.read()  # 读取全部内容\n    # 或逐行读取：\n    # for line in f:\n    #     print(line)",
                },
            ],
        },
        "file_write": {
            "category": "file_operations",
            "triggers": [
                "write file",
                "写入文件",
                "保存文件",
                "save file",
                "写文件",
                "create file",
                "创建文件",
                "append",
                "追加",
            ],
            "examples": [
                {
                    "q": "Python写入文件",
                    "a": "with open('output.txt', 'w', encoding='utf-8') as f:\n    f.write('Hello, World!\\n')\n    f.write('Second line\\n')\n# 'w' 覆盖，'a' 追加",
                },
            ],
        },
        "file_csv": {
            "category": "file_operations",
            "triggers": [
                "csv",
                "逗号分隔",
                "表格文件",
                "spreadsheet",
                "excel",
                "pandas read_csv",
                "to_csv",
            ],
            "examples": [
                {
                    "q": "Python读写CSV文件",
                    "a": "import csv\n# 读取\nwith open('data.csv') as f:\n    reader = csv.DictReader(f)\n    for row in reader:\n        print(row['name'])\n# 写入\nwith open('out.csv', 'w', newline='') as f:\n    writer = csv.writer(f)\n    writer.writerow(['name', 'age'])\n    writer.writerow(['Alice', 30])",
                },
            ],
        },
        "file_path": {
            "category": "file_operations",
            "triggers": [
                "path",
                "路径",
                "目录",
                "directory",
                "folder",
                "文件夹",
                "os.path",
                "pathlib",
                "遍历目录",
                "walk",
                "glob",
                "创建目录",
                "mkdir",
                "删除文件",
                "remove",
                "rename",
                "重命名",
            ],
            "examples": [
                {
                    "q": "Python遍历目录所有文件",
                    "a": "from pathlib import Path\n# 推荐pathlib\nfor f in Path('.').rglob('*.py'):\n    print(f)\n\n# 或os.walk\nimport os\nfor root, dirs, files in os.walk('.'):\n    for f in files:\n        if f.endswith('.py'):\n            print(os.path.join(root, f))",
                },
            ],
        },
        "file_json": {
            "category": "file_operations",
            "triggers": [
                "json",
                "解析",
                "parse",
                "序列化",
                "serialize",
                "deserialize",
                "反序列化",
                "json文件",
            ],
            "examples": [
                {
                    "q": "Python解析JSON",
                    "a": "import json\n# 字符串转字典\ndata = json.loads('{\"name\": \"Alice\", \"age\": 30}')\n# 字典转字符串\njson_str = json.dumps(data, indent=2, ensure_ascii=False)\n# 文件读写\nwith open('data.json') as f:\n    data = json.load(f)\nwith open('out.json', 'w') as f:\n    json.dump(data, f, indent=2, ensure_ascii=False)",
                },
            ],
        },
        "file_yaml": {
            "category": "file_operations",
            "triggers": [
                "yaml",
                "yml",
                "配置文件",
                "config file",
                "pyyaml",
            ],
            "examples": [
                {
                    "q": "Python读写YAML文件",
                    "a": "import yaml\n# 读取\nwith open('config.yaml') as f:\n    config = yaml.safe_load(f)\n# 写入\nwith open('config.yaml', 'w') as f:\n    yaml.dump(config, f, default_flow_style=False)",
                },
            ],
        },
        # === 正则与文本处理 (2) ===
        "regex": {
            "category": "text_processing",
            "triggers": [
                "regex",
                "正则",
                "regular expression",
                "pattern",
                "匹配",
                "re模块",
                "re.search",
                "re.findall",
                "re.sub",
                "re.match",
            ],
            "examples": [
                {
                    "q": "Python正则表达式匹配邮箱",
                    "a": "import re\npattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'\nmatch = re.search(pattern, text)\nif match:\n    email = match.group()  # 提取邮箱",
                },
                {
                    "q": "正则提取所有数字",
                    "a": "import re\nnumbers = re.findall(r'\\d+', text)  # ['123', '456']\n# 或整数列表：\nnums = [int(n) for n in re.findall(r'\\d+', text)]",
                },
            ],
        },
        "string_ops": {
            "category": "text_processing",
            "triggers": [
                "string",
                "字符串",
                "split",
                "join",
                "replace",
                "替换",
                "strip",
                "upper",
                "lower",
                "format",
                "f-string",
                "截取",
                "substring",
                "拼接",
                "concatenate",
            ],
            "examples": [
                {
                    "q": "Python字符串操作",
                    "a": "s = 'Hello World'\ns.split()           # ['Hello', 'World']\n'-'.join(['a','b']) # 'a-b'\ns.replace('o','0')  # 'Hell0 W0rld'\ns.strip()           # 去两端空白\ns.lower() / s.upper()\nf'{s}! {42}'        # f-string格式化",
                },
            ],
        },
        # === Git 操作 (2) ===
        "git_basic": {
            "category": "git_operations",
            "triggers": [
                "git",
                "提交",
                "commit",
                "push",
                "pull",
                "branch",
                "分支",
                "merge",
                "合并",
                "clone",
                "init",
                "status",
                "log",
                "diff",
                "add",
                "reset",
                "checkout",
                "switch",
                "stash",
                "tag",
            ],
            "examples": [
                {
                    "q": "git常用命令",
                    "a": 'git status              # 查看状态\ngit add .               # 添加所有文件\ngit commit -m "msg"     # 提交\ngit push origin main    # 推送\ngit pull origin main    # 拉取\ngit log --oneline       # 查看历史\ngit branch -a           # 查看所有分支',
                },
            ],
        },
        "git_advanced": {
            "category": "git_operations",
            "triggers": [
                "rebase",
                "变基",
                "cherry-pick",
                "bisect",
                "blame",
                "reflog",
                "回滚",
                "revert",
                "force push",
                "冲突",
                "conflict",
                "submodule",
                "子模块",
                "gitignore",
            ],
            "examples": [
                {
                    "q": "git解决冲突",
                    "a": "1. git pull 发现冲突\n2. 编辑冲突文件，搜索 <<<<<<<\n3. 手动解决后保存\n4. git add <resolved_files>\n5. git commit\n\n# 或放弃合并\ngit merge --abort",
                },
            ],
        },
        # === 网络与HTTP (3) ===
        "http_request": {
            "category": "network",
            "triggers": [
                "http",
                "请求",
                "request",
                "api",
                "接口",
                "get",
                "post",
                "fetch",
                "网络请求",
                "requests库",
                "urllib",
                "httpx",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            ],
            "examples": [
                {
                    "q": "Python发送HTTP GET请求",
                    "a": "import requests\nresponse = requests.get('https://api.example.com/data')\ndata = response.json()  # 解析JSON\nprint(response.status_code)  # 状态码",
                },
                {
                    "q": "Python发送POST请求带JSON",
                    "a": "import requests\nresponse = requests.post(\n    'https://api.example.com/data',\n    json={'key': 'value'},\n    headers={'Authorization': 'Bearer token'}\n)\nresult = response.json()",
                },
            ],
        },
        "web_scraping": {
            "category": "network",
            "triggers": [
                "scrape",
                "爬虫",
                "web scraping",
                "beautifulsoup",
                "bs4",
                "selenium",
                "playwright",
                "解析网页",
                "html解析",
                "xpath",
                "css selector",
            ],
            "examples": [
                {
                    "q": "Python用BeautifulSoup解析网页",
                    "a": "import requests\nfrom bs4 import BeautifulSoup\n\nhtml = requests.get('https://example.com').text\nsoup = BeautifulSoup(html, 'html.parser')\ntitles = soup.find_all('h2')\nfor t in titles:\n    print(t.text)",
                },
            ],
        },
        "websocket": {
            "category": "network",
            "triggers": [
                "websocket",
                "ws",
                "wss",
                "长连接",
                "实时",
                "realtime",
                "socket.io",
                "订阅",
                "subscribe",
                "publish",
            ],
            "examples": [
                {
                    "q": "Python WebSocket客户端",
                    "a": "import websocket\nws = websocket.WebSocket()\nws.connect('ws://localhost:8080')\nws.send('Hello')\nresult = ws.recv()\nws.close()",
                },
            ],
        },
        # === 数据库 (4) ===
        "sql_basic": {
            "category": "database",
            "triggers": [
                "sql",
                "数据库",
                "database",
                "query",
                "查询",
                "select",
                "insert",
                "update",
                "delete",
                "where",
                "join",
                "group by",
                "order by",
                "having",
                "limit",
                "索引",
                "index",
            ],
            "examples": [
                {
                    "q": "SQL常用查询语句",
                    "a": "SELECT * FROM users WHERE age > 18 ORDER BY name;\nSELECT name, COUNT(*) FROM orders GROUP BY user_id HAVING COUNT(*) > 5;\nSELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id;",
                },
            ],
        },
        "sqlite": {
            "category": "database",
            "triggers": [
                "sqlite",
                "轻量数据库",
                "sqlite3",
                "嵌入式数据库",
            ],
            "examples": [
                {
                    "q": "Python操作SQLite数据库",
                    "a": "import sqlite3\nconn = sqlite3.connect('app.db')\ncursor = conn.cursor()\ncursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)')\ncursor.execute('INSERT INTO users (name) VALUES (?)', ('Alice',))\nconn.commit()\ncursor.execute('SELECT * FROM users')\nrows = cursor.fetchall()\nconn.close()",
                },
            ],
        },
        "orm": {
            "category": "database",
            "triggers": [
                "orm",
                "sqlalchemy",
                "peewee",
                "django orm",
                "模型",
                "migration",
                "迁移",
                "alembic",
            ],
            "examples": [
                {
                    "q": "SQLAlchemy基本用法",
                    "a": "from sqlalchemy import create_engine, Column, Integer, String\nfrom sqlalchemy.orm import declarative_base, sessionmaker\n\nBase = declarative_base()\nclass User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    name = Column(String)\n\nengine = create_engine('sqlite:///app.db')\nBase.metadata.create_all(engine)\nSession = sessionmaker(bind=engine)\nsession = Session()",
                },
            ],
        },
        "redis": {
            "category": "database",
            "triggers": [
                "redis",
                "缓存",
                "cache",
                "key-value",
                "发布订阅",
                "pub/sub",
                "set",
                "get",
                "expire",
            ],
            "examples": [
                {
                    "q": "Python操作Redis",
                    "a": "import redis\nr = redis.Redis(host='localhost', port=6379, db=0)\nr.set('key', 'value')\nvalue = r.get('key').decode()\nr.expire('key', 3600)  # 1小时过期\nr.delete('key')",
                },
            ],
        },
        # === 测试 (1) ===
        "test_write": {
            "category": "testing",
            "triggers": [
                "test",
                "测试",
                "pytest",
                "unittest",
                "单元测试",
                "assert",
                "断言",
                "fixture",
                "mock",
                "patch",
                "覆盖率",
                "coverage",
                "集成测试",
                "integration",
            ],
            "examples": [
                {
                    "q": "用pytest写单元测试",
                    "a": "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n    assert add(0, 0) == 0\n\ndef test_add_type_error():\n    with pytest.raises(TypeError):\n        add('a', 1)\n\n# 运行: pytest test_file.py -v",
                },
            ],
        },
        # === 错误处理与调试 (2) ===
        "error_handling": {
            "category": "error_handling",
            "triggers": [
                "error",
                "错误",
                "异常",
                "exception",
                "try",
                "catch",
                "处理错误",
                "报错",
                "raise",
                "throw",
                "finally",
                "context manager",
                "上下文管理器",
                "with语句",
            ],
            "examples": [
                {
                    "q": "Python错误处理最佳实践",
                    "a": 'try:\n    result = risky_operation()\nexcept ValueError as e:\n    print(f"值错误: {e}")\nexcept FileNotFoundError:\n    print("文件不存在")\nexcept Exception as e:\n    print(f"未知错误: {e}")\nelse:\n    print("成功")  # 无异常时执行\nfinally:\n    cleanup()  # 总是执行',
                },
            ],
        },
        "debugging": {
            "category": "debugging",
            "triggers": [
                "debug",
                "调试",
                "pdb",
                "breakpoint",
                "断点",
                "traceback",
                "堆栈",
                "stack trace",
                "print debug",
                "单步",
                "step",
                "inspect",
                "检查",
            ],
            "examples": [
                {
                    "q": "Python调试技巧",
                    "a": "# 1. 使用breakpoint()\ndef func(x):\n    breakpoint()  # 进入pdb\n    return x * 2\n\n# 2. pdb命令: n(下一步), s(进入), c(继续), p(打印), q(退出)\n\n# 3. 使用logging代替print\nimport logging; logging.basicConfig(level=logging.DEBUG)\nlogging.debug(f'x={x}')",
                },
            ],
        },
        # === OOP与设计模式 (2) ===
        "class_design": {
            "category": "oop",
            "triggers": [
                "class",
                "类",
                "对象",
                "object",
                "面向对象",
                "oop",
                "封装",
                "继承",
                "多态",
                "property",
                "staticmethod",
                "classmethod",
                "self",
                "__init__",
                "构造函数",
            ],
            "examples": [
                {
                    "q": "Python写一个类",
                    "a": 'class Person:\n    def __init__(self, name: str, age: int):\n        self.name = name\n        self.age = age\n\n    def greet(self) -> str:\n        return f"Hi, I\'m {self.name}, {self.age} years old."\n\n    def __repr__(self) -> str:\n        return f"Person(name={self.name!r}, age={self.age})"\n\n# 使用\np = Person("Alice", 30)\nprint(p.greet())',
                },
            ],
        },
        "design_patterns": {
            "category": "oop",
            "triggers": [
                "设计模式",
                "pattern",
                "单例",
                "singleton",
                "工厂",
                "factory",
                "观察者",
                "observer",
                "策略",
                "strategy",
                "装饰器模式",
                "适配器",
                "adapter",
                "模板方法",
                "template method",
                "建造者",
                "builder",
                "代理",
                "proxy",
            ],
            "examples": [
                {
                    "q": "Python单例模式",
                    "a": "class Singleton:\n    _instance = None\n    def __new__(cls, *args, **kwargs):\n        if not cls._instance:\n            cls._instance = super().__new__(cls)\n        return cls._instance",
                },
            ],
        },
        # === Python基础 (2) ===
        "list_comprehension": {
            "category": "python_basics",
            "triggers": [
                "list comprehension",
                "列表推导",
                "列表生成",
                "dict comprehension",
                "字典推导",
                "set comprehension",
                "generator",
                "生成器",
                "yield",
                "map",
                "filter",
                "lambda",
                "匿名函数",
                "enumerate",
                "zip",
            ],
            "examples": [
                {
                    "q": "Python列表推导式",
                    "a": "# 基础\nsquares = [x**2 for x in range(10)]\n# 带条件\nevens = [x for x in range(20) if x % 2 == 0]\n# 字典推导\nword_len = {w: len(w) for w in ['hello', 'world']}\n# 生成器表达式\nsum(x**2 for x in range(100))",
                },
            ],
        },
        "type_hints": {
            "category": "python_basics",
            "triggers": [
                "type hint",
                "类型注解",
                "typing",
                "Optional",
                "Union",
                "List",
                "Dict",
                "类型提示",
                "Tuple",
                "Callable",
                "Any",
                "Generic",
                "Protocol",
            ],
            "examples": [
                {
                    "q": "Python类型注解示例",
                    "a": 'from typing import Optional, Union\n\ndef greet(name: str, age: int = 0) -> str:\n    return f"Hello {name}"\n\ndef find_user(user_id: int) -> Optional[dict]:\n    return users.get(user_id)\n\ndef process(value: Union[int, str]) -> str:\n    return str(value)',
                },
            ],
        },
        # === Python高级 (3) ===
        "decorator": {
            "category": "python_advanced",
            "triggers": [
                "decorator",
                "装饰器",
                "wrapper",
                "wraps",
                "functools",
                "高阶函数",
                "闭包",
                "closure",
            ],
            "examples": [
                {
                    "q": "Python写一个装饰器",
                    "a": 'from functools import wraps\nimport time\n\ndef timer(func):\n    @wraps(func)\n    def wrapper(*args, **kwargs):\n        start = time.time()\n        result = func(*args, **kwargs)\n        print(f"{func.__name__} took {time.time()-start:.2f}s")\n        return result\n    return wrapper\n\n@timer\ndef slow_func():\n    time.sleep(1)',
                },
            ],
        },
        "async_await": {
            "category": "python_advanced",
            "triggers": [
                "async",
                "await",
                "异步",
                "asyncio",
                "并发",
                "concurrent",
                "coroutine",
                "协程",
                "event loop",
                "事件循环",
                "aiohttp",
                "async for",
                "async with",
            ],
            "examples": [
                {
                    "q": "Python异步编程示例",
                    "a": 'import asyncio\n\nasync def fetch_data(url):\n    await asyncio.sleep(1)\n    return f"Data from {url}"\n\nasync def main():\n    tasks = [fetch_data(url) for url in urls]\n    results = await asyncio.gather(*tasks)\n    return results\n\nasyncio.run(main())',
                },
            ],
        },
        "context_manager": {
            "category": "python_advanced",
            "triggers": [
                "context manager",
                "上下文管理器",
                "with",
                "enter",
                "exit",
                "contextlib",
                "resource management",
                "资源管理",
            ],
            "examples": [
                {
                    "q": "Python自定义上下文管理器",
                    "a": "from contextlib import contextmanager\n\n@contextmanager\ndef managed_resource():\n    resource = acquire()\n    try:\n        yield resource\n    finally:\n        release(resource)\n\n# 使用\nwith managed_resource() as r:\n    r.do_work()",
                },
            ],
        },
        # === Shell与系统 (2) ===
        "shell_command": {
            "category": "shell",
            "triggers": [
                "shell",
                "命令",
                "command",
                "bash",
                "终端",
                "terminal",
                "脚本",
                "script",
                "chmod",
                "ls",
                "grep",
                "find",
                "awk",
                "sed",
                "pipe",
                "管道",
                "重定向",
                "subprocess",
            ],
            "examples": [
                {
                    "q": "常用Linux命令",
                    "a": "ls -la                  # 列出文件（含隐藏）\nfind . -name '*.py'     # 查找Python文件\ngrep -r 'pattern' .     # 递归搜索\ncat file | sort | uniq  # 排序去重\nchmod +x script.sh      # 添加执行权限\ntail -f log.txt         # 实时查看日志\ndf -h                   # 磁盘使用",
                },
            ],
        },
        "subprocess": {
            "category": "shell",
            "triggers": [
                "subprocess",
                "子进程",
                "执行命令",
                "run command",
                "os.system",
                "Popen",
                "capture output",
                "管道输出",
            ],
            "examples": [
                {
                    "q": "Python执行shell命令",
                    "a": "import subprocess\n# 推荐方式\nresult = subprocess.run(['ls', '-la'], capture_output=True, text=True)\nprint(result.stdout)\nprint(result.returncode)\n\n# 带超时\nresult = subprocess.run(['cmd'], timeout=10)",
                },
            ],
        },
        # === 配置与环境 (2) ===
        "env_vars": {
            "category": "configuration",
            "triggers": [
                "env",
                "环境变量",
                "environment",
                "dotenv",
                ".env",
                "config",
                "配置",
                "secret",
                "密钥",
                "os.environ",
                "os.getenv",
            ],
            "examples": [
                {
                    "q": "Python读取环境变量",
                    "a": "import os\n# 读取环境变量\napi_key = os.environ.get('API_KEY', 'default')\ndb_url = os.getenv('DATABASE_URL')\n\n# 使用python-dotenv\nfrom dotenv import load_dotenv\nload_dotenv()  # 加载.env文件\napi_key = os.environ['API_KEY']",
                },
            ],
        },
        "logging": {
            "category": "logging_monitoring",
            "triggers": [
                "log",
                "日志",
                "logging",
                "debug",
                "info",
                "warn",
                "error",
                "记录",
                "logger",
                "handler",
                "formatter",
                "log file",
                "日志文件",
                "轮转",
                "rotation",
            ],
            "examples": [
                {
                    "q": "Python日志配置",
                    "a": "import logging\nlogging.basicConfig(\n    level=logging.INFO,\n    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',\n    handlers=[\n        logging.FileHandler('app.log'),\n        logging.StreamHandler()\n    ]\n)\nlogger = logging.getLogger(__name__)\nlogger.info('App started')\nlogger.error('Something went wrong', exc_info=True)",
                },
            ],
        },
        # === 安全 (1) ===
        "security": {
            "category": "security",
            "triggers": [
                "加密",
                "解密",
                "encrypt",
                "decrypt",
                "hash",
                "密码",
                "password",
                "token",
                "jwt",
                "认证",
                "auth",
                "authorization",
                "bcrypt",
                "hashlib",
                "hmac",
                "ssl",
                "https",
            ],
            "examples": [
                {
                    "q": "Python密码哈希存储",
                    "a": "import bcrypt\n# 哈希化\npassword = b'my_secret'\nhashed = bcrypt.hashpw(password, bcrypt.gensalt())\n# 验证\nif bcrypt.checkpw(password, hashed):\n    print('Match')",
                },
            ],
        },
        # === 日期时间 (1) ===
        "datetime": {
            "category": "datetime",
            "triggers": [
                "date",
                "时间",
                "datetime",
                "timestamp",
                "时区",
                "timezone",
                "格式化日期",
                "strptime",
                "strftime",
                "timedelta",
                "时间差",
                "UTC",
                "now",
            ],
            "examples": [
                {
                    "q": "Python日期时间操作",
                    "a": "from datetime import datetime, timedelta\nnow = datetime.now()\nformatted = now.strftime('%Y-%m-%d %H:%M:%S')\nparsed = datetime.strptime('2024-01-01', '%Y-%m-%d')\ntomorrow = now + timedelta(days=1)\ndiff = now - parsed  # timedelta",
                },
            ],
        },
        # === 性能优化 (1) ===
        "performance": {
            "category": "performance",
            "triggers": [
                "性能",
                "performance",
                "profile",
                "基准",
                "benchmark",
                "内存泄漏",
                "memory leak",
                "优化",
                "optimize",
                "cProfile",
                "timeit",
                "缓存",
                "cache",
                "lru_cache",
                "慢",
                "slow",
                "加速",
                "fast",
            ],
            "examples": [
                {
                    "q": "Python性能优化技巧",
                    "a": "from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef expensive_func(n):\n    return n * 2  # 结果会被缓存\n\n# 使用timeit测量\nimport timeit\ntimeit.timeit('sum(range(1000))', number=1000)\n\n# 使用cProfile分析\nimport cProfile\ncProfile.run('my_function()')",
                },
            ],
        },
        # === 代码质量 (1) ===
        "code_quality": {
            "category": "code_quality",
            "triggers": [
                "lint",
                "pep8",
                "格式化",
                "format",
                "black",
                "flake8",
                "ruff",
                "mypy",
                "类型检查",
                "代码规范",
                "code style",
                "docstring",
                "文档字符串",
                "注释",
                "comment",
            ],
            "examples": [
                {
                    "q": "Python代码规范",
                    "a": '# 使用ruff检查和格式化\n# ruff check . && ruff format .\n\n# 使用mypy类型检查\n# mypy my_code.py\n\n# 好的docstring示例\ndef add(a: int, b: int) -> int:\n    """Add two integers.\n\n    Args:\n        a: First integer\n        b: Second integer\n\n    Returns:\n        Sum of a and b\n    """\n    return a + b',
                },
            ],
        },
        # === DevOps (2) ===
        "docker_basic": {
            "category": "devops",
            "triggers": [
                "docker",
                "容器",
                "container",
                "image",
                "镜像",
                "Dockerfile",
                "compose",
                "docker-compose",
                "volume",
                "network",
                "registry",
                "hub",
            ],
            "examples": [
                {
                    "q": "Docker常用命令",
                    "a": "docker build -t myapp .     # 构建镜像\ndocker run -p 8080:80 myapp  # 运行容器\ndocker ps                    # 查看运行中的容器\ndocker images                # 查看镜像\ndocker stop <container_id>   # 停止容器\ndocker logs <container_id>   # 查看日志\ndocker-compose up -d         # 启动compose",
                },
            ],
        },
        "ci_cd": {
            "category": "devops",
            "triggers": [
                "ci",
                "cd",
                "pipeline",
                "流水线",
                "github actions",
                "gitlab ci",
                "jenkins",
                "自动化部署",
                "deploy",
                "workflow",
                "yaml ci",
            ],
            "examples": [
                {
                    "q": "GitHub Actions基本用法",
                    "a": "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: pip install -e .\n      - run: pytest",
                },
            ],
        },
        # === 包管理 (1) ===
        "package_management": {
            "category": "package_management",
            "triggers": [
                "pip",
                "依赖",
                "dependency",
                "requirement",
                "requirements.txt",
                "virtualenv",
                "venv",
                "conda",
                "uv",
                "poetry",
                "安装包",
                "install",
                "upgrade",
                "uninstall",
                "pyproject.toml",
                "setup.py",
            ],
            "examples": [
                {
                    "q": "Python虚拟环境和包管理",
                    "a": "# 创建虚拟环境\npython -m venv venv\nsource venv/bin/activate  # Linux/Mac\n# venv\\Scripts\\activate   # Windows\n\n# 安装包\npip install requests\npip install -r requirements.txt\npip install -e .  # 可编辑安装\n\n# 导出依赖\npip freeze > requirements.txt",
                },
            ],
        },
        # === CLI开发 (1) ===
        "cli_dev": {
            "category": "cli_dev",
            "triggers": [
                "cli",
                "命令行",
                "argparse",
                "click",
                "参数解析",
                "subcommand",
                "子命令",
                "rich console",
                "typer",
                "命令行工具",
                "command line",
            ],
            "examples": [
                {
                    "q": "Python用argparse写CLI",
                    "a": "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('name', help='Your name')\nparser.add_argument('-v', '--verbose', action='store_true')\nargs = parser.parse_args()\nprint(f'Hello {args.name}')",
                },
            ],
        },
        # === Web开发 (1) ===
        "web_api": {
            "category": "web_dev",
            "triggers": [
                "flask",
                "fastapi",
                "django",
                "web框架",
                "路由",
                "route",
                "endpoint",
                "rest api",
                "restful",
                "middleware",
                "cors",
                "gunicorn",
                "uvicorn",
            ],
            "examples": [
                {
                    "q": "FastAPI基本示例",
                    "a": "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'message': 'Hello'}\n\n@app.get('/users/{user_id}')\ndef get_user(user_id: int):\n    return {'id': user_id}\n\n# 运行: uvicorn main:app --reload",
                },
            ],
        },
        # === 数学与统计 (1) ===
        "math_stats": {
            "category": "math_stats",
            "triggers": [
                "数学",
                "math",
                "统计",
                "statistics",
                "概率",
                "probability",
                "公式",
                "formula",
                "计算",
                "calculate",
                "mean",
                "average",
                "标准差",
                "std",
                "方差",
                "variance",
                "中位数",
                "median",
                "numpy",
                "矩阵",
                "matrix",
                "向量",
                "vector",
            ],
            "examples": [
                {
                    "q": "Python计算统计值",
                    "a": "import statistics\ndata = [1, 2, 3, 4, 5]\nstatistics.mean(data)     # 平均值\nstatistics.median(data)   # 中位数\nstatistics.stdev(data)    # 标准差\nstatistics.variance(data) # 方差\n\n# 或用numpy\nimport numpy as np\narr = np.array(data)\narr.mean(), arr.std()",
                },
            ],
        },
        # === 代码解释与审查 (2) ===
        "code_explanation": {
            "category": "code_explanation",
            "triggers": [
                "解释",
                "说明",
                "什么意思",
                "what does",
                "how does",
                "这段代码",
                "this code",
                "理解",
                "understand",
                "讲解",
                "explain",
                "原理",
                "principle",
            ],
            "examples": [
                {
                    "q": "解释这段Python代码",
                    "a": "分析代码时关注以下几点：\n1. 输入输出：函数接收什么参数，返回什么\n2. 核心逻辑：主要算法或流程\n3. 边界情况：空值、异常处理\n4. 复杂度：时间/空间复杂度\n5. 改进建议：更简洁或高效的写法",
                },
            ],
        },
        "code_review": {
            "category": "code_review",
            "triggers": [
                "优化",
                "优化建议",
                "改进",
                "better way",
                "更优雅",
                "best practice",
                "最佳实践",
                "重构",
                "refactor",
                "code review",
                "代码审查",
                "review",
            ],
            "examples": [
                {
                    "q": "这段代码怎么优化",
                    "a": "代码优化检查清单：\n1. 命名是否清晰有意义\n2. 是否有重复代码可提取函数\n3. 是否可以用内置函数/库替代\n4. 错误处理是否完善\n5. 类型注解是否完整\n6. 是否有不必要的计算\n7. 数据结构选择是否最优",
                },
            ],
        },
        # === 系统信息 (1) ===
        "system_info": {
            "category": "system_info",
            "triggers": [
                "系统信息",
                "system info",
                "platform",
                "cpu",
                "内存",
                "memory",
                "disk",
                "磁盘",
                "操作系统",
                "os",
                "版本",
                "version",
                "python版本",
                "python version",
            ],
            "examples": [
                {
                    "q": "Python获取系统信息",
                    "a": "import platform\nimport os\nprint(f'OS: {platform.system()} {platform.release()}')\nprint(f'Python: {platform.python_version()}')\nprint(f'Machine: {platform.machine()}')\nprint(f'CPU count: {os.cpu_count()}')\nprint(f'CWD: {os.getcwd()}')",
                },
            ],
        },
        # === 机器学习基础 (1) ===
        "ml_basics": {
            "category": "machine_learning",
            "triggers": [
                "机器学习",
                "machine learning",
                "训练",
                "train",
                "模型",
                "model",
                "训练集",
                "test set",
                "测试集",
                "accuracy",
                "准确率",
                "sklearn",
                "scikit-learn",
                "fit",
                "predict",
                "pipeline",
            ],
            "examples": [
                {
                    "q": "sklearn基本用法",
                    "a": "from sklearn.model_selection import train_test_split\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import accuracy_score\n\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\nmodel = RandomForestClassifier()\nmodel.fit(X_train, y_train)\npredictions = model.predict(X_test)\nprint(accuracy_score(y_test, predictions))",
                },
            ],
        },
    }
