import os
import platform
import logging

logger = logging.getLogger(__name__)

RISK_LEVEL_LOW = 1
RISK_LEVEL_MEDIUM = 2
RISK_LEVEL_HIGH = 3

RISK_LEVEL_MAP = {
    RISK_LEVEL_LOW: {'label': '低', 'color': '#e6a23c'},
    RISK_LEVEL_MEDIUM: {'label': '中', 'color': '#f56c6c'},
    RISK_LEVEL_HIGH: {'label': '高', 'color': '#f56c6c'},
}

CHECK_REGISTRY = []

_is_windows = platform.system().lower() == 'windows'


def register_check(cls):
    CHECK_REGISTRY.append(cls)
    return cls


class BaseCheck:
    check_id = ''
    title = ''
    description = ''
    level = RISK_LEVEL_LOW
    category = 'basic'
    platform = 'all'

    def run(self):
        raise NotImplementedError

    def is_available(self):
        if self.platform == 'linux' and _is_windows:
            return False
        if self.platform == 'windows' and not _is_windows:
            return False
        return True

    def execute(self):
        if not self.is_available():
            return {
                'check_id': self.check_id,
                'title': self.title,
                'description': self.description,
                'level': self.level,
                'level_label': RISK_LEVEL_MAP.get(self.level, {}).get('label', '低'),
                'category': self.category,
                'status': None,
                'msg': '当前系统不适用',
                'tips': [],
                'available': False,
            }
        try:
            status, msg, tips = self.run()
        except Exception as e:
            logger.error(f"安全检查 [{self.check_id}] 执行异常: {e}")
            status, msg, tips = True, '检查异常', []
        return {
            'check_id': self.check_id,
            'title': self.title,
            'description': self.description,
            'level': self.level,
            'level_label': RISK_LEVEL_MAP.get(self.level, {}).get('label', '低'),
            'category': self.category,
            'status': status,
            'msg': msg,
            'tips': tips if isinstance(tips, list) else [tips],
            'available': True,
        }
