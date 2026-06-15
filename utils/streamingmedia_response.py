"""
Views and functions for serving static files. These are only to be used
during development, and SHOULD NOT be used in a production setting.
"""
"""
流媒体文件的流式响应（支持视频快进）
"""
import mimetypes
import posixpath
from pathlib import Path

from django.http import (
    FileResponse, Http404, HttpResponse, HttpResponseNotModified,
)
from django.template import Context, Engine, TemplateDoesNotExist, loader
from django.utils._os import safe_join
from django.utils.http import http_date, parse_http_date
from django.utils.translation import gettext as _, gettext_lazy
import re
import os
from wsgiref.util import FileWrapper
from django.http import StreamingHttpResponse


# Vite 构建产物的文件名包含 hash，可以设置长期缓存
# 匹配类似 app.abc123.js、index.def456.css 这种带 hash 的文件名
_hash_pattern = re.compile(r'\.[0-9a-f]{8,}\.')

def _is_hashed_asset(filename):
    """判断静态资源文件名是否包含内容 hash（Vite/Rollup 产物特征）"""
    return bool(_hash_pattern.search(filename))

def _get_cache_control(path_str, is_hashed):
    """根据文件类型和是否带 hash 返回 Cache-Control 策略"""
    ext = os.path.splitext(path_str)[1].lower()
    # 带 hash 的 JS/CSS/SVG/字体文件 → 长期缓存（1年），内容变了 hash 会变
    if is_hashed and ext in ('.js', '.css', '.svg', '.woff', '.woff2', '.ttf', '.eot'):
        return 'public, max-age=31536000, immutable'
    # 图片资源 → 中期缓存（30天）
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.avif'):
        return 'public, max-age=2592000'
    # HTML 和其他 → 短期缓存（1小时），确保更新及时生效
    if ext in ('.html', '.htm'):
        return 'public, max-age=3600, must-revalidate'
    # 其他静态资源 → 1天缓存
    return 'public, max-age=86400'

def streamingmedia_serve(request, path, document_root=None, show_indexes=False):
    """
    Serve static files below a given point in the directory structure.

    To use, put a URL pattern such as::

        from django.views.static import serve

        path('<path:path>', serve, {'document_root': '/path/to/my/files/'})

    in your URLconf. You must provide the ``document_root`` param. You may
    also set ``show_indexes`` to ``True`` if you'd like to serve a basic index
    of the directory.  This index view will use the template hardcoded below,
    but if you'd like to override it, you can create a template called
    ``static/directory_index.html``.
    """
    path = posixpath.normpath(path).lstrip('/')
    fullpath = Path(safe_join(document_root, path))
    if fullpath.is_dir():
        if show_indexes:
            return directory_index(path, fullpath)
        raise Http404(_("Directory indexes are not allowed here."))
    if not fullpath.exists():
        raise Http404(_('“%(path)s” does not exist') % {'path': fullpath})
    # Respect the If-Modified-Since header.
    statobj = fullpath.stat()
    if not was_modified_since(request.META.get('HTTP_IF_MODIFIED_SINCE'),
                              statobj.st_mtime, statobj.st_size):
        return HttpResponseNotModified()
    content_type, encoding = mimetypes.guess_type(str(fullpath))
    content_type = content_type or 'application/octet-stream'
    if content_type in ['video/mp4','video/ogg', 'video/flv', 'video/avi', 'video/wmv', 'video/rmvb','audio/mp3','audio/x-m4a','audio/mpeg','audio/ogg']:
        response = stream_video(request, fullpath)
        return response
    elif fullpath.suffix in ['.apk']:#兼容小米的浏览器等迅雷下载内核无法下载问题
        content_type = 'application/vnd.android.package-archive'
        response = FileResponse(fullpath.open('rb'), content_type=content_type)
        response['Content-Length'] = fullpath.stat().st_size
        return response
    else:
        # 尝试返回 gzip 预压缩文件（构建时由 vite-plugin-compression 生成）
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if 'gzip' in accept_encoding and fullpath.suffix in ('.js', '.css', '.svg', '.html', '.json', '.woff2', '.ttf'):
            gz_path = fullpath.with_suffix(fullpath.suffix + '.gz')
            if gz_path.exists():
                response = FileResponse(gz_path.open('rb'), content_type=content_type)
                response.headers["Content-Encoding"] = 'gzip'
                response.headers["Content-Length"] = gz_path.stat().st_size
                response.headers["Vary"] = 'Accept-Encoding'
                response.headers["Last-Modified"] = http_date(statobj.st_mtime)
                response.headers["Cache-Control"] = _get_cache_control(path, _is_hashed_asset(fullpath.name))
                return response
        response = FileResponse(fullpath.open('rb'), content_type=content_type)
        response.headers["Last-Modified"] = http_date(statobj.st_mtime)
        if encoding:
            response.headers["Content-Encoding"] = encoding
        # 添加缓存控制头
        response.headers["Cache-Control"] = _get_cache_control(path, _is_hashed_asset(fullpath.name))
        response.headers["Vary"] = 'Accept-Encoding'
        return response


DEFAULT_DIRECTORY_INDEX_TEMPLATE = """
{% load i18n %}
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8">
    <meta http-equiv="Content-Language" content="en-us">
    <meta name="robots" content="NONE,NOARCHIVE">
    <title>{% blocktranslate %}Index of {{ directory }}{% endblocktranslate %}</title>
  </head>
  <body>
    <h1>{% blocktranslate %}Index of {{ directory }}{% endblocktranslate %}</h1>
    <ul>
      {% if directory != "/" %}
      <li><a href="../">../</a></li>
      {% endif %}
      {% for f in file_list %}
      <li><a href="{{ f|urlencode }}">{{ f }}</a></li>
      {% endfor %}
    </ul>
  </body>
</html>
"""
template_translatable = gettext_lazy("Index of %(directory)s")


def directory_index(path, fullpath):
    try:
        t = loader.select_template([
            'static/directory_index.html',
            'static/directory_index',
        ])
    except TemplateDoesNotExist:
        t = Engine(libraries={'i18n': 'django.templatetags.i18n'}).from_string(DEFAULT_DIRECTORY_INDEX_TEMPLATE)
        c = Context()
    else:
        c = {}
    files = []
    for f in fullpath.iterdir():
        if not f.name.startswith('.'):
            url = str(f.relative_to(fullpath))
            if f.is_dir():
                url += '/'
            files.append(url)
    c.update({
        'directory': path + '/',
        'file_list': files,
    })
    return HttpResponse(t.render(c))


def was_modified_since(header=None, mtime=0, size=0):
    """
    Was something modified since the user last downloaded it?

    header
      This is the value of the If-Modified-Since header.  If this is None,
      I'll just return True.

    mtime
      This is the modification time of the item we're talking about.

    size
      This is the size of the item we're talking about.
    """
    try:
        if header is None:
            raise ValueError
        matches = re.match(r"^([^;]+)(; length=([0-9]+))?$", header,
                           re.IGNORECASE)
        header_mtime = parse_http_date(matches[1])
        header_len = matches[3]
        if header_len and int(header_len) != size:
            raise ValueError
        if int(mtime) > header_mtime:
            raise ValueError
    except (AttributeError, ValueError, OverflowError):
        return True
    return False

def file_iterator(file_name, chunk_size=8192, offset=0, length=None):
    with open(file_name, "rb") as f:
        f.seek(offset, os.SEEK_SET)
        remaining = length
        while True:
            bytes_length = chunk_size if remaining is None else min(remaining, chunk_size)
            data = f.read(bytes_length)
            if not data:
                break
            if remaining:
                remaining -= len(data)
            yield data

def get_buff_size(file_size):
    buff_size = 2097152
    if file_size > 1073741824:
        buff_size = 4194304
    return buff_size

def stream_video(request,path):
    """将视频文件以流媒体的方式响应"""
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)
    range_match = range_re.match(range_header)
    #这里根据实际情况改变，我的views.py在core文件夹下但是folder_path却只到core的上一层，media也在core文件夹下
    size = os.path.getsize(path)
    content_type, encoding = mimetypes.guess_type(path)
    content_type = content_type or 'application/octet-stream'
    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        # last_byte = first_byte + 1024 * 1024 * 10
        last_byte = first_byte + get_buff_size(size)
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1
        resp = StreamingHttpResponse(file_iterator(path, offset=first_byte, length=length), status=206, content_type=content_type)
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = 'bytes %s-%s/%s' % (first_byte, last_byte, size)
    else:
        resp = StreamingHttpResponse(FileWrapper(open(path, 'rb')), content_type=content_type)
        resp['Content-Length'] = str(size)
    resp['Accept-Ranges'] = 'bytes'
    return resp