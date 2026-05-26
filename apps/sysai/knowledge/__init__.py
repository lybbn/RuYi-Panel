import os
import re
import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class KnowledgeBase:
    _instance = None

    KNOWLEDGE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'template', 'agent', 'knowledge'
    )

    CUSTOM_KNOWLEDGE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'data', 'agent', 'knowledge'
    )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_all()
            self._loaded = True

    def reload(self):
        self._loaded = False
        self._docs.clear()
        self._ensure_loaded()

    def _load_all(self):
        self._docs.clear()
        self._scan_dir(self.KNOWLEDGE_DIR)
        self._scan_dir(self.CUSTOM_KNOWLEDGE_DIR)
        logger.info(f'知识库加载完成: {len(self._docs)} 篇文档')

    def _scan_dir(self, base_dir: str):
        if not os.path.exists(base_dir):
            return
        for filename in sorted(os.listdir(base_dir)):
            if not filename.endswith('.md'):
                continue
            filepath = os.path.join(base_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                doc = self._parse_doc(filename[:-3], content, filepath)
                if doc:
                    self._docs[doc['id']] = doc
            except Exception as e:
                logger.warning(f'加载知识文档失败 [{filename}]: {e}')

    def _parse_doc(self, doc_id: str, content: str, filepath: str) -> Optional[Dict[str, Any]]:
        title = doc_id
        tags = []
        body = content

        first_line = content.split('\n', 1)[0] if content else ''
        if first_line.startswith('# '):
            title = first_line[2:].strip()

        meta_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if meta_match:
            meta_text = meta_match.group(1)
            body = content[meta_match.end():]
            for line in meta_text.split('\n'):
                if line.startswith('title:'):
                    title = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('tags:'):
                    tags_str = line.split(':', 1)[1].strip()
                    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        else:
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('tags:'):
                    tags_str = stripped.split(':', 1)[1].strip()
                    tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        sections = self._split_sections(body)

        return {
            'id': doc_id,
            'title': title,
            'tags': tags,
            'content': body,
            'sections': sections,
            'filepath': filepath,
        }

    def _split_sections(self, content: str) -> List[Dict[str, Any]]:
        sections = []
        current_title = ''
        current_lines = []

        for line in content.split('\n'):
            if line.startswith('## ') or line.startswith('### '):
                if current_lines:
                    section_text = '\n'.join(current_lines).strip()
                    if section_text:
                        sections.append({
                            'title': current_title,
                            'content': section_text,
                        })
                current_title = line.lstrip('#').strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            section_text = '\n'.join(current_lines).strip()
            if section_text:
                sections.append({
                    'title': current_title,
                    'content': section_text,
                })

        return sections

    def _tokenize(self, text: str) -> set:
        tokens = set()
        for word in re.findall(r'[a-zA-Z0-9]+', text):
            tokens.add(word.lower())
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        for segment in chinese_chars:
            tokens.add(segment)
            if len(segment) >= 2:
                for i in range(len(segment) - 1):
                    tokens.add(segment[i:i + 2])
        return tokens

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        if not self._docs:
            return []

        query_lower = query.lower()
        query_words = self._tokenize(query)

        scored = []
        for doc_id, doc in self._docs.items():
            score = self._score_doc(doc, query_lower, query_words)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, doc in scored[:max_results]:
            relevant_sections = self._find_relevant_sections(doc, query_lower, query_words)
            results.append({
                'id': doc['id'],
                'title': doc['title'],
                'tags': doc['tags'],
                'relevance': round(score, 2),
                'sections': relevant_sections,
            })

        return results

    def _score_doc(self, doc: Dict[str, Any], query_lower: str, query_words: set) -> float:
        score = 0.0

        title_lower = doc['title'].lower()
        if query_lower in title_lower:
            score += 10.0
        for word in query_words:
            if word in title_lower:
                score += 3.0

        for tag in doc.get('tags', []):
            tag_lower = tag.lower()
            if query_lower in tag_lower or tag_lower in query_lower:
                score += 5.0
            for word in query_words:
                if word in tag_lower:
                    score += 2.0

        content_lower = doc['content'].lower()
        for word in query_words:
            count = content_lower.count(word)
            if count > 0:
                score += min(count * 0.3, 3.0)

        for section in doc.get('sections', []):
            section_title_lower = section['title'].lower()
            if query_lower in section_title_lower:
                score += 4.0
            for word in query_words:
                if word in section_title_lower:
                    score += 1.5

        return score

    def _find_relevant_sections(self, doc: Dict[str, Any], query_lower: str,
                                 query_words: set) -> List[Dict[str, Any]]:
        if not doc.get('sections'):
            return [{'title': '', 'content': doc['content'][:2000]}]

        scored_sections = []
        for section in doc['sections']:
            score = 0.0
            title_lower = section['title'].lower()
            content_lower = section['content'].lower()

            if query_lower in title_lower:
                score += 5.0
            for word in query_words:
                if word in title_lower:
                    score += 2.0
                count = content_lower.count(word)
                if count > 0:
                    score += min(count * 0.5, 4.0)

            if score > 0:
                scored_sections.append((score, section))

        if not scored_sections:
            return [{'title': doc['sections'][0]['title'],
                     'content': doc['sections'][0]['content'][:1500]}]

        scored_sections.sort(key=lambda x: x[0], reverse=True)
        return [{'title': s['title'], 'content': s['content'][:2000]}
                for _, s in scored_sections[:3]]

    def list_docs(self) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return [
            {'id': doc['id'], 'title': doc['title'], 'tags': doc['tags'],
             'size': len(doc['content'])}
            for doc in self._docs.values()
        ]

    def get_doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_loaded()
        doc = self._docs.get(doc_id)
        if not doc:
            return None
        return {'id': doc['id'], 'title': doc['title'], 'tags': doc['tags'],
                'content': doc['content']}


knowledge_base = KnowledgeBase.get_instance()
