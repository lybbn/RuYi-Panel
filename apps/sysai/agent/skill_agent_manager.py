import os
import re
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SkillAgentConfig:
    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        category: str,
        toolsets: List[str],
        tools: List[str],
        system_prompt: str,
        preset_questions: List[str],
        metadata: Dict[str, Any],
        location: str,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.category = category
        self.toolsets = toolsets
        self.tools = tools
        self.system_prompt = system_prompt
        self.preset_questions = preset_questions
        self.metadata = metadata
        self.location = location

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.agent_id,
            'title': self.name,
            'description': self.description,
            'category': self.category,
            'toolsets': self.toolsets,
            'tools': self.tools,
            'welcome_suggestions': self.preset_questions,
            'has_auto_collect': False,
            'source': self.metadata.get('source', 'user'),
        }


class SkillAgentManager:
    _instance = None

    SKILL_AGENTS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'template', 'agent', 'skill_agents'
    )

    EVOLVED_SKILLS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'evolved_skills'
    )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._agents: Dict[str, SkillAgentConfig] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_all()
            self._loaded = True

    def _load_all(self):
        self._agents.clear()
        self._scan_skill_dir(self.SKILL_AGENTS_DIR)
        self._scan_skill_dir(self.EVOLVED_SKILLS_DIR)

    def _scan_skill_dir(self, base_dir: str):
        if not os.path.exists(base_dir):
            return

        for root, dirs, files in os.walk(base_dir):
            if 'SKILL.md' in files:
                agent = self._load_from_dir(root)
                if agent and agent.agent_id not in self._agents:
                    self._agents[agent.agent_id] = agent

    def _load_from_dir(self, agent_dir: str) -> Optional[SkillAgentConfig]:
        skill_md_path = os.path.join(agent_dir, 'SKILL.md')
        if not os.path.exists(skill_md_path):
            return None

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata, body = self._parse_frontmatter(content)

            agent_id = metadata.get('agent_id', '') or metadata.get('name', os.path.basename(agent_dir))
            name = metadata.get('name', agent_id)
            description = metadata.get('description', '')
            category = metadata.get('category', 'system')

            toolsets_str = metadata.get('toolsets', '')
            toolsets = [t.strip() for t in toolsets_str.split(',') if t.strip()] if toolsets_str else []

            tools_str = metadata.get('tools', '')
            tools = [t.strip() for t in tools_str.split(',') if t.strip()] if tools_str else []

            questions_str = metadata.get('preset_questions', '')
            preset_questions = [q.strip() for q in questions_str.split('|') if q.strip()] if questions_str else []

            return SkillAgentConfig(
                agent_id=agent_id,
                name=name,
                description=description,
                category=category,
                toolsets=toolsets,
                tools=tools,
                system_prompt=body.strip(),
                preset_questions=preset_questions,
                metadata=metadata,
                location=skill_md_path,
            )
        except Exception as e:
            logger.error(f'Error loading skill agent from {agent_dir}: {e}')
            return None

    def _parse_frontmatter(self, content: str) -> tuple:
        frontmatter_regex = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
        match = frontmatter_regex.match(content)

        metadata = {}
        body = content

        if match:
            yaml_content = match.group(1)
            body = content[match.end():]

            for line in yaml_content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()

        return metadata, body

    def get(self, agent_id: str) -> Optional[SkillAgentConfig]:
        self._ensure_loaded()
        return self._agents.get(agent_id)

    def all(self) -> List[SkillAgentConfig]:
        self._ensure_loaded()
        return list(self._agents.values())

    def match_by_input(self, user_input: str) -> Optional[SkillAgentConfig]:
        self._ensure_loaded()
        input_lower = user_input.lower()

        best_match = None
        best_score = 0

        for agent in self._agents.values():
            score = 0
            for keyword in agent.preset_questions:
                keyword_lower = keyword.lower()
                if keyword_lower in input_lower or input_lower in keyword_lower:
                    score += 2

            for keyword in agent.description.lower().split():
                if len(keyword) > 1 and keyword in input_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = agent

        if best_match and best_score >= 2:
            return best_match
        return None

    def reload(self):
        self._loaded = False
        self._ensure_loaded()

    def all_as_dict(self) -> List[Dict[str, Any]]:
        return [agent.to_dict() for agent in self.all()]

    def create_skill(self, name: str, description: str, category: str,
                     toolsets: List[str], tools: List[str],
                     system_prompt: str, preset_questions: List[str]) -> Dict[str, Any]:
        agent_id = re.sub(r'[^a-z0-9_]', '_', name.lower()).strip('_')
        if not agent_id:
            agent_id = f'custom_{int(__import__("time").time())}'

        agent_dir = os.path.join(self.EVOLVED_SKILLS_DIR, agent_id)
        os.makedirs(agent_dir, exist_ok=True)

        skill_md_path = os.path.join(agent_dir, 'SKILL.md')
        frontmatter_lines = [
            '---',
            f'name: {name}',
            f'agent_id: {agent_id}',
            f'description: {description}',
            f'category: {category}',
            f'toolsets: {",".join(toolsets)}',
            f'tools: {",".join(tools)}',
            f'preset_questions: {"|".join(preset_questions)}',
            '---',
        ]
        content = '\n'.join(frontmatter_lines) + '\n\n' + system_prompt + '\n'

        with open(skill_md_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self._loaded = False
        self._ensure_loaded()

        return {'id': agent_id, 'name': name, 'created': True}

    def delete_skill(self, agent_id: str) -> bool:
        self._ensure_loaded()
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent_dir = os.path.dirname(agent.location)
        if os.path.exists(agent_dir) and agent_dir.startswith(self.EVOLVED_SKILLS_DIR):
            import shutil
            shutil.rmtree(agent_dir)
            del self._agents[agent_id]
            return True

        return False


skill_agent_manager = SkillAgentManager.get_instance()
