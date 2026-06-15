"""
如意面板AI助手 - 项目类型检测工具
自动检测项目类型并生成部署配置
"""
import json
import os
import re
from apps.sysai.tools.base import register_tool
from utils.common import current_os


def _read_file_safe(path: str, max_size: int = 51200) -> str:
    """安全读取文件，限制大小"""
    try:
        if not os.path.isfile(path):
            return ''
        size = os.path.getsize(path)
        if size > max_size:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(max_size)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''


def _read_json_safe(path: str) -> dict:
    """安全读取JSON文件"""
    content = _read_file_safe(path)
    if content:
        try:
            return json.loads(content)
        except Exception:
            pass
    return {}


def _find_wsgi_asgi(root: str) -> dict:
    """查找Django/Flask的WSGI/ASGI入口"""
    result = {'wsgi': '', 'asgi': '', 'settings': '', 'manage_py': ''}
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过隐藏目录和虚拟环境
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('venv', 'env', 'node_modules', '__pycache__', '.venv')]
        depth = dirpath.replace(root, '').count(os.sep)
        if depth > 3:
            continue
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            rel = os.path.relpath(fpath, root).replace('\\', '/')
            if f == 'wsgi.py':
                content = _read_file_safe(fpath)
                if 'application' in content or 'get_wsgi_application' in content:
                    module = rel.replace('/', '.').replace('.py', '')
                    result['wsgi'] = f'{module}:application'
            elif f == 'asgi.py':
                content = _read_file_safe(fpath)
                if 'application' in content or 'get_asgi_application' in content:
                    module = rel.replace('/', '.').replace('.py', '')
                    result['asgi'] = f'{module}:application'
            elif f == 'settings.py':
                rel_path = os.path.relpath(fpath, root).replace('\\', '/')
                module = rel_path.replace('/', '.').replace('.py', '')
                result['settings'] = module
            elif f == 'manage.py':
                result['manage_py'] = rel
    return result


def _detect_python_framework(content: str, files: list) -> str:
    """检测Python框架"""
    content_lower = content.lower()
    if 'django' in content_lower or 'DJANGO_SETTINGS_MODULE' in content:
        return 'django'
    if 'flask' in content_lower:
        return 'flask'
    if 'fastapi' in content_lower or 'uvicorn' in content_lower:
        return 'fastapi'
    if 'tornado' in content_lower:
        return 'tornado'
    if 'aiohttp' in content_lower:
        return 'aiohttp'
    # 通过文件判断
    if 'manage.py' in files:
        return 'django'
    return 'python'


def _detect_python_project(root: str) -> dict:
    """检测Python项目"""
    result = {
        'language': 'python',
        'project_type': 'python',
        'framework': 'python',
        'version': '3.10',
        'requirements_file': '',
        'install_cmd': '',
        'start_cmd': '',
        'application': '',
        'entry_point': '',
        'start_method': 'command',
        'port': 8000,
    }

    # 检测requirements文件
    for req_file in ['requirements.txt', 'requirements.pip', 'setup.py', 'pyproject.toml', 'Pipfile']:
        fpath = os.path.join(root, req_file)
        if os.path.isfile(fpath):
            result['requirements_file'] = req_file
            if req_file == 'requirements.txt':
                result['install_cmd'] = 'pip install -r requirements.txt'
            elif req_file == 'pyproject.toml':
                result['install_cmd'] = 'pip install -e .'
            elif req_file == 'Pipfile':
                result['install_cmd'] = 'pipenv install'
            break

    # 读取requirements内容检测框架
    req_content = ''
    if result['requirements_file']:
        req_content = _read_file_safe(os.path.join(root, result['requirements_file']))

    files = os.listdir(root)
    framework = _detect_python_framework(req_content, files)
    result['framework'] = framework

    if framework == 'django':
        wsgi_info = _find_wsgi_asgi(root)
        if wsgi_info['wsgi']:
            result['application'] = wsgi_info['wsgi']
            result['start_method'] = 'gunicorn'
            result['entry_point'] = wsgi_info['wsgi'].split(':')[0].replace('.', '/') + '.py'
            result['start_cmd'] = f'gunicorn {wsgi_info["wsgi"]}'
        elif wsgi_info['asgi']:
            result['application'] = wsgi_info['asgi']
            result['start_method'] = 'daphne'
            result['entry_point'] = wsgi_info['asgi'].split(':')[0].replace('.', '/') + '.py'
            result['start_cmd'] = f'daphne {wsgi_info["asgi"]}'
        # 检测端口
        settings_module = wsgi_info.get('settings', '')
        if settings_module:
            settings_path = os.path.join(root, settings_module.replace('.', '/') + '.py')
            settings_content = _read_file_safe(settings_path)
            port_match = re.search(r'(?:PORT|port)\s*=\s*(\d+)', settings_content)
            if port_match:
                result['port'] = int(port_match.group(1))

    elif framework == 'flask':
        # 查找Flask app实例
        for f in files:
            if f.endswith('.py'):
                content = _read_file_safe(os.path.join(root, f))
                if 'Flask(__name__)' in content or 'Flask(' in content:
                    app_match = re.search(r'(\w+)\s*=\s*Flask\(', content)
                    if app_match:
                        app_name = app_match.group(1)
                        module = f.replace('.py', '')
                        result['application'] = f'{module}:{app_name}'
                        result['entry_point'] = f
                        result['start_method'] = 'gunicorn'
                        result['start_cmd'] = f'gunicorn {module}:{app_name}'
                        break
        if not result['application']:
            result['application'] = 'app:app'
            result['start_cmd'] = 'gunicorn app:app'

    elif framework == 'fastapi':
        for f in files:
            if f.endswith('.py'):
                content = _read_file_safe(os.path.join(root, f))
                if 'FastAPI(' in content:
                    app_match = re.search(r'(\w+)\s*=\s*FastAPI\(', content)
                    if app_match:
                        app_name = app_match.group(1)
                        module = f.replace('.py', '')
                        result['application'] = f'{module}:{app_name}'
                        result['entry_point'] = f
                        result['start_method'] = 'command'
                        result['start_cmd'] = f'uvicorn {module}:{app_name} --host 0.0.0.0 --port 8000'
                        break
        if not result['application']:
            result['application'] = 'main:app'
            result['start_cmd'] = 'uvicorn main:app --host 0.0.0.0 --port 8000'

    else:
        # 通用Python项目
        result['start_method'] = 'command'
        # 查找main.py或app.py
        for entry in ['main.py', 'app.py', 'run.py', 'server.py', 'start.py']:
            if entry in files:
                result['entry_point'] = entry
                result['start_cmd'] = f'python {entry}'
                break
        if not result['start_cmd']:
            result['start_cmd'] = 'python main.py'

    # 检测Python版本要求
    for ver_file in ['runtime.txt', '.python-version', 'Pipfile']:
        fpath = os.path.join(root, ver_file)
        if os.path.isfile(fpath):
            content = _read_file_safe(fpath)
            ver_match = re.search(r'python[\s-]*(\d+\.\d+)', content, re.IGNORECASE)
            if ver_match:
                result['version'] = ver_match.group(1)
                break
    # pyproject.toml
    pyproj = os.path.join(root, 'pyproject.toml')
    if os.path.isfile(pyproj):
        content = _read_file_safe(pyproj)
        ver_match = re.search(r'python\s*=\s*"[\^>=]*(\d+\.\d+)', content)
        if ver_match:
            result['version'] = ver_match.group(1)

    return result


def _detect_node_project(root: str) -> dict:
    """检测Node.js项目"""
    result = {
        'language': 'node',
        'project_type': 'node',
        'framework': 'node',
        'version': '18',
        'install_cmd': 'npm install',
        'start_cmd': '',
        'start_method': 'command',
        'port': 3000,
        'package_json': 'package.json',
    }

    pkg = _read_json_safe(os.path.join(root, 'package.json'))
    if not pkg:
        return result

    deps = {}
    deps.update(pkg.get('dependencies', {}))
    deps.update(pkg.get('devDependencies', {}))

    scripts = pkg.get('scripts', {})
    engine = pkg.get('engines', {})
    if engine.get('node'):
        ver_match = re.search(r'(\d+)', engine['node'])
        if ver_match:
            result['version'] = ver_match.group(1)

    # 检测框架
    if 'next' in deps:
        result['framework'] = 'next'
        result['port'] = 3000
        result['start_cmd'] = scripts.get('start', 'npm start')
        result['install_cmd'] = 'npm install && npm run build'
    elif 'nuxt' in deps:
        result['framework'] = 'nuxt'
        result['port'] = 3000
        result['start_cmd'] = scripts.get('start', 'npm start')
    elif '@nestjs/core' in deps:
        result['framework'] = 'nestjs'
        result['port'] = 3000
        result['start_cmd'] = scripts.get('start:prod', scripts.get('start', 'npm start'))
    elif 'express' in deps:
        result['framework'] = 'express'
        result['port'] = 3000
        # 查找入口文件
        entry = pkg.get('main', 'index.js')
        result['start_cmd'] = scripts.get('start', f'node {entry}')
    elif 'koa' in deps:
        result['framework'] = 'koa'
        result['port'] = 3000
        entry = pkg.get('main', 'index.js')
        result['start_cmd'] = scripts.get('start', f'node {entry}')
    elif 'vue' in deps:
        result['framework'] = 'vue'
        result['port'] = 8080
        result['install_cmd'] = 'npm install && npm run build'
        result['start_cmd'] = 'npm run build'
    elif 'react' in deps:
        result['framework'] = 'react'
        result['port'] = 3000
        result['install_cmd'] = 'npm install && npm run build'
        result['start_cmd'] = 'npm run build'
    elif 'angular' in deps:
        result['framework'] = 'angular'
        result['port'] = 4200
        result['install_cmd'] = 'npm install && npm run build'
        result['start_cmd'] = 'npm run build'
    else:
        result['start_cmd'] = scripts.get('start', 'node index.js')

    # 从scripts中提取端口
    start_script = scripts.get('start', '')
    port_match = re.search(r'(?:-p|--port|PORT=)\s*(\d+)', start_script)
    if port_match:
        result['port'] = int(port_match.group(1))

    # .nvmrc / .node-version
    for ver_file in ['.nvmrc', '.node-version']:
        fpath = os.path.join(root, ver_file)
        if os.path.isfile(fpath):
            ver = _read_file_safe(fpath).strip()
            if ver:
                ver_clean = ver.lstrip('v')
                if re.match(r'^\d+$', ver_clean):
                    result['version'] = ver_clean
                break

    return result


def _detect_go_project(root: str) -> dict:
    """检测Go项目"""
    result = {
        'language': 'go',
        'project_type': 'go',
        'framework': 'go',
        'version': '1.21',
        'install_cmd': 'go mod download',
        'start_cmd': '',
        'start_method': 'command',
        'port': 8080,
    }

    # 读取go.mod
    gomod = _read_file_safe(os.path.join(root, 'go.mod'))
    if gomod:
        ver_match = re.search(r'go\s+(\d+\.\d+)', gomod)
        if ver_match:
            result['version'] = ver_match.group(1)

    # 检测框架
    if 'github.com/gin-gonic/gin' in gomod:
        result['framework'] = 'gin'
    elif 'github.com/labstack/echo' in gomod:
        result['framework'] = 'echo'
    elif 'github.com/gofiber/fiber' in gomod:
        result['framework'] = 'fiber'
    elif 'github.com/beego/beego' in gomod:
        result['framework'] = 'beego'

    # 查找main.go中的端口
    main_go = os.path.join(root, 'main.go')
    if os.path.isfile(main_go):
        content = _read_file_safe(main_go)
        port_match = re.search(r':(\d{2,5})', content)
        if port_match:
            port = int(port_match.group(1))
            if 1024 <= port <= 65535:
                result['port'] = port

    result['start_cmd'] = './main'
    result['install_cmd'] = 'go mod download && go build -o main .'

    return result


def _detect_php_project(root: str) -> dict:
    """检测PHP项目"""
    result = {
        'language': 'php',
        'project_type': 'php',
        'framework': 'php',
        'version': '8.1',
        'install_cmd': '',
        'start_cmd': '',
        'start_method': 'php-fpm',
        'port': 9000,
    }

    # composer.json
    composer = _read_json_safe(os.path.join(root, 'composer.json'))
    if composer:
        deps = composer.get('require', {})
        if 'laravel/framework' in deps:
            result['framework'] = 'laravel'
            result['install_cmd'] = 'composer install --no-dev'
        elif 'symfony/framework-bundle' in deps:
            result['framework'] = 'symfony'
            result['install_cmd'] = 'composer install --no-dev'
        elif 'yiisoft/yii2' in deps:
            result['framework'] = 'yii2'
            result['install_cmd'] = 'composer install --no-dev'
        elif 'topthink/framework' in deps:
            result['framework'] = 'thinkphp'
            result['install_cmd'] = 'composer install --no-dev'
        else:
            result['install_cmd'] = 'composer install --no-dev'

        php_ver = deps.get('php', '')
        ver_match = re.search(r'(\d+\.\d+)', php_ver)
        if ver_match:
            result['version'] = ver_match.group(1)

    # 检查web入口
    for entry_dir in ['public', 'web', 'www', 'htdocs']:
        if os.path.isdir(os.path.join(root, entry_dir)):
            index_php = os.path.join(root, entry_dir, 'index.php')
            if os.path.isfile(index_php):
                result['entry_point'] = f'{entry_dir}/index.php'
                break

    return result


def _extract_deploy_docs(root: str) -> dict:
    """读取项目自带的部署文档，提取安装/构建/运行命令"""
    result = {
        'found': False,
        'source': '',
        'install_steps': [],
        'build_steps': [],
        'run_steps': [],
        'env_requirements': [],
        'raw_content': '',
    }
    # 按优先级查找部署文档
    doc_files = [
        'DEPLOY.md', 'DEPLOYMENT.md', 'INSTALL.md',
        'README.md', 'README.txt', 'README.rst',
        'docs/deploy.md', 'docs/install.md',
        'docs/DEPLOY.md', 'docs/INSTALL.md',
    ]
    for doc in doc_files:
        fpath = os.path.join(root, doc)
        if os.path.isfile(fpath):
            content = _read_file_safe(fpath, max_size=102400)
            if not content:
                continue
            result['found'] = True
            result['source'] = doc
            result['raw_content'] = content[:8000]  # 截取前8000字符供AI参考
            # 提取代码块中的命令
            code_blocks = re.findall(r'```(?:bash|shell|sh)?\s*\n(.*?)```', content, re.DOTALL)
            all_cmds = []
            for block in code_blocks:
                for line in block.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('//'):
                        all_cmds.append(line)
            # 按关键词分类命令
            for cmd in all_cmds:
                cmd_lower = cmd.lower()
                if any(kw in cmd_lower for kw in ['install', 'pip install', 'npm install', 'yarn', 'bundle install', 'composer install', 'go mod', 'go get']):
                    result['install_steps'].append(cmd)
                elif any(kw in cmd_lower for kw in ['build', 'compile', 'webpack', 'vite build', 'npm run build', 'make', 'go build', 'cargo build']):
                    result['build_steps'].append(cmd)
                elif any(kw in cmd_lower for kw in ['start', 'run', 'serve', 'launch', 'gunicorn', 'uvicorn', 'pm2', 'rails s', 'rackup', 'npm start', 'npm run dev', 'npm run serve', 'python manage.py', 'python app.py', 'python main.py', 'python server.py', 'python -m', 'flask run', 'dotnet run', './main', './app', 'node server', 'node app']):
                    result['run_steps'].append(cmd)
            # 提取环境要求
            env_patterns = [
                r'(?:需要|require|requires|依赖|环境)[：:]\s*(.+)',
                r'Node\.?js\s*[>=]+\s*(\d+)',
                r'Python\s*[>=]+\s*(\d+\.\d+)',
                r'Go\s*[>=]+\s*(\d+\.\d+)',
                r'PHP\s*[>=]+\s*(\d+\.\d+)',
                r'Ruby\s*[>=]+\s*(\d+\.\d+)',
            ]
            for pattern in env_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                result['env_requirements'].extend(matches)
            break  # 只读第一个找到的文档
    return result


def _detect_static_site(root: str) -> dict:
    """检测静态站点（纯HTML/CSS/JS），也检查常见子目录"""
    files = os.listdir(root)
    html_files = [f for f in files if f.endswith('.html')]
    has_css = any(f.endswith('.css') for f in files)
    has_js = any(f.endswith('.js') for f in files)

    # 检查常见静态文件子目录
    sub_root = root
    for sub in ['public', 'dist', 'build', 'out', 'docs']:
        sub_path = os.path.join(root, sub)
        if os.path.isdir(sub_path):
            sub_files = os.listdir(sub_path)
            sub_html = [f for f in sub_files if f.endswith('.html')]
            if sub_html and not html_files:
                sub_root = sub_path
                html_files = sub_html
                has_css = has_css or any(f.endswith('.css') for f in sub_files)
                has_js = has_js or any(f.endswith('.js') for f in sub_files)
                break

    if not html_files:
        return None

    # 检查是否有index.html
    has_index = 'index.html' in html_files

    return {
        'language': 'static',
        'project_type': 'static',
        'framework': 'static',
        'start_method': 'static',
        'port': 80,
        'has_index_html': has_index,
        'html_files': html_files[:10],
        'has_css': has_css,
        'has_js': has_js,
        'start_cmd': '',
        'install_cmd': '',
        'web_root': os.path.relpath(sub_root, root).replace('\\', '/') if sub_root != root else '',
        'note': '静态站点，通过Nginx直接托管，无需运行时进程',
    }


def _detect_ruby_project(root: str) -> dict:
    """检测Ruby项目"""
    result = {
        'language': 'ruby',
        'project_type': 'ruby',
        'framework': 'ruby',
        'version': '3.0',
        'install_cmd': 'bundle install',
        'start_cmd': '',
        'start_method': 'command',
        'port': 3000,
    }

    gemfile = _read_file_safe(os.path.join(root, 'Gemfile'))
    if gemfile:
        if 'rails' in gemfile.lower():
            result['framework'] = 'rails'
            result['start_cmd'] = 'bundle exec rails server -b 0.0.0.0 -p 3000'
            result['port'] = 3000
        elif 'sinatra' in gemfile.lower():
            result['framework'] = 'sinatra'
            result['start_cmd'] = 'ruby app.rb -o 0.0.0.0 -p 4567'
            result['port'] = 4567
        else:
            # 查找config.ru
            if os.path.isfile(os.path.join(root, 'config.ru')):
                result['start_cmd'] = 'bundle exec rackup -o 0.0.0.0 -p 9292'
                result['port'] = 9292
            else:
                for entry in ['app.rb', 'main.rb', 'server.rb']:
                    if os.path.isfile(os.path.join(root, entry)):
                        result['start_cmd'] = f'ruby {entry}'
                        break

    # .ruby-version
    ruby_ver_file = os.path.join(root, '.ruby-version')
    if os.path.isfile(ruby_ver_file):
        ver = _read_file_safe(ruby_ver_file).strip()
        ver_match = re.search(r'(\d+\.\d+)', ver)
        if ver_match:
            result['version'] = ver_match.group(1)

    return result


def _detect_project_type(root: str) -> dict:
    """自动检测项目类型"""
    if not os.path.isdir(root):
        return {'error': f'目录不存在: {root}'}

    files = os.listdir(root)

    # Git仓库检测
    is_git = '.git' in files

    # 读取部署文档（优先级最高）
    deploy_docs = _extract_deploy_docs(root)

    # Python项目
    python_indicators = ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile', 'manage.py']
    if any(f in files for f in python_indicators):
        result = _detect_python_project(root)
        result['is_git_repo'] = is_git
        result['deploy_docs'] = deploy_docs
        return result

    # Node.js项目
    if 'package.json' in files:
        result = _detect_node_project(root)
        result['is_git_repo'] = is_git
        result['deploy_docs'] = deploy_docs
        return result

    # Go项目
    if 'go.mod' in files or 'main.go' in files:
        result = _detect_go_project(root)
        result['is_git_repo'] = is_git
        result['deploy_docs'] = deploy_docs
        return result

    # PHP项目
    php_indicators = ['composer.json', 'index.php']
    if any(f in files for f in php_indicators):
        result = _detect_php_project(root)
        result['is_git_repo'] = is_git
        result['deploy_docs'] = deploy_docs
        return result

    # Ruby项目
    ruby_indicators = ['Gemfile', 'config.ru', 'Rakefile']
    if any(f in files for f in ruby_indicators):
        result = _detect_ruby_project(root)
        result['is_git_repo'] = is_git
        result['deploy_docs'] = deploy_docs
        return result

    # Docker项目
    if 'Dockerfile' in files or 'docker-compose.yml' in files or 'docker-compose.yaml' in files:
        result = {
            'language': 'docker',
            'project_type': 'docker',
            'framework': 'docker',
            'is_git_repo': is_git,
            'deploy_docs': deploy_docs,
        }
        compose_file = None
        for cf in ['docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml']:
            if cf in files:
                compose_file = cf
                break
        if compose_file:
            result['compose_file'] = compose_file
            result['start_cmd'] = f'docker compose -f {compose_file} up -d'
        elif 'Dockerfile' in files:
            result['dockerfile'] = 'Dockerfile'
        return result

    # 静态站点检测（最后尝试）
    static_result = _detect_static_site(root)
    if static_result:
        static_result['is_git_repo'] = is_git
        static_result['deploy_docs'] = deploy_docs
        return static_result

    return {
        'error': '无法识别项目类型。未检测到已知的项目配置文件（requirements.txt、package.json、go.mod、composer.json、Gemfile、Dockerfile等）。',
        'files_found': files[:20],
        'is_git_repo': is_git,
        'deploy_docs': deploy_docs,
        'suggestion': '请使用web_search搜索该项目的部署方式，或查看deploy_docs中的部署文档内容',
    }


@register_tool(id='panel_detect_project', category='panel', name_cn='项目类型检测', risk_level='low')
def panel_detect_project(path: str):
    """检测指定目录下的项目类型，自动识别项目语言、框架、入口文件、启动命令等部署信息。
    在部署Git仓库或本地代码项目前必须先调用此工具，获取项目配置后再调用panel_deploy_project部署。

    支持检测的项目类型：
    - Python: Django、Flask、FastAPI、Tornado、Aiohttp、通用Python
    - Node.js: Express、Koa、NestJS、Next.js、Nuxt、Vue、React、Angular
    - Go: Gin、Echo、Fiber、Beego、通用Go
    - PHP: Laravel、Symfony、Yii2、ThinkPHP、通用PHP
    - Ruby: Rails、Sinatra、Rack、通用Ruby
    - Docker: Dockerfile、docker-compose
    - 静态站点: 纯HTML/CSS/JS

    额外功能：
    - 自动读取项目部署文档（README.md/DEPLOY.md/INSTALL.md等），提取安装/构建/运行命令
    - 部署文档中的命令优先级高于自动检测结果，应优先使用
    - 检测失败时返回suggestion，建议使用web_search联网搜索部署方式

    返回内容可直接用于panel_deploy_project的project_cfg参数。

    Args:
        path: 项目目录的绝对路径，如网站根目录/myproject
    """
    try:
        path = path.rstrip('/').rstrip('\\')
        return _detect_project_type(path)
    except Exception as e:
        return {'error': f'项目检测失败: {str(e)}'}
