import os
import json
import logging
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SkillCurator:
    _instance = None

    EVOLVED_SKILLS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'evolved_skills'
    )

    STATS_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'evolved_skills', 'stats.json'
    )

    CURATOR_LOG_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'curator_log.json'
    )

    MIN_EXECUTIONS_FOR_EVOLUTION = 5
    MIN_SUCCESS_RATE_FOR_EVOLUTION = 0.75
    STALE_DAYS_THRESHOLD = 30
    MIN_CALLS_BEFORE_PRUNE = 2
    MAX_EVOLVED_SKILLS = 20

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._log_entries: List[Dict[str, Any]] = []
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_log()
            self._loaded = True

    def _load_log(self):
        if not os.path.exists(self.CURATOR_LOG_FILE):
            return
        try:
            with open(self.CURATOR_LOG_FILE, 'r', encoding='utf-8') as f:
                self._log_entries = json.load(f)
        except Exception as e:
            logger.error(f'加载curator日志失败: {e}')
            self._log_entries = []

    def _save_log(self):
        try:
            os.makedirs(os.path.dirname(self.CURATOR_LOG_FILE), exist_ok=True)
            with open(self.CURATOR_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._log_entries[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存curator日志失败: {e}')

    def _add_log(self, action: str, detail: str, data: Dict[str, Any] = None):
        self._ensure_loaded()
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'detail': detail,
        }
        if data:
            entry['data'] = data
        self._log_entries.append(entry)
        self._save_log()

    def _load_stats(self) -> Dict[str, Any]:
        if not os.path.exists(self.STATS_FILE):
            return {}
        try:
            with open(self.STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_stats(self, stats: Dict[str, Any]):
        try:
            os.makedirs(os.path.dirname(self.STATS_FILE), exist_ok=True)
            with open(self.STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存stats失败: {e}')

    def _list_evolved_skills(self) -> List[str]:
        if not os.path.exists(self.EVOLVED_SKILLS_DIR):
            return []
        skills = []
        for name in os.listdir(self.EVOLVED_SKILLS_DIR):
            skill_dir = os.path.join(self.EVOLVED_SKILLS_DIR, name)
            if os.path.isdir(skill_dir) and os.path.exists(os.path.join(skill_dir, 'SKILL.md')):
                skills.append(name)
        return skills

    def validate_skill(self, skill_name: str) -> Dict[str, Any]:
        skill_dir = os.path.join(self.EVOLVED_SKILLS_DIR, skill_name)
        skill_md = os.path.join(skill_dir, 'SKILL.md')

        issues = []

        if not os.path.exists(skill_dir):
            return {'valid': False, 'issues': [f'技能目录不存在: {skill_dir}']}

        if not os.path.exists(skill_md):
            return {'valid': False, 'issues': ['SKILL.md文件不存在']}

        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.startswith('---'):
                issues.append('缺少frontmatter元数据')

            from apps.sysai.agent.skill_agent_manager import SkillAgentManager
            mgr = SkillAgentManager.get_instance()
            metadata, body = mgr._parse_frontmatter(content)

            required_fields = ['agent_id', 'name', 'description']
            for field in required_fields:
                if not metadata.get(field):
                    issues.append(f'缺少必要字段: {field}')

            if not body.strip():
                issues.append('系统提示词为空')

            toolsets_str = metadata.get('toolsets', '')
            tools_str = metadata.get('tools', '')
            if not toolsets_str and not tools_str:
                issues.append('未配置任何工具集或工具')

        except Exception as e:
            issues.append(f'解析SKILL.md失败: {str(e)}')

        return {'valid': len(issues) == 0, 'issues': issues}

    def prune_stale_skills(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        stats = self._load_stats()
        pruned = []
        now = datetime.now()

        for skill_name in self._list_evolved_skills():
            skill_stats = stats.get(skill_name, {})
            total_calls = skill_stats.get('total_calls', 0)
            created_at_str = skill_stats.get('created_at', '')

            should_prune = False
            reason = ''

            if total_calls <= self.MIN_CALLS_BEFORE_PRUNE and created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if (now - created_at).days > self.STALE_DAYS_THRESHOLD:
                        should_prune = True
                        reason = f'超过{self.STALE_DAYS_THRESHOLD}天仅调用{total_calls}次'
                except (ValueError, TypeError):
                    pass

            validation = self.validate_skill(skill_name)
            if not validation['valid']:
                should_prune = True
                reason = f'技能验证失败: {"; ".join(validation["issues"])}'

            if should_prune:
                pruned.append({
                    'skill_name': skill_name,
                    'reason': reason,
                    'total_calls': total_calls,
                })
                if not dry_run:
                    skill_dir = os.path.join(self.EVOLVED_SKILLS_DIR, skill_name)
                    try:
                        shutil.rmtree(skill_dir)
                        if skill_name in stats:
                            del stats[skill_name]
                        self._add_log('prune', f'清理技能: {skill_name}, 原因: {reason}')
                    except Exception as e:
                        logger.error(f'清理技能失败 {skill_name}: {e}')

        if not dry_run and pruned:
            self._save_stats(stats)
            try:
                from apps.sysai.agent.skill_agent_manager import skill_agent_manager
                skill_agent_manager.reload()
            except Exception:
                pass

        return pruned

    def auto_evolve(self) -> List[Dict[str, Any]]:
        stats = self._load_stats()
        evolved = []
        existing_skills = self._list_evolved_skills()

        if len(existing_skills) >= self.MAX_EVOLVED_SKILLS:
            logger.info(f'已达到最大技能数({self.MAX_EVOLVED_SKILLS})，跳过自动进化')
            return evolved

        candidates = []
        for tool_name, tool_stats in stats.items():
            if tool_stats.get('type') == 'pattern':
                continue
            if tool_name in existing_skills:
                continue

            total = tool_stats.get('total_calls', 0)
            success = tool_stats.get('success_calls', 0)

            if total >= self.MIN_EXECUTIONS_FOR_EVOLUTION:
                success_rate = success / total
                if success_rate >= self.MIN_SUCCESS_RATE_FOR_EVOLUTION:
                    candidates.append({
                        'tool_name': tool_name,
                        'total_calls': total,
                        'success_rate': round(success_rate, 3),
                        'related_inputs': tool_stats.get('related_inputs', [])[:5],
                    })

        candidates.sort(key=lambda x: x['total_calls'], reverse=True)

        for candidate in candidates:
            if len(existing_skills) + len(evolved) >= self.MAX_EVOLVED_SKILLS:
                break

            tool_name = candidate['tool_name']
            skill_name = f'auto_{tool_name}'

            if skill_name in existing_skills:
                continue

            try:
                from apps.sysai.agent.skill_evolution import skill_evolution
                related_inputs = candidate.get('related_inputs', [])
                description = f'自动沉淀技能: {tool_name} (调用{candidate["total_calls"]}次, 成功率{candidate["success_rate"]*100:.0f}%)'

                preset_questions = related_inputs[:4] if related_inputs else []

                success = skill_evolution.evolve_to_skill(
                    tool_name=tool_name,
                    skill_name=skill_name,
                    description=description,
                    system_prompt=f'你是{tool_name}工具的专业操作助手。根据用户需求，精确调用{tool_name}工具完成任务。',
                    tools=[tool_name],
                )

                if success:
                    evolved.append({
                        'tool_name': tool_name,
                        'skill_name': skill_name,
                        'total_calls': candidate['total_calls'],
                        'success_rate': candidate['success_rate'],
                    })
                    self._add_log('evolve', f'自动进化技能: {tool_name} -> {skill_name}', candidate)
            except Exception as e:
                logger.error(f'自动进化技能失败 {tool_name}: {e}')

        return evolved

    def run_maintenance(self, dry_run: bool = False) -> Dict[str, Any]:
        logger.info(f'Curator维护开始, dry_run={dry_run}')

        pruned = self.prune_stale_skills(dry_run=dry_run)
        evolved = [] if dry_run else self.auto_evolve()

        validation_results = {}
        for skill_name in self._list_evolved_skills():
            validation = self.validate_skill(skill_name)
            if not validation['valid']:
                validation_results[skill_name] = validation['issues']

        result = {
            'timestamp': datetime.now().isoformat(),
            'pruned': pruned,
            'evolved': evolved,
            'validation_issues': validation_results,
            'total_skills': len(self._list_evolved_skills()),
        }

        if not dry_run:
            self._add_log('maintenance', f'维护完成: 清理{len(pruned)}个, 进化{len(evolved)}个', result)

        logger.info(f'Curator维护完成: 清理{len(pruned)}个, 进化{len(evolved)}个')
        return result

    def get_curator_status(self) -> Dict[str, Any]:
        self._ensure_loaded()
        stats = self._load_stats()
        evolved_skills = self._list_evolved_skills()

        tool_count = sum(1 for v in stats.values() if v.get('type') != 'pattern')
        pattern_count = sum(1 for v in stats.values() if v.get('type') == 'pattern')

        recent_logs = self._log_entries[-10:] if self._log_entries else []

        return {
            'evolved_skills_count': len(evolved_skills),
            'tracked_tools_count': tool_count,
            'tracked_patterns_count': pattern_count,
            'max_skills': self.MAX_EVOLVED_SKILLS,
            'recent_logs': recent_logs,
            'evolved_skills': evolved_skills,
        }


skill_curator = SkillCurator.get_instance()
