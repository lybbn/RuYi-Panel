import logging
from apps.sysai.tools.base import register_tool, _xml_response
from apps.sysai.knowledge import knowledge_base

logger = logging.getLogger(__name__)


@register_tool(id='search_docs', category='system', name_cn='搜索面板文档', risk_level='low')
def search_docs(query: str, max_results: int = 3) -> str:
    """搜索如意面板操作说明文档。当用户询问面板功能使用方法、操作步骤、配置方式时使用此工具。参数: query(搜索关键词，如"SSL证书""创建网站""Docker部署"), max_results(返回结果数量，默认3)"""
    try:
        results = knowledge_base.search(query, max_results)
        if not results:
            return _xml_response('search_docs', 'done',
                f'未找到与"{query}"相关的面板文档。请尝试其他关键词，或使用 web_search 搜索互联网。')

        parts = []
        for i, result in enumerate(results, 1):
            parts.append(f'### 文档{i}: {result["title"]}')
            if result.get('tags'):
                parts.append(f'标签: {", ".join(result["tags"])}')
            parts.append(f'相关度: {result["relevance"]}')
            for section in result.get('sections', []):
                if section.get('title'):
                    parts.append(f'\n#### {section["title"]}')
                parts.append(section['content'])
            parts.append('')

        content = '\n'.join(parts)
        return _xml_response('search_docs', 'done', content)
    except Exception as e:
        logger.error(f'搜索面板文档失败: {e}')
        return _xml_response('search_docs', 'error', f'搜索失败: {str(e)}')


@register_tool(id='list_docs', category='system', name_cn='列出面板文档', risk_level='low')
def list_docs() -> str:
    """列出如意面板所有可用的操作说明文档。当用户想了解面板有哪些功能或文档时使用此工具。"""
    try:
        docs = knowledge_base.list_docs()
        if not docs:
            return _xml_response('list_docs', 'done', '暂无面板操作说明文档。')

        parts = ['如意面板操作说明文档列表：\n']
        for doc in docs:
            tags_str = f' [{", ".join(doc["tags"])}]' if doc.get('tags') else ''
            parts.append(f'- {doc["title"]}{tags_str}')

        return _xml_response('list_docs', 'done', '\n'.join(parts))
    except Exception as e:
        logger.error(f'列出面板文档失败: {e}')
        return _xml_response('list_docs', 'error', f'获取文档列表失败: {str(e)}')
