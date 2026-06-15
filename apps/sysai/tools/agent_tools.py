import json
import os
import time
from typing import List, Dict, Any, Optional
from enum import Enum
from apps.sysai.tools.base import register_tool, _xml_response


class TodoStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class TodoPriority(str, Enum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class TodoItem:
    def __init__(self, content: str, status: str = 'pending',
                 id: Optional[str] = None, priority: str = 'medium'):
        self.id = id or str(int(time.time() * 1000))
        self.content = content
        self.status = status
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'status': self.status,
            'priority': self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoItem':
        return cls(
            content=data.get('content', ''),
            status=data.get('status', 'pending'),
            id=data.get('id'),
            priority=data.get('priority', 'medium'),
        )


class TodoManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'data', 'agent', 'sessions', session_id
        )
        self.file_path = os.path.join(self.session_dir, 'todos.json')
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.session_dir):
            try:
                os.makedirs(self.session_dir, exist_ok=True)
            except OSError:
                pass

    def get_todos(self) -> List[TodoItem]:
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [TodoItem.from_dict(item) for item in data]
        except Exception:
            return []

    def save_todos(self, todos: List[TodoItem]):
        data = [item.to_dict() for item in todos]
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update_todos(self, new_todos_data: List[Dict[str, Any]], merge: bool = False) -> List[TodoItem]:
        if merge:
            current_todos = self.get_todos()
            current_map = {t.id: t for t in current_todos}

            new_items = []  # 收集新增项，用于插入到正确位置
            for item_data in new_todos_data:
                item_id = item_data.get('id')
                if item_id and item_id in current_map:
                    existing = current_map[item_id]
                    if 'content' in item_data:
                        existing.content = item_data['content']
                    if 'status' in item_data:
                        existing.status = item_data['status']
                    if 'priority' in item_data:
                        existing.priority = item_data['priority']
                else:
                    new_items.append(item_data)

            # 将新增项插入到父任务后面（如 id=3.1 插入到 id=3 后面）
            for item_data in new_items:
                item_id = item_data.get('id', '')
                inserted = False
                # 尝试找到父任务位置（如 "3.1" 的父任务是 "3"）
                parent_id = item_id.split('.')[0] if '.' in str(item_id) else None
                if parent_id and parent_id in current_map:
                    parent_idx = None
                    for idx, t in enumerate(current_todos):
                        if t.id == parent_id:
                            parent_idx = idx
                            break
                    if parent_idx is not None:
                        # 找到父任务后面所有同级子任务的最后位置
                        insert_idx = parent_idx + 1
                        while insert_idx < len(current_todos):
                            existing_id = current_todos[insert_idx].id
                            # 同级子任务：父ID相同且是子任务（含.），或者紧跟的兄弟任务
                            if str(existing_id).startswith(str(parent_id) + '.') or existing_id == parent_id:
                                insert_idx += 1
                            else:
                                break
                        current_todos.insert(insert_idx, TodoItem.from_dict(item_data))
                        inserted = True
                if not inserted:
                    current_todos.append(TodoItem.from_dict(item_data))

            final_todos = current_todos
        else:
            final_todos = [TodoItem.from_dict(item) for item in new_todos_data]

        self.save_todos(final_todos)
        return final_todos


@register_tool(id='TodoRead', category='agent', name_cn='读取待办', risk_level='low')
def TodoRead(session_id: str = ''):
    """读取当前会话的待办任务列表，用于继续执行未完成的任务。

⚠️ 此工具与"计划任务/crontab"完全无关。计划任务请使用 crontab_list。

仅在以下场景使用：
1. 之前已通过 TodoWrite 创建了任务列表，现在需要继续执行
2. 需要确认当前任务的完成状态以决定下一步
3. 用户明确询问"待办任务进度"或"任务完成情况"

禁止使用的场景：
- 用户提到"计划任务""定时任务""cron"时（请用 crontab_list）
- 没有已创建的待办列表时
- 用户只是普通提问时

Args:
    session_id: 会话ID，用于关联待办列表
"""
    if not session_id:
        return _xml_response('TodoRead', 'error', '缺少session_id参数')

    manager = TodoManager(session_id)
    todos = manager.get_todos()

    if not todos:
        return _xml_response('TodoRead', 'done', '当前没有待办任务。如果用户提到"计划任务"或"定时任务"，请使用 crontab_list 工具。')

    pending = [t for t in todos if t.status == 'pending']
    in_progress = [t for t in todos if t.status == 'in_progress']
    completed = [t for t in todos if t.status == 'completed']

    summary = f'待办任务总览: 共{len(todos)}个, 进行中{len(in_progress)}个, 待处理{len(pending)}个, 已完成{len(completed)}个\n'

    if in_progress:
        current = in_progress[0]
        summary += f'\n🔴 当前执行中: [{current.id}] {current.content}\n'
        summary += '→ 请继续执行此任务，完成后调用 TodoWrite 更新为completed。'

    if pending:
        summary += f'\n⏳ 待处理任务:'
        for t in pending[:5]:
            summary += f'\n  - [{t.id}] {t.content} (优先级: {t.priority})'

    if completed:
        summary += f'\n✅ 已完成: {len(completed)}个'

    output = json.dumps([t.to_dict() for t in todos], indent=2, ensure_ascii=False)
    return _xml_response('TodoRead', 'done', f'{summary}\n\n详细数据:\n{output}')


@register_tool(id='TodoWrite', category='agent', name_cn='写入待办', risk_level='low')
def TodoWrite(todos: list, session_id: str = '', merge: bool = False):
    """创建和更新结构化任务列表，用于跟踪多步骤任务的执行进度。

⚠️ 此工具与"计划任务/crontab"完全无关。创建定时任务请使用 crontab_create。

## 核心规则（必须严格遵守）

1. **创建后必须立即执行**：调用 TodoWrite 创建任务列表后，必须在同一轮回复中立即开始执行第一个任务。绝对禁止只创建计划而不执行。
2. **每次只推进一个任务**：同时只能有一个任务处于 in_progress 状态。完成当前任务后，再开始下一个。
3. **及时更新状态**：每完成一个步骤，必须调用 TodoWrite 更新该任务为 completed，并将下一个任务更新为 in_progress。
4. **简单任务不需要任务列表**：查看状态、获取信息等简单操作直接调用工具即可，不要创建任务列表。

## 使用场景

✅ 应该使用：
- 用户明确要求执行多步骤操作（如"帮我部署LNMP环境""帮我配置SSL"）
- 正在执行复杂任务，需要跟踪进度
- 任务被中断后恢复执行

❌ 禁止使用：
- 用户只是询问"怎么做""如何部署"（直接文字回答）
- 用户提到"计划任务""定时任务""cron"（请用 crontab_create）
- 简单的单步查询（直接调用对应工具）
- 缺少关键信息无法执行（应先调用 request_user_input）

## 任务状态流转

pending → in_progress → completed
                ↓
            cancelled

每次调用时：
- 将当前完成的任务标记为 completed
- 将下一个要执行的任务标记为 in_progress
- 不要一次性标记多个任务为 in_progress

## 参数格式

todos 数组中每项必须包含：
- id: 任务ID（更新已有任务时必须传入原ID）
- content: 任务描述
- status: 任务状态（pending/in_progress/completed/cancelled）
- priority: 优先级（high/medium/low）

示例：
[{"id": "1", "content": "检查系统环境", "status": "in_progress", "priority": "high"}, {"id": "2", "content": "安装依赖", "status": "pending", "priority": "high"}]

Args:
    todos: 待办任务数组，每项包含id、content、status、priority
    session_id: 会话ID
    merge: 是否与现有待办合并，默认False(替换)
"""
    if not session_id:
        return _xml_response('TodoWrite', 'error', '缺少session_id参数')

    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except (json.JSONDecodeError, ValueError):
            return _xml_response('TodoWrite', 'error', 'todos参数必须是数组，无法解析传入的字符串')

    if not isinstance(todos, list):
        return _xml_response('TodoWrite', 'error', 'todos参数必须是数组')

    parsed_todos = []
    for t in todos:
        if isinstance(t, str):
            try:
                t = json.loads(t)
            except (json.JSONDecodeError, ValueError):
                continue
        if isinstance(t, dict):
            parsed_todos.append(t)
    todos = parsed_todos

    if not todos:
        return _xml_response('TodoWrite', 'error', 'todos数组为空或所有元素格式无效')

    in_progress_count = sum(
        1 for t in todos
        if isinstance(t, dict) and t.get('status') == 'in_progress'
    )
    if in_progress_count > 1:
        first_in_progress = True
        for t in todos:
            if isinstance(t, dict) and t.get('status') == 'in_progress':
                if first_in_progress:
                    first_in_progress = False
                else:
                    t['status'] = 'pending'

    has_in_progress = any(
        isinstance(t, dict) and t.get('status') == 'in_progress'
        for t in todos
    )
    if not has_in_progress:
        for t in todos:
            if isinstance(t, dict) and t.get('status') == 'pending':
                t['status'] = 'in_progress'
                break

    manager = TodoManager(session_id)
    updated_todos = manager.update_todos(todos, merge=merge)

    pending = [t for t in updated_todos if t.status == 'pending']
    in_progress = [t for t in updated_todos if t.status == 'in_progress']
    completed = [t for t in updated_todos if t.status == 'completed']

    summary = f'任务列表已更新: 共{len(updated_todos)}个, 进行中{len(in_progress)}个, 待处理{len(pending)}个, 已完成{len(completed)}个\n'

    if in_progress:
        current = in_progress[0]
        summary += f'\n🔴 当前执行中: [{current.id}] {current.content}'
        summary += '\n→ 请立即调用相应工具执行此任务！'

    next_pending = pending[0] if pending else None
    if next_pending:
        summary += f'\n⏳ 下一个: [{next_pending.id}] {next_pending.content}'

    if completed and len(completed) == len(updated_todos):
        summary += '\n\n✅ 所有任务已完成！请向用户汇报最终结果。'

    # 返回紧凑格式的JSON（前端需要解析渲染任务卡片）
    output = json.dumps([t.to_dict() for t in updated_todos], separators=(',', ':'), ensure_ascii=False)
    return _xml_response('TodoWrite', 'done', f'{summary}\n{output}')


@register_tool(id='request_user_input', category='agent', name_cn='请求用户输入', risk_level='low')
def request_user_input(title: str = '', fields: list = None, session_id: str = ''):
    """当需要用户提供结构化信息时，必须使用此工具展示表单，禁止用纯文本提问。

## ⛔ 重要：一次收集所有参数
**禁止多次调用此工具**。必须将所有需要收集的参数放在一次调用中，避免多次弹窗打断用户。
例如部署应用时，域名、端口、安装方式等所有参数应在一次表单中全部收集完毕。

## 何时必须使用（强制）

当缺少以下类型的信息且无法通过工具自动获取时，必须调用此工具：
- 项目路径、部署目录
- 端口号、域名
- 数据库用户名/密码（⚠️ 绝对禁止自行尝试获取密码）
- 版本号、运行环境
- 用户偏好选择（如Web服务器类型、PHP版本）

## 何时不需要使用

- 信息可以通过工具自动获取（如系统信息用 get_system_info）
- 只需要简单的是/否确认（直接在文本中询问即可）
- 用户已经提供了足够的信息

## 表单设计原则

1. **字段精简**：只问真正缺少的信息，不要问可以通过工具查到的信息
2. **合理默认值**：为可选字段提供 default 值
3. **选项明确**：select 类型字段提供清晰的选项列表
4. **占位提示**：用 placeholder 给出输入示例

Args:
    title: 表单标题，简要说明需要用户提供什么信息
    fields: 表单字段数组，每项包含:
        - name: 字段名(英文标识)
        - label: 字段标签(中文显示)
        - type: 字段类型(text/select/textarea/number/password)
        - required: 是否必填(默认true)
        - placeholder: 占位提示文字
        - options: 选项列表(仅select类型需要)，每项含label和value
        - default: 默认值
    session_id: 会话ID

示例:
    request_user_input(
        title='部署PHP项目信息',
        fields=[
            {'name': 'project_type', 'label': '项目类型', 'type': 'select', 'required': True, 'options': [{'label': 'Laravel', 'value': 'laravel'}, {'label': 'WordPress', 'value': 'wordpress'}]},
            {'name': 'project_path', 'label': '项目文件路径', 'type': 'text', 'required': True, 'placeholder': '例如: D:\\\\projects\\\\myapp'},
        ],
        session_id=session_id
    )
"""
    if not title:
        title = '请填写以下信息'
    if not fields:
        return _xml_response('request_user_input', 'error', 'fields参数不能为空，必须提供至少一个表单字段。请重新调用并传入fields数组，每个字段包含name、label、type等属性。')

    return _xml_response('request_user_input', 'done', json.dumps({'title': title, 'fields': fields}, ensure_ascii=False))


@register_tool(id='agent_call', category='agent', name_cn='调用智能体', risk_level='low')
def agent_call(agent_name: str = '', task: str = '', session_id: str = ''):
    """调用专业智能体执行领域专家任务。智能体会自动收集诊断信息并给出专业分析和操作建议。

## 与普通工具调用的区别

agent_call 不仅仅是获取建议，而是委托专业智能体执行完整的诊断流程：
1. 自动收集相关系统信息
2. 基于专业知识分析问题
3. 给出具体可执行的操作方案

## 何时必须使用

- 用户要求进行全面的安全检查 → 调用 security_expert
- 用户要求分析服务器性能 → 调用 process_analyzer
- 用户要求分析磁盘空间 → 调用 disk_analyzer
- 用户要求分析网站访问 → 调用 site_analyzer
- 遇到专业领域问题需要深度分析时

## 可用智能体

| 智能体ID | 名称 | 适用场景 |
|---------|------|---------|
| security_expert | 安全专家 | 安全漏洞扫描、防火墙配置、SSH加固、内核漏洞检测 |
| process_analyzer | 进程分析专家 | 进程资源占用分析、服务器体检报告 |
| disk_analyzer | 磁盘分析专家 | 磁盘空间分析、大文件查找、清理建议 |
| site_analyzer | 站点分析专家 | 网站配置分析、访问日志分析 |

## 使用方式

1. 不传 agent_name：返回所有可用智能体列表
2. 传入 agent_name + task：调用指定智能体执行任务

调用后，智能体会返回专业分析结果和操作建议。你应该：
- 基于分析结果，制定具体执行步骤
- 如果需要执行操作，调用 TodoWrite 创建任务列表并立即执行
- 不要只是转述建议，要付诸行动

Args:
    agent_name: 智能体名称（如 security_expert、process_analyzer）
    task: 要委托的任务描述，越具体越好
    session_id: 会话ID
"""
    import logging
    logger = logging.getLogger(__name__)

    if not agent_name:
        agents_info = []
        try:
            from apps.sysai.agent.specialized import AGENT_REGISTRY
            for aid, agent_cls in AGENT_REGISTRY.items():
                instance = agent_cls()
                agents_info.append({
                    'id': aid,
                    'name': instance.title,
                    'description': instance.description,
                    'has_auto_collect': bool(instance.auto_collect_steps),
                })
        except Exception as e:
            logger.error(f'获取内置智能体列表失败: {e}')

        try:
            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            for agent in skill_agent_manager.all():
                agents_info.append({
                    'id': agent.agent_id,
                    'name': agent.name,
                    'description': agent.description,
                    'has_auto_collect': False,
                })
        except Exception as e:
            logger.error(f'获取Skill智能体列表失败: {e}')

        return _xml_response('agent_call', 'done', json.dumps(agents_info, ensure_ascii=False, indent=2))

    system_prompt = None
    agent_title = ''
    agent_desc = ''
    auto_collect_steps = []

    try:
        from apps.sysai.agent.specialized import AGENT_REGISTRY
        agent_cls = AGENT_REGISTRY.get(agent_name)
        if agent_cls:
            instance = agent_cls()
            system_prompt = instance.system_prompt
            agent_title = instance.title
            agent_desc = instance.description
            auto_collect_steps = instance.get_auto_collect_steps()
    except Exception as e:
        logger.error(f'获取内置智能体失败: {e}')

    if not system_prompt:
        try:
            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            skill_agent = skill_agent_manager.get(agent_name)
            if skill_agent:
                system_prompt = skill_agent.system_prompt
                agent_title = skill_agent.name
                agent_desc = skill_agent.description
        except Exception as e:
            logger.error(f'获取Skill智能体失败: {e}')

    if not system_prompt:
        return _xml_response('agent_call', 'error', f'未找到智能体: {agent_name}。不传agent_name参数可查看所有可用智能体。')

    result = {
        'agent_name': agent_title,
        'agent_id': agent_name,
        'description': agent_desc,
        'has_auto_collect': bool(auto_collect_steps),
    }

    if task:
        result['task'] = task
        result['expert_knowledge'] = system_prompt

        if auto_collect_steps:
            result['auto_collect_steps'] = [
                {
                    'tool': step.get('tool', ''),
                    'params': step.get('params', {}),
                    'label': step.get('label', ''),
                }
                for step in auto_collect_steps
            ]
            result['instruction'] = (
                f'请以{agent_title}的身份分析任务: {task}\n\n'
                f'专家知识已提供。该智能体支持自动收集信息，'
                f'建议先执行以下诊断步骤收集数据:\n'
                + '\n'.join(
                    f'  {i+1}. [{s.get("label", "")}] 调用 {s.get("tool", "")}'
                    for i, s in enumerate(auto_collect_steps)
                )
                + '\n\n收集数据后，基于专家知识给出专业分析和操作建议。'
            )
        else:
            result['instruction'] = (
                f'请以{agent_title}的身份，基于以下专家知识，'
                f'对任务"{task}"给出专业分析和具体操作建议：\n\n'
                f'{system_prompt}'
            )

    return _xml_response('agent_call', 'done', json.dumps(result, ensure_ascii=False, indent=2))
