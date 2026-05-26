import os
from apps.sysai.tools.base import register_tool
from apps.sysai.skills import skill_manager


def _get_skill_doc():
    skills = skill_manager.all_enabled()

    if not skills:
        return '管理和查看专业技能。当前没有可用的技能。'

    skill_list = '\n'.join([
        f'  <skill>\n    <name>{s.name}</name>\n    <description>{s.description}</description>\n  </skill>'
        for s in skills
    ])

    examples = ', '.join([f"'{s.name}'" for s in skills[:3]])
    hint = f' (例如: {examples} 等)' if examples else ''

    return f"""管理和查看专业技能。当用户提到"技能""skills""有哪些技能""创建技能"等关键词时，必须使用此工具。

两种用法：
1. **查看技能列表**：不传 name 参数（或 name 为空），返回所有可用技能的名称和描述
2. **加载技能指令**：传入 name 参数，加载该技能的完整指令内容

技能采用渐进式加载：
- 首次调用返回技能的核心指令（Level 1）
- 如果需要更多细节（脚本、参考文档、模板），再次调用并设置 detail=true（Level 2）

当前可用技能列表：
<available_skills>
{skill_list}
</available_skills>

当任务匹配以上可用技能时，调用此工具加载技能指令。

Args:
    name: 要加载的技能名称{hint}。不传此参数则返回所有可用技能列表。
    detail: 是否加载详细内容（脚本、参考文档等），默认false仅加载核心指令
"""


class Skills:
    __name__ = 'Skills'

    @property
    def __doc__(self):
        return _get_skill_doc()

    def __call__(self, name: str = '', detail: bool = False):
        return self.execute(name, detail)

    def execute(self, name: str = '', detail: bool = False):
        if not name or not name.strip():
            return self._list_skills()

        name = name.strip()
        skill_obj = skill_manager.get_enabled(name)

        if not skill_obj:
            target_skill = skill_manager.get(name)
            if target_skill and not skill_manager.is_enabled(name):
                return f'<tool>\n<tool_name>Skills</tool_name>\n<toolcall_status>error</toolcall_status>\n<toolcall_result>\n技能 "{name}" 已被禁用。\n</toolcall_result>\n</tool>'
            available = ', '.join([s.name for s in skill_manager.all_enabled()])
            return f'<tool>\n<tool_name>Skills</tool_name>\n<toolcall_status>error</toolcall_status>\n<toolcall_result>\n技能 "{name}" 不存在。可用技能: {available or "无"}\n</toolcall_result>\n</tool>'

        skill_dir = os.path.dirname(skill_obj.location)

        output_parts = [
            f'<skill_content name="{skill_obj.name}">',
            f'# Skill: {skill_obj.name}',
            '',
            skill_obj.content.strip(),
            '',
        ]

        if detail:
            files = skill_manager.list_files(skill_dir)
            file_list_str = '\n'.join([f'<file>{f}</file>' for f in files])
            output_parts.extend([
                f'此技能的基础目录: {skill_dir}',
                '此技能中的相对路径（如 scripts/、reference/）相对于此基础目录。',
                '',
                '<skill_files>',
                file_list_str,
                '</skill_files>',
            ])

            for ref_file in files:
                if ref_file.endswith(('.md', '.txt', '.sh', '.py', '.yaml', '.yml', '.json', '.conf')):
                    ref_path = os.path.join(skill_dir, ref_file)
                    if ref_file == 'SKILL.md':
                        continue
                    try:
                        with open(ref_path, 'r', encoding='utf-8') as f:
                            ref_content = f.read()
                        if len(ref_content) > 10000:
                            ref_content = ref_content[:10000] + '\n...[内容已截断]...'
                        output_parts.extend([
                            '',
                            f'<reference_file path="{ref_file}">',
                            ref_content,
                            '</reference_file>',
                        ])
                    except Exception:
                        pass
        else:
            output_parts.extend([
                f'此技能的基础目录: {skill_dir}',
                '如需加载技能的参考文件和脚本，请再次调用此工具并设置 detail=true',
            ])

        output_parts.append('</skill_content>')

        content = '\n'.join(output_parts)
        return f'<tool>\n<tool_name>Skills</tool_name>\n<toolcall_status>done</toolcall_status>\n<toolcall_result>\n{content}\n</toolcall_result>\n</tool>'

    def _list_skills(self):
        skills = skill_manager.all_enabled()
        if not skills:
            return '<tool>\n<tool_name>Skills</tool_name>\n<toolcall_status>done</toolcall_status>\n<toolcall_result>\n当前没有可用的技能。\n</toolcall_result>\n</tool>'

        lines = ['当前可用技能列表：', '']
        for s in skills:
            lines.append(f'- **{s.name}**: {s.description}')
        lines.append('')
        lines.append('使用 Skills 工具并传入技能名称即可加载该技能的完整指令。')

        content = '\n'.join(lines)
        return f'<tool>\n<tool_name>Skills</tool_name>\n<toolcall_status>done</toolcall_status>\n<toolcall_result>\n{content}\n</toolcall_result>\n</tool>'


register_tool(id='Skills', category='agent', name_cn='技能代理', risk_level='low')(Skills())
