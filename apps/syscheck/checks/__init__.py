import importlib
import os
import logging

logger = logging.getLogger(__name__)

_checks_loaded = False

def load_all_checks():
    global _checks_loaded
    if _checks_loaded:
        return
    checks_dir = os.path.dirname(__file__)
    for fname in os.listdir(checks_dir):
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        module_name = fname[:-3]
        if module_name in ('base',):
            continue
        try:
            importlib.import_module(f'.{module_name}', package=__name__)
        except Exception as e:
            logger.error(f"加载安全检查模块 [{module_name}] 失败: {e}")
    _checks_loaded = True

def get_all_checks():
    from .base import CHECK_REGISTRY
    load_all_checks()
    return [cls() for cls in CHECK_REGISTRY]
