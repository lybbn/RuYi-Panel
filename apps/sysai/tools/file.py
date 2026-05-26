import os
import fnmatch
import base64
from apps.sysai.tools.base import register_tool
from utils.common import RunCommand


def _format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} PB'


@register_tool(id='list_directory', category='file', name_cn='目录列表', risk_level='low')
def list_directory(path: str = '/', show_hidden: bool = False):
    """列出指定目录下的文件和子目录，包括文件大小、权限、修改时间等信息。当用户需要查看目录内容时使用。

    Args:
        path: 要列出的目录路径，默认为根目录 /
        show_hidden: 是否显示隐藏文件，默认否
    """
    if not os.path.exists(path):
        return {'error': f'路径不存在: {path}'}

    if not os.path.isdir(path):
        return {'error': f'不是目录: {path}'}

    try:
        entries = []
        for entry in os.scandir(path):
            if not show_hidden and entry.name.startswith('.'):
                continue
            try:
                stat = entry.stat()
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'is_dir': entry.is_dir(),
                    'is_file': entry.is_file(),
                    'is_symlink': entry.is_symlink(),
                    'size_bytes': stat.st_size,
                    'size_human': _format_size(stat.st_size),
                    'mode': oct(stat.st_mode)[-3:],
                    'uid': stat.st_uid,
                    'gid': stat.st_gid,
                    'mtime': stat.st_mtime,
                })
            except (PermissionError, OSError):
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'error': '权限不足',
                })

        entries.sort(key=lambda x: (not x.get('is_dir', False), x.get('name', '')))

        return {
            'path': path,
            'entries': entries,
            'total': len(entries),
        }
    except PermissionError:
        return {'error': f'权限不足，无法访问: {path}'}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='read_file', category='file', name_cn='读取文件', risk_level='low')
def read_file(path: str, start_line: int = 1, end_line: int = 100, encoding: str = 'utf-8'):
    """读取指定文件的内容，支持指定行范围。当用户需要查看文件内容时使用。

    Args:
        path: 文件路径
        start_line: 起始行号，默认1
        end_line: 结束行号，默认100
        encoding: 文件编码，默认utf-8
    """
    from apps.sysai.agent.file_safety import is_read_denied
    denied = is_read_denied(path)
    if denied:
        return {'error': denied}

    if not os.path.exists(path):
        return {'error': f'文件不存在: {path}'}

    if not os.path.isfile(path):
        return {'error': f'不是文件: {path}'}

    try:
        file_size = os.path.getsize(path)
        if file_size > 10 * 1024 * 1024:
            return {'error': f'文件过大({file_size}字节)，请使用 start_line 和 end_line 参数分段读取'}

        with open(path, 'r', encoding=encoding, errors='replace') as f:
            lines = f.readlines()

        total_lines = len(lines)
        selected = lines[start_line - 1:end_line]
        content = ''.join(selected)

        return {
            'path': path,
            'total_lines': total_lines,
            'start_line': start_line,
            'end_line': min(end_line, total_lines),
            'content': content[:20000],
            'truncated': len(content) > 20000,
            'file_size_bytes': file_size,
        }
    except PermissionError:
        return {'error': f'权限不足，无法读取: {path}'}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='write_file', category='file', name_cn='写入文件', risk_level='high')
def write_file(path: str, content: str, mode: str = 'overwrite', encoding: str = 'utf-8'):
    """写入内容到指定文件。⚠️此为高危操作，会修改或创建文件，请确认操作意图后再执行。

    Args:
        path: 文件路径
        content: 要写入的内容
        mode: 写入模式，overwrite(覆盖) 或 append(追加)，默认overwrite
        encoding: 文件编码，默认utf-8
    """
    from apps.sysai.agent.file_safety import is_write_denied
    denied = is_write_denied(path)
    if denied:
        return {'error': denied}

    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        return {'error': f'目录不存在: {dir_path}，请先创建目录'}

    try:
        if mode == 'append':
            with open(path, 'a', encoding=encoding) as f:
                f.write(content)
        else:
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)

        return {
            'path': path,
            'mode': mode,
            'content_length': len(content),
            'message': f'文件{"追加" if mode == "append" else "写入"}成功',
        }
    except PermissionError:
        return {'error': f'权限不足，无法写入: {path}'}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='search_files', category='file', name_cn='搜索文件', risk_level='low')
def search_files(directory: str, pattern: str = '*', max_results: int = 50):
    """在指定目录下搜索文件，支持通配符模式匹配。当用户需要查找特定文件时使用。

    Args:
        directory: 搜索的目录路径
        pattern: 文件名匹配模式，支持通配符，默认 *
        max_results: 最大返回结果数，默认50
    """
    if not os.path.exists(directory):
        return {'error': f'目录不存在: {directory}'}

    try:
        files = []
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                if fnmatch.fnmatch(filename, pattern):
                    files.append(os.path.join(root, filename))
                    if len(files) >= max_results:
                        break
            if len(files) >= max_results:
                break

        return {
            'directory': directory,
            'pattern': pattern,
            'files': files,
            'count': len(files),
        }
    except PermissionError:
        return {'error': f'权限不足，无法搜索: {directory}'}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='search_in_file', category='file', name_cn='文件内容搜索', risk_level='low')
def search_in_file(path: str, keyword: str, case_sensitive: bool = True, max_lines: int = 30):
    """在文件中搜索包含指定关键词的行。当用户需要在文件中查找特定内容时使用。

    Args:
        path: 文件路径
        keyword: 搜索关键词
        case_sensitive: 是否区分大小写，默认是
        max_lines: 最大返回行数，默认30
    """
    if not os.path.exists(path):
        return {'error': f'文件不存在: {path}'}

    if not os.path.isfile(path):
        return {'error': f'不是文件: {path}'}

    try:
        search_key = keyword if case_sensitive else keyword.lower()
        lines = []

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                check_line = line if case_sensitive else line.lower()
                if search_key in check_line:
                    lines.append({
                        'line_number': line_num,
                        'content': line.rstrip('\n\r'),
                    })
                    if len(lines) >= max_lines:
                        break

        return {
            'path': path,
            'keyword': keyword,
            'matches': lines,
            'count': len(lines),
        }
    except PermissionError:
        return {'error': f'权限不足，无法读取: {path}'}
    except Exception as e:
        return {'error': str(e)}