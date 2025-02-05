"""
Django settings for ruyi project.

# +-------------------------------------------------------------------
# | system: 如意面板配置
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-02-28
# +-------------------------------------------------------------------
# | EditDate: 2024-11-28
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------
"""
import os
import sys
from pathlib import Path
from utils.common import ReadFile,GetBackupPath

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))
RUYI_DATA_BASE_PATH = os.path.join(BASE_DIR, 'data')
RUYI_VHOST_PATH = os.path.join(RUYI_DATA_BASE_PATH,'vhost')
if not os.path.exists(RUYI_VHOST_PATH):os.mkdir(RUYI_VHOST_PATH)
if not os.path.exists(GetBackupPath()):os.mkdir(GetBackupPath())
# ruyi Data
RUYI_SECRET_KEY = 'django-insecure-%^ycfl@-_wpr#=hz*7n%#@c0d6!mlt_l#6ruyi*=+3$(y7-ky'
RUYI_SECRET_KEY_FILE = os.path.join(RUYI_DATA_BASE_PATH,'secret_key.ry')
if os.path.exists(RUYI_SECRET_KEY_FILE):
    RUYI_SECRET_KEY = ReadFile(RUYI_SECRET_KEY_FILE).strip()
RUYI_SECURITY_PATH = '/'
RUYI_SECURITY_PATH_FILE = os.path.join(RUYI_DATA_BASE_PATH,'security_path.ry')
RUYI_SYSTEM_PATH_LIST = [
    '/', '/login/', '/api', '/api/','/api/captcha/','/static/','/media/','/ry/','/ry','/settings','/home','/websites','/databases','/databases','/terminal',
    '/files','/crontab','/logs','/appstore','/firewall',"/monitors"
]
if os.path.exists(RUYI_SECURITY_PATH_FILE):
    RUYI_SECURITY_PATH = ReadFile(RUYI_SECURITY_PATH_FILE).strip()
    RUYI_SECURITY_PATH =RUYI_SECURITY_PATH if RUYI_SECURITY_PATH else '/ry'
if RUYI_SECURITY_PATH in RUYI_SYSTEM_PATH_LIST: RUYI_SECURITY_PATH = '/ry'
if RUYI_SECURITY_PATH.endswith("/"): RUYI_SECURITY_PATH = RUYI_SECURITY_PATH[:-1]
if RUYI_SECURITY_PATH[0] != '/': RUYI_SECURITY_PATH = '/' + RUYI_SECURITY_PATH

#版本
RUYI_SYSVERSION_FILE = os.path.join(BASE_DIR,'sysVersion.ry')
#模板路径
RUYI_TEMPLATE_BASE_PATH = os.path.join(BASE_DIR,'template')
#防火墙是否禁止ping
RUYI_PING_FILE = os.path.join(RUYI_DATA_BASE_PATH,'ping.ry')
#如意面板是否已初始化了
RUYI_ISINITED_FILE = os.path.join(RUYI_DATA_BASE_PATH,'is_inited.ry')
#如意公网IP
RUYI_PUBLICIP_FILE = os.path.join(RUYI_DATA_BASE_PATH,'public_ip.ry')
#如意公网Port
RUYI_PORT_FILE = os.path.join(RUYI_DATA_BASE_PATH,'port.ry')
#如意SSL证书
RUYI_PRIVATEKEY_PATH_FILE = os.path.join(RUYI_DATA_BASE_PATH,"key",'privateKey.pem')
RUYI_CERTKEY_PATH_FILE = os.path.join(RUYI_DATA_BASE_PATH,"key",'certificate.pem')
RUYI_ROOTPFX_PATH_FILE = os.path.join(RUYI_DATA_BASE_PATH,"key",'ruyi_root.pfx')
RUYI_ROOTPFX_PASSWORD_PATH_FILE = os.path.join(RUYI_DATA_BASE_PATH,"key",'ruyi_root_password.ry')
RUYI_SSL_ENABLE_FILE = os.path.join(RUYI_DATA_BASE_PATH,'ssl.ry')#是否开启面板ssl

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = RUYI_SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ["*"]

#路由结尾不强制带斜杠
APPEND_SLASH = False

AUTH_USER_MODEL = 'system.Users'
USERNAME_FIELD = 'username'

# Application definition

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'django_filters',
    'corsheaders',#允许跨域
    'captcha',#验证码
    'django_apscheduler',
    'apps.system',
    'apps.syslogs',
    'apps.systask',
    'apps.sysshop',
    'apps.sysbak',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',#跨域中间件
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'utils.securityMiddleware.SecurityMiddleware',
]

ROOT_URLCONF = 'ruyi.urls'

FRONTEND_ROOT = os.path.join(BASE_DIR, "web","dist")

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_ROOT],
        'APP_DIRS': False,# 启用应用目录下的模板加载
        # 'OPTIONS': {
        #     'context_processors': [
        #         'django.template.context_processors.debug',
        #         'django.template.context_processors.request',
        #         'django.contrib.auth.context_processors.auth',
        #         'django.contrib.messages.context_processors.messages',
        #     ],
        # },
    },
]

WSGI_APPLICATION = 'ruyi.wsgi.application'
ASGI_APPLICATION = 'ruyi.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        "BACKEND": "channels.layers.InMemoryChannelLayer"  # 默认用内存
    },
}

# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR,'data','db','ruyi.db'),
    },
    'logs': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR,'data','db','ruyi_logs.db'),
    },
    'tasks': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR,'data','db','ruyi_tasks.db'),
    },
    'shop': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR,'data','db','ruyi_shop.db'),
    },
    'backup': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR,'data','db','ruyi_backup.db'),
    }
}

# 多数据库路由（分库）
DATABASE_ROUTERS = ['utils.dbRouters.RuyiDatabasesRouter']

# 缓存配置
CACHES = {
    'default': {
        # 'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'BACKEND': 'diskcache.DjangoCache',
        'LOCATION': os.path.join(BASE_DIR,'data','cache'),
        'TIMEOUT': None,# None永不过期
        "OPTIONS": {"MAX_ENTRIES": 1000},
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'zh-Hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

# STATIC_URL = 'static/'
STATIC_URL = '/static/'

# STATICFILES_DIRS = [
#     FRONTEND_ROOT,
# ]
# 收集静态文件，必须将 MEDIA_ROOT,STATICFILES_DIRS先注释
# python manage.py collectstatic
# STATIC_ROOT=os.path.join(BASE_DIR,'static')
STATIC_ROOT=FRONTEND_ROOT

MEDIA_URL = "/media/"
# 项目中存储上传文件的根目录
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

#指定collectstatic只收集STATICFILES_DIRS指定的目录
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
]
# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================================= #
# ******************* 跨域的配置 ******************* #
# ================================================= #
# 如果为True，则将不使用白名单，并且将接受所有来源。默认为False
#允许跨域
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_ALL_ORIGINS = True #新版 ACCESS_CONTROL_ALLOW_ORIGIN = '*' ,不能与CORS_ALLOW_CREDENTIALS一起使用
# 允许cookie
# CORS_ALLOW_CREDENTIALS = True  # 指明在跨域访问中，后端是否支持对cookie的操作
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'None'

X_FRAME_OPTIONS = 'SAMEORIGIN'#SAMEORIGIN允许同源iframe嵌套、 DENY不允许iframe、ALLOW-FROM http://xxx.com指定uri嵌套、ALLOWALL 允许所有域名嵌套
CORS_EXPOSE_HEADERS = ['Content-Disposition'] # Content-Disposition 头部添加到 Access-Control-Expose-Headers 中，允许客户端 JavaScript 访问该头部
#解决开发环境csrf问题
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8680',
]
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8680',
]
# ================================================= #
# *************** REST_FRAMEWORK配置 *************** #
# ================================================= #

REST_FRAMEWORK = {
    'DATETIME_FORMAT': "%Y-%m-%d %H:%M:%S",  # 日期时间格式配置
    'DATE_FORMAT': "%Y-%m-%d",
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',

    ),
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.CustomPagination',  # 自定义分页
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # 'rest_framework_simplejwt.authentication.JWTTokenUserAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
    ),
    #限速设置
    'DEFAULT_THROTTLE_CLASSES': (
            'rest_framework.throttling.AnonRateThrottle',   #未登陆用户
            'rest_framework.throttling.UserRateThrottle'    #登陆用户
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',                   #未登录用户每分钟可以请求60次，还可以设置'100/day',天数
        'user': '160/minute'                    #已登录用户每分钟可以请求160次
    },
    'EXCEPTION_HANDLER': 'utils.exception.CustomExceptionHandler',  # 自定义的异常处理
    'DEFAULT_THROTTLE_FAILURE_MESSAGE': '请求太频繁，请稍后再试',
    #线上部署正式环境，关闭web接口测试页面
    'DEFAULT_RENDERER_CLASSES':(
        'rest_framework.renderers.JSONRenderer',
    ),
}
# ================================================= #
# ****************** simplejwt配置 ***************** #
# ================================================= #
from datetime import timedelta

SIMPLE_JWT = {
    # token有效时长
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    # token刷新后的有效时间
    'REFRESH_TOKEN_LIFETIME': timedelta(days=2),
    # 设置header字段Authorization的值得前缀： JWT accesstoken字符串
    'AUTH_HEADER_TYPES': ('JWT',),
    'ROTATE_REFRESH_TOKENS': True
}

# ================================================= #
# **************** 验证码配置  ******************* #
# ================================================= #
CAPTCHA_STATE = True
CAPTCHA_IMAGE_SIZE = (160, 60)  # 设置 captcha 图片大小
CAPTCHA_LENGTH = 4  # 字符个数
CAPTCHA_TIMEOUT = 3  # 超时(minutes)
CAPTCHA_OUTPUT_FORMAT = '%(image)s %(text_field)s %(hidden_field)s '
CAPTCHA_FONT_SIZE = 42  # 字体大小
CAPTCHA_FOREGROUND_COLOR = '#008040'  # 前景色
CAPTCHA_BACKGROUND_COLOR = '#FFFFFF'  # 背景色
CAPTCHA_NOISE_FUNCTIONS = (
    'captcha.helpers.noise_arcs', # 线
    # 'captcha.helpers.noise_dots', # 点
)
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge' #字母验证码
# CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.math_challenge' # 加减乘除验证码

# ================================================= #
# ********************* 日志配置 ******************* #
# ================================================= #
# log 配置部分BEGIN #
SERVER_LOGS_FILE = os.path.join(BASE_DIR, 'logs', 'server.log')
ERROR_LOGS_FILE = os.path.join(BASE_DIR, 'logs', 'error.log')
TASK_LOGS_FILE = os.path.join(BASE_DIR, 'logs', 'task.log')
if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
    os.makedirs(os.path.join(BASE_DIR, 'logs'))

# 格式:[2020-04-22 23:33:01][micoservice.apps.ready():16] [INFO] 这是一条日志:
# 格式:[日期][模块.函数名称():行号] [级别] 信息
STANDARD_LOG_FORMAT = '[%(asctime)s][%(name)s.%(funcName)s():%(lineno)d] [%(levelname)s] %(message)s'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,# 不禁用默认日志
    'formatters': {
        'standard': {
            'format': STANDARD_LOG_FORMAT
        },
        'console': {
            'format': STANDARD_LOG_FORMAT,
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'file': {
            'format': STANDARD_LOG_FORMAT,
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': SERVER_LOGS_FILE,
            'maxBytes': 1024 * 1024 * 20,  # 20 MB
            'backupCount': 10,  # 最多备份10个
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOGS_FILE,
            'maxBytes': 1024 * 1024 * 20,  # 20 MB
            'backupCount': 10,  # 最多备份10个
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
        'scheduler_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': TASK_LOGS_FILE,
            'maxBytes': 1024 * 1024 * 20, 
            'backupCount': 10,
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        # default日志
        '': {
            'handlers': ['console', 'error', 'file'],
            'level': 'INFO',
        },
        'apscheduler.scheduler': {
            'handlers': ['scheduler_file'],
            'level': 'INFO',
            'propagate': False, #False 不传播到父logger，即只在本logger中记录日志，不在传播的其他logger
        },
    }
}

# 存储 任务Logger 实例的字典
TASK_LOGGERS_DIC = {}