#!/usr/bin/env rypython
import sys
import os
import re
from pathlib import Path


def get_ruyi_python():
    if sys.platform == 'win32':
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


def validate_skill(skill_path):
    skill_path = Path(skill_path)

    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md 未找到"

    content = skill_md.read_text(encoding='utf-8')
    if not content.startswith('---'):
        return False, "缺少 YAML frontmatter"

    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "frontmatter 格式无效"

    frontmatter_text = match.group(1)

    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                return False, "frontmatter 必须是 YAML 字典"
        except yaml.YAMLError as e:
            return False, f"frontmatter YAML 解析错误: {e}"
    else:
        frontmatter = {}
        for line in frontmatter_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    ALLOWED_PROPERTIES = {'name', 'description', 'category', 'toolsets', 'tools',
                          'preset_questions', 'metadata', 'compatibility', 'agent_id'}

    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"frontmatter 中存在未识别的字段: {', '.join(sorted(unexpected_keys))}。"
            f"允许的字段: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    if 'name' not in frontmatter:
        return False, "缺少 'name' 字段"
    if 'description' not in frontmatter:
        return False, "缺少 'description' 字段"

    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"name 必须是字符串，当前类型: {type(name).__name__}"
    name = name.strip()
    if name:
        if not re.match(r'^[a-z0-9_\-\u4e00-\u9fff]+$', name):
            return False, f"name '{name}' 格式不正确，应使用小写字母、数字、连字符或下划线"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"name '{name}' 不能以连字符开头/结尾或包含连续连字符"
        if len(name) > 64:
            return False, f"name 过长（{len(name)} 字符），最大64字符"

    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"description 必须是字符串，当前类型: {type(description).__name__}"
    description = description.strip()
    if description:
        if '<' in description or '>' in description:
            return False, "description 不能包含尖括号（< 或 >）"
        if len(description) > 1024:
            return False, f"description 过长（{len(description)} 字符），最大1024字符"

    body_match = re.match(r'^---\n.*?\n---\s*\n(.*)', content, re.DOTALL)
    if body_match:
        body = body_match.group(1).strip()
        if not body:
            return False, "SKILL.md 正文为空，技能需要包含操作指令"
        if len(body) < 50:
            return False, f"SKILL.md 正文过短（{len(body)} 字符），技能指令不够详细"

    return True, "技能格式验证通过！"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: rypython quick_validate.py <技能目录>  (Linux)")
        print("用法: <python_path>\\python.exe quick_validate.py <技能目录>  (Windows)")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
