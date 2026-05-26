import os
import re
import json
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionTracker:
    _instance = None

    TRACKER_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'evolved_skills'
    )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._current_session = None
        self._lock = threading.Lock()

    def start_session(self, user_input: str, session_id: str = ''):
        with self._lock:
            self._current_session = {
                'session_id': session_id,
                'user_input': user_input[:500],
                'tool_calls': [],
                'start_time': datetime.now().isoformat(),
                'errors_encountered': [],
                'corrections': [],
            }

    def record_tool_call(self, tool_name: str, arguments: Dict = None,
                         success: bool = True, error_msg: str = ''):
        with self._lock:
            if not self._current_session:
                return
            self._current_session['tool_calls'].append({
                'tool': tool_name,
                'arguments': arguments or {},
                'success': success,
                'error': error_msg[:200] if error_msg else '',
                'time': datetime.now().isoformat(),
            })

    def record_error(self, error_description: str, resolution: str = ''):
        with self._lock:
            if not self._current_session:
                return
            self._current_session['errors_encountered'].append({
                'error': error_description[:300],
                'resolution': resolution[:300],
                'time': datetime.now().isoformat(),
            })

    def record_correction(self, what_was_wrong: str, correct_approach: str):
        with self._lock:
            if not self._current_session:
                return
            self._current_session['corrections'].append({
                'wrong': what_was_wrong[:300],
                'correct': correct_approach[:300],
                'time': datetime.now().isoformat(),
            })

    def end_session(self) -> Optional[Dict]:
        with self._lock:
            if not self._current_session:
                return None
            session = self._current_session.copy()
            session['end_time'] = datetime.now().isoformat()
            session['total_tool_calls'] = len(session['tool_calls'])
            session['success_tool_calls'] = sum(
                1 for tc in session['tool_calls'] if tc['success']
            )
            session['has_errors'] = len(session['errors_encountered']) > 0
            session['has_corrections'] = len(session['corrections']) > 0
            session['is_complex'] = session['total_tool_calls'] >= 5
            self._current_session = None
            return session

    def get_current_session(self) -> Optional[Dict]:
        with self._lock:
            return self._current_session.copy() if self._current_session else None


session_tracker = SessionTracker.get_instance()


class SkillEvolution:
    _instance = None

    EVOLVED_SKILLS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'evolved_skills'
    )

    MIN_EXECUTIONS = 3
    MIN_SUCCESS_RATE = 0.7

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._stats_file = os.path.join(self.EVOLVED_SKILLS_DIR, 'stats.json')
        self._history_file = os.path.join(self.EVOLVED_SKILLS_DIR, 'session_history.json')
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_stats()
            self._loaded = True

    def _load_stats(self):
        if not os.path.exists(self._stats_file):
            os.makedirs(os.path.dirname(self._stats_file), exist_ok=True)
            return

        try:
            with open(self._stats_file, 'r', encoding='utf-8') as f:
                self._stats = json.load(f)
        except Exception as e:
            logger.error(f'加载技能统计失败: {e}')
            self._stats = {}

    def _save_stats(self):
        try:
            os.makedirs(os.path.dirname(self._stats_file), exist_ok=True)
            with open(self._stats_file, 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存技能统计失败: {e}')

    def record_tool_usage(self, tool_name: str, success: bool, user_input: str = ''):
        self._ensure_loaded()

        if tool_name not in self._stats:
            self._stats[tool_name] = {
                'total_calls': 0,
                'success_calls': 0,
                'related_inputs': [],
                'created_at': datetime.now().isoformat(),
            }

        stats = self._stats[tool_name]
        stats['total_calls'] += 1
        if success:
            stats['success_calls'] += 1

        if user_input and len(stats['related_inputs']) < 50:
            stats['related_inputs'].append(user_input[:200])

        self._save_stats()

    def record_pattern(self, pattern_name: str, tool_sequence: List[str],
                       user_inputs: List[str], success: bool):
        self._ensure_loaded()

        if pattern_name not in self._stats:
            self._stats[pattern_name] = {
                'type': 'pattern',
                'tool_sequence': tool_sequence,
                'total_calls': 0,
                'success_calls': 0,
                'sample_inputs': [],
                'created_at': datetime.now().isoformat(),
            }

        stats = self._stats[pattern_name]
        stats['total_calls'] += 1
        if success:
            stats['success_calls'] += 1

        if user_inputs and len(stats.get('sample_inputs', [])) < 20:
            stats.setdefault('sample_inputs', []).extend(
                [inp[:200] for inp in user_inputs[:3]]
            )

        self._save_stats()

    def record_skill_created(self, skill_name: str, trigger_keywords: str = ''):
        self._ensure_loaded()

        key = f'_skill:{skill_name}'
        if key not in self._stats:
            self._stats[key] = {
                'type': 'skill_lifecycle',
                'skill_name': skill_name,
                'created_at': datetime.now().isoformat(),
                'refinements': 0,
                'last_refined': None,
                'trigger_keywords': trigger_keywords,
                'usage_count': 0,
            }
        self._save_stats()
        self._append_session_history('skill_created', skill_name=skill_name)

    def record_skill_refined(self, skill_name: str, action: str = 'patch'):
        self._ensure_loaded()

        key = f'_skill:{skill_name}'
        if key in self._stats:
            self._stats[key]['refinements'] = self._stats[key].get('refinements', 0) + 1
            self._stats[key]['last_refined'] = datetime.now().isoformat()
            self._stats[key]['last_action'] = action
        else:
            self._stats[key] = {
                'type': 'skill_lifecycle',
                'skill_name': skill_name,
                'created_at': datetime.now().isoformat(),
                'refinements': 1,
                'last_refined': datetime.now().isoformat(),
                'last_action': action,
                'usage_count': 0,
            }
        self._save_stats()
        self._append_session_history('skill_refined', skill_name=skill_name, action=action)

    def record_skill_used(self, skill_name: str):
        self._ensure_loaded()

        key = f'_skill:{skill_name}'
        if key in self._stats:
            self._stats[key]['usage_count'] = self._stats[key].get('usage_count', 0) + 1
            self._stats[key]['last_used'] = datetime.now().isoformat()
        self._save_stats()

    def record_session_summary(self, session_data: Dict):
        if not session_data:
            return

        is_complex = session_data.get('is_complex', False)
        has_errors = session_data.get('has_errors', False)
        has_corrections = session_data.get('has_corrections', False)

        self._append_session_history(
            'session_complete',
            user_input=session_data.get('user_input', ''),
            tool_count=session_data.get('total_tool_calls', 0),
            is_complex=is_complex,
            has_errors=has_errors,
            has_corrections=has_corrections,
        )

        if is_complex or has_errors or has_corrections:
            tool_sequence = [tc['tool'] for tc in session_data.get('tool_calls', [])]
            if len(tool_sequence) >= 3:
                pattern_key = ' -> '.join(tool_sequence[:6])
                self.record_pattern(
                    pattern_name=pattern_key,
                    tool_sequence=tool_sequence,
                    user_inputs=[session_data.get('user_input', '')],
                    success=session_data.get('success_tool_calls', 0) > 0,
                )

    def _append_session_history(self, event_type: str, **kwargs):
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)

            history = []
            if os.path.exists(self._history_file):
                try:
                    with open(self._history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except Exception:
                    history = []

            entry = {
                'event': event_type,
                'time': datetime.now().isoformat(),
            }
            entry.update(kwargs)
            history.append(entry)

            if len(history) > 500:
                history = history[-500:]

            with open(self._history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f'记录会话历史失败: {e}')

    def check_evolution_candidates(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()

        candidates = []
        for name, stats in self._stats.items():
            if stats.get('type') in ('pattern', 'skill_lifecycle'):
                continue

            total = stats.get('total_calls', 0)
            success = stats.get('success_calls', 0)

            if total >= self.MIN_EXECUTIONS:
                success_rate = success / total
                if success_rate >= self.MIN_SUCCESS_RATE:
                    candidates.append({
                        'name': name,
                        'total_calls': total,
                        'success_rate': success_rate,
                        'related_inputs': stats.get('related_inputs', [])[:5],
                    })

        candidates.sort(key=lambda x: x['total_calls'], reverse=True)
        return candidates[:10]

    def evolve_to_skill(self, tool_name: str, skill_name: str,
                        description: str, system_prompt: str,
                        toolsets: List[str] = None, tools: List[str] = None) -> bool:
        try:
            evolved_dir = os.path.join(self.EVOLVED_SKILLS_DIR, skill_name)
            os.makedirs(evolved_dir, exist_ok=True)

            toolsets_str = ','.join(toolsets or [])
            tools_str = ','.join(tools or [tool_name])

            related_inputs = self._stats.get(tool_name, {}).get('related_inputs', [])
            preset_questions = '|'.join(related_inputs[:4]) if related_inputs else ''

            frontmatter = f"""---
agent_id: {skill_name}
name: {skill_name}
description: {description}
category: evolved
toolsets: {toolsets_str}
tools: {tools_str}
preset_questions: {preset_questions}
source: evolved
---"""

            skill_md_path = os.path.join(evolved_dir, 'SKILL.md')
            with open(skill_md_path, 'w', encoding='utf-8') as f:
                f.write(frontmatter + '\n\n' + system_prompt)

            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            skill_agent_manager.reload()

            self.record_skill_created(skill_name)

            logger.info(f'技能沉淀成功: {tool_name} -> {skill_name}')
            return True
        except Exception as e:
            logger.error(f'技能沉淀失败: {e}')
            return False

    def get_stats_summary(self) -> Dict[str, Any]:
        self._ensure_loaded()

        tool_stats = []
        skill_stats = []
        total_calls = 0
        total_success = 0
        evolved_count = 0
        learned_skills_count = 0

        for name, stats in self._stats.items():
            if stats.get('type') == 'pattern':
                evolved_count += 1
                continue

            if stats.get('type') == 'skill_lifecycle':
                learned_skills_count += 1
                skill_stats.append({
                    'skill_name': stats.get('skill_name', name),
                    'created_at': stats.get('created_at', ''),
                    'refinements': stats.get('refinements', 0),
                    'last_refined': stats.get('last_refined', ''),
                    'usage_count': stats.get('usage_count', 0),
                    'last_used': stats.get('last_used', ''),
                })
                continue

            total = stats.get('total_calls', 0)
            success = stats.get('success_calls', 0)
            total_calls += total
            total_success += success

            success_rate = round((success / total) * 100, 1) if total > 0 else 0
            can_evolve = total >= self.MIN_EXECUTIONS and (success / total) >= self.MIN_SUCCESS_RATE

            tool_stats.append({
                'tool_name': name,
                'call_count': total,
                'success_count': success,
                'success_rate': success_rate,
                'can_evolve': can_evolve,
            })

        tool_stats.sort(key=lambda x: x['call_count'], reverse=True)

        avg_success_rate = round((total_success / total_calls) * 100, 1) if total_calls > 0 else 0

        return {
            'total_tools': len(tool_stats),
            'total_calls': total_calls,
            'avg_success_rate': avg_success_rate,
            'evolved_skills': evolved_count,
            'learned_skills': learned_skills_count,
            'tool_stats': tool_stats[:20],
            'skill_lifecycle': skill_stats,
        }

    def get_session_history(self, limit: int = 50) -> List[Dict]:
        try:
            if not os.path.exists(self._history_file):
                return []
            with open(self._history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return history[-limit:]
        except Exception:
            return []


skill_evolution = SkillEvolution.get_instance()
