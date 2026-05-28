#!/usr/bin/env rypython
import os
import re
from pathlib import Path


def get_ruyi_python():
    if os.name == 'nt':
        base_dir = _find_ruyi_root()
        if base_dir:
            python_path_file = os.path.join(base_dir, 'data', 'python_path.ry')
            if os.path.exists(python_path_file):
                with open(python_path_file, 'r') as f:
                    py_dir = f.read().strip()
                if py_dir:
                    return os.path.join(py_dir, 'python.exe')
        return 'python'
    else:
        return 'rypython'


def _find_ruyi_root():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / 'ruyi' / 'settings.py').exists():
            return str(current)
        if (current / 'data' / 'python_path.ry').exists() and (current / 'manage.py').exists():
            return str(current)
        current = current.parent
    return None


def parse_skill_md(skill_path):
    content = (Path(skill_path) / "SKILL.md").read_text(encoding='utf-8')
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md 缺少 frontmatter（没有开头的 ---）")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md 缺少 frontmatter（没有结尾的 ---）")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value in (">", "|", ">-", "|-"):
                continuation_lines = []
                i += 1
                while i < len(frontmatter_lines) and (
                    frontmatter_lines[i].startswith("  ")
                    or frontmatter_lines[i].startswith("\t")
                ):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content


def find_skill_creator_dir():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "SKILL.md").exists():
            return current
        current = current.parent
    return None
