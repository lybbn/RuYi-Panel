import os
import re
import json
import logging
import shutil
import tempfile
from typing import List, Dict, Optional

from utils.fileunzip import func_unzip_secure

logger = logging.getLogger(__name__)


class Skill:
    def __init__(self, name: str, location: str, description: str, content: str, metadata: Dict):
        self.name = name
        self.location = location
        self.description = description
        self.content = content
        self.metadata = metadata


class SkillManager:
    _instance = None

    SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'template', 'agent', 'skills')
    DATA_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'agent', 'skills')
    SKILLS_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'agent', 'skills_state.json')

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._ensure_skills_dir()
        self._ensure_data_skills_dir()
        self._state = self._load_state()

    def _ensure_skills_dir(self):
        if not os.path.exists(self.SKILLS_DIR):
            try:
                os.makedirs(self.SKILLS_DIR, exist_ok=True)
            except OSError:
                pass

    def _ensure_data_skills_dir(self):
        if not os.path.exists(self.DATA_SKILLS_DIR):
            try:
                os.makedirs(self.DATA_SKILLS_DIR, exist_ok=True)
            except OSError:
                pass

    def _load_state(self) -> Dict:
        default_state = {'disabled_skills': []}
        if not os.path.exists(self.SKILLS_STATE_FILE):
            return default_state
        try:
            with open(self.SKILLS_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return default_state
            disabled = state.get('disabled_skills', [])
            if not isinstance(disabled, list):
                disabled = []
            return {'disabled_skills': [str(name).strip() for name in disabled if str(name).strip()]}
        except Exception:
            return default_state

    def _save_state(self) -> bool:
        try:
            state_dir = os.path.dirname(self.SKILLS_STATE_FILE)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
            with open(self.SKILLS_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _disabled_name_set(self) -> set:
        disabled_names = self._state.get('disabled_skills', [])
        return set(disabled_names)

    def all(self) -> List[Skill]:
        skills = []
        seen_names = set()

        for skills_dir in [self.DATA_SKILLS_DIR, self.SKILLS_DIR]:
            if not os.path.exists(skills_dir):
                continue
            for root, dirs, files in os.walk(skills_dir):
                if 'SKILL.md' in files:
                    skill = self._load_skill_from_dir(root)
                    if skill and skill.name not in seen_names:
                        seen_names.add(skill.name)
                        if skills_dir == self.DATA_SKILLS_DIR:
                            skill.metadata['_source'] = skill.metadata.get('source') or 'user'
                        else:
                            skill.metadata['_source'] = skill.metadata.get('source') or 'builtin'
                        skills.append(skill)
        return skills

    def get(self, name: str) -> Optional[Skill]:
        for skill in self.all():
            if skill.name == name:
                return skill
        return None

    def get_enabled(self, name: str) -> Optional[Skill]:
        skill = self.get(name)
        if not skill:
            return None
        if not self.is_enabled(name):
            return None
        return skill

    def all_enabled(self) -> List[Skill]:
        disabled_names = self._disabled_name_set()
        return [skill for skill in self.all() if skill.name not in disabled_names]

    def is_enabled(self, name: str) -> bool:
        if not self.get(name):
            return False
        disabled_names = self._disabled_name_set()
        return name not in disabled_names

    def set_skill_enabled(self, name: str, enabled: bool) -> Dict:
        skill = self.get(name)
        if not skill:
            return {'status': False, 'msg': f'技能不存在: {name}'}
        disabled_names = self._disabled_name_set()
        if enabled:
            disabled_names.discard(name)
        else:
            disabled_names.add(name)
        self._state['disabled_skills'] = sorted(disabled_names)
        if not self._save_state():
            return {'status': False, 'msg': '保存技能状态失败'}
        return {'status': True, 'msg': '设置成功'}

    def get_all_skills_info(self) -> List[Dict]:
        disabled_names = self._disabled_name_set()
        infos = []
        for skill in self.all():
            infos.append({
                'name': skill.name,
                'description': skill.description,
                'location': skill.location,
                'enabled': skill.name not in disabled_names,
                'metadata': skill.metadata,
                'source': skill.metadata.get('_source', 'builtin'),
            })
        return infos

    def _load_skill_from_dir(self, skill_dir: str) -> Optional[Skill]:
        skill_md_path = os.path.join(skill_dir, 'SKILL.md')
        if not os.path.exists(skill_md_path):
            return None

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata, body = self._parse_frontmatter(content)

            name = metadata.get('name', os.path.basename(skill_dir))
            description = metadata.get('description', '')

            return Skill(
                name=name,
                location=skill_md_path,
                description=description,
                content=body,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f'Error loading skill from {skill_dir}: {e}')
            return None

    def _parse_frontmatter(self, content: str):
        frontmatter_regex = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
        match = frontmatter_regex.match(content)

        metadata = {}
        body = content

        if match:
            yaml_content = match.group(1)
            body = content[match.end():]

            try:
                for line in yaml_content.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
            except Exception:
                pass

        return metadata, body

    def list_files(self, skill_dir: str, limit: int = 50) -> List[str]:
        files = []
        for root, dirs, filenames in os.walk(skill_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in filenames:
                if filename == 'SKILL.md' or filename.startswith('.'):
                    continue

                full_path = os.path.join(root, filename)
                files.append(full_path)

                if len(files) >= limit:
                    return files
        return files

    def import_skill_from_content(self, name: str, content: str, description: str = '') -> Dict:
        if not name or not name.strip():
            return {'status': False, 'msg': '技能名称不能为空'}
        name = name.strip()
        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$', name):
            return {'status': False, 'msg': '技能名称只能包含字母、数字、下划线、横线和中文'}

        skill_dir = os.path.join(self.DATA_SKILLS_DIR, name)
        skill_md_path = os.path.join(skill_dir, 'SKILL.md')

        try:
            os.makedirs(skill_dir, exist_ok=True)
        except OSError as e:
            return {'status': False, 'msg': f'创建技能目录失败: {e}'}

        if not content.strip().startswith('---'):
            frontmatter = f'---\nname: {name}\ndescription: {description}\n---\n\n'
            content = frontmatter + content

        try:
            with open(skill_md_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return {'status': False, 'msg': f'写入技能文件失败: {e}'}

        return {'status': True, 'msg': f'技能 [{name}] 导入成功', 'name': name}

    def import_skill_from_archive(self, archive_path: str) -> Dict:
        if not os.path.exists(archive_path):
            return {'status': False, 'msg': '压缩包文件不存在'}

        name_lower = archive_path.lower()
        if name_lower.endswith('.tar.gz'):
            pass
        elif name_lower.endswith('.tar.bz2'):
            pass
        elif name_lower.endswith('.tgz'):
            pass
        elif name_lower.endswith('.zip'):
            pass
        else:
            ext = os.path.splitext(archive_path)[1].lower()
            if ext not in ('.zip',):
                return {'status': False, 'msg': '不支持的压缩格式，仅支持 zip/tar.gz/tar.bz2'}

        tmp_dir = tempfile.mkdtemp(prefix='ruyi_skill_import_')
        try:
            func_unzip_secure(archive_path, tmp_dir)
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {'status': False, 'msg': f'解压失败: {e}'}

        skill_dirs = self._find_skill_dirs(tmp_dir)
        if not skill_dirs:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {'status': False, 'msg': '压缩包中未找到有效的技能目录（需包含SKILL.md）'}

        results = []
        success_count = 0
        fail_count = 0
        for src_dir in skill_dirs:
            result = self._install_skill_dir(src_dir)
            results.append(result)
            if result.get('status'):
                success_count += 1
            else:
                fail_count += 1

        shutil.rmtree(tmp_dir, ignore_errors=True)

        if success_count == 0:
            return {
                'status': False,
                'msg': f'导入失败: {fail_count} 个技能安装不成功',
                'results': results,
            }

        return {
            'status': True,
            'msg': f'导入完成: 成功 {success_count} 个, 失败 {fail_count} 个',
            'success_count': success_count,
            'fail_count': fail_count,
            'results': results,
        }

    def _find_skill_dirs(self, root_dir: str) -> List[str]:
        skill_dirs = []
        has_skill_md = os.path.exists(os.path.join(root_dir, 'SKILL.md'))
        if has_skill_md:
            skill_dirs.append(root_dir)
            return skill_dirs

        for entry in os.listdir(root_dir):
            entry_path = os.path.join(root_dir, entry)
            if os.path.isdir(entry_path) and not entry.startswith('.'):
                if os.path.exists(os.path.join(entry_path, 'SKILL.md')):
                    skill_dirs.append(entry_path)

        if not skill_dirs:
            for entry in os.listdir(root_dir):
                entry_path = os.path.join(root_dir, entry)
                if os.path.isdir(entry_path) and not entry.startswith('.'):
                    for sub in os.listdir(entry_path):
                        sub_path = os.path.join(entry_path, sub)
                        if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, 'SKILL.md')):
                            skill_dirs.append(sub_path)

        return skill_dirs

    def _install_skill_dir(self, src_dir: str) -> Dict:
        skill_md_path = os.path.join(src_dir, 'SKILL.md')
        if not os.path.exists(skill_md_path):
            return {'status': False, 'msg': f'目录 {src_dir} 中缺少 SKILL.md'}

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {'status': False, 'msg': f'读取 SKILL.md 失败: {e}'}

        metadata, _ = self._parse_frontmatter(content)
        name = metadata.get('name', os.path.basename(src_dir)).strip()

        if not name:
            name = os.path.basename(src_dir)

        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$', name):
            return {'status': False, 'msg': f'技能名称无效: {name}'}

        dest_dir = os.path.join(self.DATA_SKILLS_DIR, name)
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)

        try:
            shutil.copytree(src_dir, dest_dir)
        except Exception as e:
            return {'status': False, 'msg': f'复制技能目录失败: {e}'}

        self._validate_skill_scripts(dest_dir)

        return {'status': True, 'msg': f'技能 [{name}] 安装成功', 'name': name}

    def _validate_skill_scripts(self, skill_dir: str):
        scripts_dir = os.path.join(skill_dir, 'scripts')
        if not os.path.isdir(scripts_dir):
            return

        for root, dirs, files in os.walk(scripts_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                if filename.endswith('.sh'):
                    try:
                        os.chmod(filepath, 0o755)
                    except Exception:
                        pass

    def import_skill_from_json(self, skill_data: Dict) -> Dict:
        name = skill_data.get('name', '')
        if not name or not name.strip():
            return {'status': False, 'msg': '技能名称不能为空'}
        name = name.strip()

        description = skill_data.get('description', '')
        content = skill_data.get('content', '')

        if not content:
            return {'status': False, 'msg': '技能内容不能为空'}

        return self.import_skill_from_content(name, content, description)

    def import_skills_from_array(self, skills_array: List[Dict]) -> Dict:
        results = []
        success_count = 0
        fail_count = 0

        for skill_data in skills_array:
            result = self.import_skill_from_json(skill_data)
            results.append(result)
            if result.get('status'):
                success_count += 1
            else:
                fail_count += 1

        return {
            'status': fail_count == 0,
            'msg': f'导入完成: 成功 {success_count} 个, 失败 {fail_count} 个',
            'success_count': success_count,
            'fail_count': fail_count,
            'results': results,
        }

    def delete_skill(self, name: str) -> Dict:
        skill = self.get(name)
        if not skill:
            return {'status': False, 'msg': f'技能不存在: {name}'}

        if skill.metadata.get('_source') == 'builtin':
            return {'status': False, 'msg': '内置技能不能删除，只能禁用'}

        skill_dir = os.path.dirname(skill.location)
        if not os.path.exists(skill_dir):
            return {'status': False, 'msg': f'技能目录不存在: {name}'}

        try:
            shutil.rmtree(skill_dir)
        except Exception as e:
            return {'status': False, 'msg': f'删除技能目录失败: {e}'}

        disabled_names = self._disabled_name_set()
        disabled_names.discard(name)
        self._state['disabled_skills'] = sorted(disabled_names)
        self._save_state()

        return {'status': True, 'msg': f'技能 [{name}] 已删除'}


skill_manager = SkillManager.get_instance()
