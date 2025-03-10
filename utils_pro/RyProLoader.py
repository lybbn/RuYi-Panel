import os
import platform
import importlib.util
from django.conf import settings

def load_ryprofunc_extension():
    """
    根据系统架构加载相应的 .so .pyd 文件。
    """
    system = platform.system().lower()
    arch = platform.machine().lower()
    lib_path=""
    if system == 'linux':
        lib_name = 'proFuncLoader.so'
        if arch == 'x86_64':
            lib_path = os.path.join(settings.BASE_DIR, 'utils_pro', 'x86_64', lib_name)
        elif arch == 'aarch64':
            lib_path = os.path.join(settings.BASE_DIR, 'utils_pro', 'aarch64', lib_name)
        else:
            raise NotImplementedError(f"不支持该系统架构：{arch} ，请联系如意面板作者！！！")
    elif system == 'windows':
        lib_name = 'proFuncLoader.pyd'
        if arch == 'amd64':
            lib_path = os.path.join(settings.BASE_DIR, 'utils_pro', 'amd64', lib_name)
        else:
            raise NotImplementedError(f"不支持该系统架构：{arch} ，请联系如意面板作者！！！")
    else:
        raise NotImplementedError(f"不支持的操作系统：{system}，请联系如意面板作者！！！")
    
    if not os.path.isfile(lib_path):
        raise FileNotFoundError(f"文件不存在：{lib_path}")

    try:
        spec = importlib.util.spec_from_file_location("proFuncLoader", lib_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # return module
        instance = module.proFuncLoader(settings)
        return instance
    except Exception as e:
        raise ImportError(f"加载失败：{lib_name} from {lib_path}: {e}")