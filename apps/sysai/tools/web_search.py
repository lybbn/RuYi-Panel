import json
import logging
import requests
from typing import Optional

from apps.sysai.tools.base import register_tool

logger = logging.getLogger(__name__)


def _get_search_api_config():
    try:
        from apps.sysai.models import AIModel
        config_obj = AIModel.get_sys_config()
        if config_obj.extra_params:
            extra = config_obj.extra_params
            return {
                'provider': extra.get('web_search_provider', ''),
                'api_key': extra.get('web_search_api_key', ''),
                'api_url': extra.get('web_search_api_url', ''),
            }
    except Exception:
        pass
    return {
        'provider': '',
        'api_key': '',
        'api_url': '',
    }


def _is_web_search_available() -> bool:
    config = _get_search_api_config()
    return bool(config.get('api_key') and config.get('provider'))


@register_tool(id='web_search', category='system', name_cn='网络搜索', risk_level='low')
def web_search(query: str, num_results: int = 5) -> str:
    """搜索互联网获取信息。当需要查找最新资讯、技术文档、解决方案、软件版本信息等时使用此工具。参数: query(搜索关键词), num_results(返回结果数量，默认5)"""
    config = _get_search_api_config()
    provider = config.get('provider', '')
    api_key = config.get('api_key', '')
    api_url = config.get('api_url', '')

    if not api_key or not provider:
        return '网络搜索功能未配置。请在AI配置中设置搜索API密钥。'

    try:
        if provider == 'bing':
            return _search_bing(query, api_key, api_url, num_results)
        elif provider == 'google':
            return _search_google(query, api_key, api_url, num_results)
        elif provider == 'serpapi':
            return _search_serpapi(query, api_key, api_url, num_results)
        elif provider == 'tavily':
            return _search_tavily(query, api_key, api_url, num_results)
        elif provider == 'bochaai':
            return _search_bochaai(query, api_key, api_url, num_results)
        else:
            return f'不支持的搜索提供商: {provider}'
    except Exception as e:
        logger.error(f'网络搜索失败: {e}')
        return f'搜索失败: {str(e)}'


def _search_bing(query: str, api_key: str, api_url: str, num_results: int) -> str:
    url = api_url or 'https://api.bing.microsoft.com/v7.0/search'
    resp = requests.get(url, params={
        'q': query,
        'count': num_results,
        'responseFilter': 'Webpages',
    }, headers={
        'Ocp-Apim-Subscription-Key': api_key,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for page in data.get('webPages', {}).get('value', [])[:num_results]:
        results.append({
            'title': page.get('name', ''),
            'url': page.get('url', ''),
            'snippet': page.get('snippet', ''),
        })
    return json.dumps(results, ensure_ascii=False, indent=2) if results else '未找到相关结果'


def _search_google(query: str, api_key: str, api_url: str, num_results: int) -> str:
    url = api_url or 'https://www.googleapis.com/customsearch/v1'
    cx = _get_search_api_config().get('api_url', '') or 'default'
    resp = requests.get(url, params={
        'q': query,
        'num': num_results,
        'key': api_key,
        'cx': cx if cx != 'default' else '',
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get('items', [])[:num_results]:
        results.append({
            'title': item.get('title', ''),
            'url': item.get('link', ''),
            'snippet': item.get('snippet', ''),
        })
    return json.dumps(results, ensure_ascii=False, indent=2) if results else '未找到相关结果'


def _search_serpapi(query: str, api_key: str, api_url: str, num_results: int) -> str:
    url = api_url or 'https://serpapi.com/search'
    resp = requests.get(url, params={
        'q': query,
        'num': num_results,
        'api_key': api_key,
        'engine': 'google',
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get('organic_results', [])[:num_results]:
        results.append({
            'title': item.get('title', ''),
            'url': item.get('link', ''),
            'snippet': item.get('snippet', ''),
        })
    return json.dumps(results, ensure_ascii=False, indent=2) if results else '未找到相关结果'


def _search_tavily(query: str, api_key: str, api_url: str, num_results: int) -> str:
    url = api_url or 'https://api.tavily.com/search'
    resp = requests.post(url, json={
        'query': query,
        'max_results': num_results,
        'api_key': api_key,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get('results', [])[:num_results]:
        results.append({
            'title': item.get('title', ''),
            'url': item.get('url', ''),
            'snippet': item.get('content', ''),
        })
    return json.dumps(results, ensure_ascii=False, indent=2) if results else '未找到相关结果'


def _search_bochaai(query: str, api_key: str, api_url: str, num_results: int) -> str:
    url = api_url or 'https://api.bochaai.com/v1/web-search'
    resp = requests.post(url, json={
        'query': query,
        'count': num_results,
        'summary': True,
        'freshness': 'oneYear',
    }, headers={
        'Authorization': f'Bearer {api_key}',
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for page in data.get('data', {}).get('webPages', {}).get('value', [])[:num_results]:
        snippet = page.get('summary', '') or page.get('snippet', '')
        results.append({
            'title': page.get('name', ''),
            'url': page.get('url', ''),
            'snippet': snippet,
            'siteName': page.get('siteName', ''),
            'datePublished': page.get('datePublished', ''),
        })
    return json.dumps(results, ensure_ascii=False, indent=2) if results else '未找到相关结果'
