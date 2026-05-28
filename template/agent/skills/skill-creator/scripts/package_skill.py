#!/usr/bin/env rypython
import fnmatch
import sys
import os
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quick_validate import validate_skill

EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
ROOT_EXCLUDE_DIRS = {"evals"}


def should_exclude(rel_path):
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def package_skill(skill_path, output_dir=None):
    skill_path = Path(skill_path).resolve()

    if not skill_path.exists():
        print(f"错误: 技能目录不存在: {skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"错误: 路径不是目录: {skill_path}")
        return None

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"错误: 未找到 SKILL.md: {skill_path}")
        return None

    print("验证技能格式...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"验证失败: {message}")
        print("请修复验证错误后再打包。")
        return None
    print(f"{message}\n")

    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = skill_path.parent

    skill_filename = output_path / f"{skill_name}.zip"

    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in skill_path.rglob('*'):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  跳过: {arcname}")
                    continue
                zipf.write(file_path, arcname)
                print(f"  添加: {arcname}")

        print(f"\n技能打包成功: {skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"打包失败: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: rypython package_skill.py <技能目录> [输出目录]  (Linux)")
        print("用法: <python_path>\\python.exe package_skill.py <技能目录> [输出目录]  (Windows)")
        print("\n示例:")
        print("  rypython package_skill.py data/agent/skills/my-skill")
        print("  rypython package_skill.py data/agent/skills/my-skill ./dist")
        sys.exit(1)

    skill_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"打包技能: {skill_path}")
    if output_dir:
        print(f"输出目录: {output_dir}")
    print()

    result = package_skill(skill_path, output_dir)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)
