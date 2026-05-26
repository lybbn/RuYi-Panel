import json
import logging
import os
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def _get_fact_store_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    data_dir = os.path.join(base, 'data', 'ai_facts')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_fact_file(server_id: str) -> str:
    data_dir = _get_fact_store_dir()
    safe_id = server_id.replace('/', '_').replace('\\', '_').replace(':', '_')
    return os.path.join(data_dir, f'{safe_id}.json')


def _get_server_id() -> str:
    import platform
    return f"{platform.system()}_{platform.node()}"


def save_fact(fact_type: str, fact_data: Dict[str, Any], server_id: str = None) -> bool:
    if server_id is None:
        server_id = _get_server_id()

    fact_file = _get_fact_file(server_id)
    facts = _load_all_facts(fact_file)

    facts[fact_type] = {
        'data': fact_data,
        'updated_at': time.time(),
    }

    try:
        with open(fact_file, 'w', encoding='utf-8') as f:
            json.dump(facts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f'保存事实失败: {e}')
        return False


def get_fact(fact_type: str, server_id: str = None) -> Optional[Dict[str, Any]]:
    if server_id is None:
        server_id = _get_server_id()

    fact_file = _get_fact_file(server_id)
    facts = _load_all_facts(fact_file)

    entry = facts.get(fact_type)
    if entry and isinstance(entry, dict):
        return entry.get('data')
    return None


def get_all_facts(server_id: str = None) -> Dict[str, Any]:
    if server_id is None:
        server_id = _get_server_id()

    fact_file = _get_fact_file(server_id)
    facts = _load_all_facts(fact_file)

    result = {}
    for fact_type, entry in facts.items():
        if isinstance(entry, dict) and 'data' in entry:
            result[fact_type] = entry['data']
    return result


def get_facts_summary(server_id: str = None, max_age_hours: int = 24) -> str:
    if server_id is None:
        server_id = _get_server_id()

    facts = get_all_facts(server_id)
    if not facts:
        return ''

    now = time.time()
    fact_file = _get_fact_file(server_id)
    raw_facts = _load_all_facts(fact_file)

    lines = []
    for fact_type, data in facts.items():
        entry = raw_facts.get(fact_type, {})
        updated_at = entry.get('updated_at', 0)
        age_hours = (now - updated_at) / 3600

        if age_hours > max_age_hours:
            continue

        age_str = f'{age_hours:.1f}小时前' if age_hours < 1 else f'{int(age_hours)}小时前'
        lines.append(f'- {fact_type}: {json.dumps(data, ensure_ascii=False)[:200]} ({age_str})')

    if not lines:
        return ''

    return '[已确认的服务器事实（跨会话共享）]\n' + '\n'.join(lines)


def _load_all_facts(fact_file: str) -> Dict[str, Any]:
    if not os.path.exists(fact_file):
        return {}
    try:
        with open(fact_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
