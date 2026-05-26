import os
import re
import json
import logging
import platform
from typing import Dict, Any, Optional
from apps.sysai.tools.base import register_tool
from apps.sysai.skills import skill_manager

logger = logging.getLogger(__name__)


def _get_skill_manage_doc():
    return """技能管理工具，用于自主创建、修改、删除和改进技能。这是你的程序性记忆——当你完成了一个复杂任务、修复了一个棘手错误、或发现了一个非平凡的工作流程时，应该将解决方案保存为技能，以便下次复用。

何时创建技能：
- 完成复杂任务（5+次工具调用）后，将成功的做法保存为技能
- 修复了一个棘手错误后，将排查过程和解决方案保存为技能
- 发现了一个非平凡的工作流程，值得未来复用
- 用户纠正了你的做法后，更新相关技能

何时改进技能：
- 使用技能时发现步骤过时或不完整，立即用 patch 修正
- 发现更好的操作顺序或参数
- 技能未覆盖的边界情况

何时不创建技能：
- 简单的单步操作（如查看状态）
- 通用知识（如Linux基本命令）
- 一次性的、不太可能重复的任务

操作说明：
- create: 创建新技能，需提供 name、content（完整SKILL.md内容），可选 description、trigger_keywords、platforms
- patch: 局部修改技能（推荐），需提供 name、old_string、new_string，仅替换匹配的文本
- edit: 完整替换技能内容，需提供 name、content（完整SKILL.md内容）
- delete: 删除技能，需提供 name
- write_file: 为技能添加辅助文件，需提供 name、file_path、file_content
- remove_file: 删除技能的辅助文件，需提供 name、file_path

SKILL.md 格式规范：
```
---
name: 技能名称（英文，kebab-case）
description: 一句话描述技能功能
trigger_keywords: 关键词1,关键词2,关键词3
platforms: linux,windows
source: learned
---

# 技能标题

## 适用场景
什么情况下使用此技能

## 操作步骤
1. 第一步
2. 第二步

## 注意事项
- 已知的坑和解决方案

## 验证方法
如何确认操作成功
```

Args:
    action: 操作类型，可选值: create, patch, edit, delete, write_file, remove_file
    name: 技能名称（kebab-case格式，如 nginx-troubleshoot）
    content: SKILL.md完整内容（create/edit时使用）
    description: 技能简短描述（create时可选，如未提供则从content中提取）
    trigger_keywords: 触发关键词，逗号分隔（create时可选，如: nginx故障,网站502,反向代理）
    platforms: 适用平台，逗号分隔（create时可选，如: linux,windows。不填则全平台适用）
    old_string: 要替换的旧文本（patch时使用）
    new_string: 替换后的新文本（patch时使用）
    file_path: 辅助文件相对路径（write_file/remove_file时使用，如 scripts/check.sh）
    file_content: 辅助文件内容（write_file时使用）
"""


class SkillManage:
    __name__ = 'skill_manage'

    @property
    def __doc__(self):
        return _get_skill_manage_doc()

    def __call__(self, action: str, name: str = '', content: str = '',
                 description: str = '', trigger_keywords: str = '',
                 platforms: str = '', old_string: str = '',
                 new_string: str = '', file_path: str = '',
                 file_content: str = '') -> str:
        return self.execute(action, name, content, description,
                            trigger_keywords, platforms, old_string,
                            new_string, file_path, file_content)

    def execute(self, action: str, name: str = '', content: str = '',
                description: str = '', trigger_keywords: str = '',
                platforms: str = '', old_string: str = '',
                new_string: str = '', file_path: str = '',
                file_content: str = '') -> str:
        action = (action or '').strip().lower()
        name = (name or '').strip()

        if action not in ('create', 'patch', 'edit', 'delete', 'write_file', 'remove_file'):
            return self._error(f'不支持的操作类型: {action}，可选值: create, patch, edit, delete, write_file, remove_file')

        if action == 'create':
            return self._create(name, content, description, trigger_keywords, platforms)
        elif action == 'patch':
            return self._patch(name, old_string, new_string)
        elif action == 'edit':
            return self._edit(name, content)
        elif action == 'delete':
            return self._delete(name)
        elif action == 'write_file':
            return self._write_file(name, file_path, file_content)
        elif action == 'remove_file':
            return self._remove_file(name, file_path)

    def _create(self, name: str, content: str, description: str,
                trigger_keywords: str, platforms: str) -> str:
        if not name:
            return self._error('技能名称不能为空')
        if not content:
            return self._error('技能内容不能为空')

        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$', name):
            return self._error(f'技能名称格式无效: {name}，仅支持字母、数字、下划线、横线和中文')

        existing = skill_manager.get(name)
        if existing and existing.metadata.get('_source') == 'builtin':
            return self._error(f'内置技能 [{name}] 不能覆盖，请使用不同的名称')

        if not content.strip().startswith('---'):
            kw_str = trigger_keywords.strip()
            pf_str = platforms.strip()
            current_platform = platform.system().lower()
            if current_platform == 'darwin':
                current_platform = 'macos'

            frontmatter_lines = [
                '---',
                f'name: {name}',
                f'description: {description or self._extract_description(content)}',
            ]
            if kw_str:
                frontmatter_lines.append(f'trigger_keywords: {kw_str}')
            if pf_str:
                frontmatter_lines.append(f'platforms: {pf_str}')
            frontmatter_lines.append('source: learned')
            frontmatter_lines.append('---')
            frontmatter = '\n'.join(frontmatter_lines)
            content = frontmatter + '\n\n' + content
        else:
            parsed_meta, _ = skill_manager._parse_frontmatter(content)
            if 'source' not in parsed_meta:
                content = content.replace('---\n', '---\nsource: learned\n', 1)

        result = skill_manager.import_skill_from_content(name, content, description)
        if result.get('status'):
            try:
                from apps.sysai.agent.skill_evolution import skill_evolution
                skill_evolution.record_skill_created(name, trigger_keywords)
            except Exception:
                pass

            logger.info(f'技能 [{name}] 创建成功')
            return self._success(f'技能 [{name}] 创建成功。下次遇到类似任务时，系统会自动激活此技能。')
        return self._error(f'技能创建失败: {result.get("msg", "未知错误")}')

    def _patch(self, name: str, old_string: str, new_string: str) -> str:
        if not name:
            return self._error('技能名称不能为空')
        if not old_string:
            return self._error('要替换的旧文本不能为空')

        skill = skill_manager.get(name)
        if not skill:
            return self._error(f'技能 [{name}] 不存在')

        if skill.metadata.get('_source') == 'builtin':
            return self._error(f'内置技能 [{name}] 不能直接修改')

        skill_md_path = skill.location
        if not os.path.exists(skill_md_path):
            return self._error(f'技能文件不存在: {skill_md_path}')

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            return self._error(f'读取技能文件失败: {e}')

        if old_string not in file_content:
            return self._error(f'在技能 [{name}] 中未找到要替换的文本。请检查 old_string 是否完全匹配（包括空格和换行）。')

        count = file_content.count(old_string)
        if count > 1:
            return self._error(f'在技能 [{name}] 中找到 {count} 处匹配，请提供更精确的 old_string 以确保唯一匹配。')

        new_content = file_content.replace(old_string, new_string, 1)

        try:
            with open(skill_md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error(f'写入技能文件失败: {e}')

        try:
            from apps.sysai.agent.skill_evolution import skill_evolution
            skill_evolution.record_skill_refined(name, 'patch')
        except Exception:
            pass

        logger.info(f'技能 [{name}] patch修改成功')
        return self._success(f'技能 [{name}] 已更新（patch模式）')

    def _edit(self, name: str, content: str) -> str:
        if not name:
            return self._error('技能名称不能为空')
        if not content:
            return self._error('技能内容不能为空')

        skill = skill_manager.get(name)
        if not skill:
            return self._error(f'技能 [{name}] 不存在')

        if skill.metadata.get('_source') == 'builtin':
            return self._error(f'内置技能 [{name}] 不能直接修改')

        result = skill_manager.import_skill_from_content(name, content)
        if result.get('status'):
            try:
                from apps.sysai.agent.skill_evolution import skill_evolution
                skill_evolution.record_skill_refined(name, 'edit')
            except Exception:
                pass

            logger.info(f'技能 [{name}] edit修改成功')
            return self._success(f'技能 [{name}] 已完整更新（edit模式）')
        return self._error(f'技能更新失败: {result.get("msg", "未知错误")}')

    def _delete(self, name: str) -> str:
        if not name:
            return self._error('技能名称不能为空')

        skill = skill_manager.get(name)
        if not skill:
            return self._error(f'技能 [{name}] 不存在')

        if skill.metadata.get('_source') == 'builtin':
            return self._error(f'内置技能 [{name}] 不能删除，只能禁用')

        result = skill_manager.delete_skill(name)
        if result.get('status'):
            logger.info(f'技能 [{name}] 已删除')
            return self._success(f'技能 [{name}] 已删除')
        return self._error(f'技能删除失败: {result.get("msg", "未知错误")}')

    def _write_file(self, name: str, file_path: str, file_content: str) -> str:
        if not name:
            return self._error('技能名称不能为空')
        if not file_path:
            return self._error('文件路径不能为空')
        if not file_content:
            return self._error('文件内容不能为空')

        skill = skill_manager.get(name)
        if not skill:
            return self._error(f'技能 [{name}] 不存在')

        skill_dir = os.path.dirname(skill.location)

        safe_path = file_path.replace('\\', '/').lstrip('/')
        if '..' in safe_path.split('/'):
            return self._error('文件路径不能包含 ..')

        full_path = os.path.join(skill_dir, safe_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
        except Exception as e:
            return self._error(f'写入文件失败: {e}')

        if safe_path.endswith('.sh'):
            try:
                os.chmod(full_path, 0o755)
            except Exception:
                pass

        logger.info(f'技能 [{name}] 辅助文件 [{safe_path}] 写入成功')
        return self._success(f'技能 [{name}] 辅助文件 [{safe_path}] 已创建')

    def _remove_file(self, name: str, file_path: str) -> str:
        if not name:
            return self._error('技能名称不能为空')
        if not file_path:
            return self._error('文件路径不能为空')

        skill = skill_manager.get(name)
        if not skill:
            return self._error(f'技能 [{name}] 不存在')

        skill_dir = os.path.dirname(skill.location)
        safe_path = file_path.replace('\\', '/').lstrip('/')
        if '..' in safe_path.split('/'):
            return self._error('文件路径不能包含 ..')

        full_path = os.path.join(skill_dir, safe_path)
        if not os.path.exists(full_path):
            return self._error(f'文件不存在: {safe_path}')

        if os.path.dirname(full_path) == skill_dir and os.path.basename(full_path) == 'SKILL.md':
            return self._error('不能删除 SKILL.md 主文件')

        try:
            os.remove(full_path)
        except Exception as e:
            return self._error(f'删除文件失败: {e}')

        logger.info(f'技能 [{name}] 辅助文件 [{safe_path}] 已删除')
        return self._success(f'技能 [{name}] 辅助文件 [{safe_path}] 已删除')

    def _extract_description(self, content: str) -> str:
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('---'):
                return line[:200]
        return ''

    def _success(self, msg: str) -> str:
        return f'<tool>\n<tool_name>skill_manage</tool_name>\n<toolcall_status>done</toolcall_status>\n<toolcall_result>\n{msg}\n</toolcall_result>\n</tool>'

    def _error(self, msg: str) -> str:
        return f'<tool>\n<tool_name>skill_manage</tool_name>\n<toolcall_status>error</toolcall_status>\n<toolcall_result>\n{msg}\n</toolcall_result>\n</tool>'


register_tool(id='skill_manage', category='agent', name_cn='技能管理', risk_level='low')(SkillManage())
