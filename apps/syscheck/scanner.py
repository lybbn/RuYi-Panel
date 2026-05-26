import os
import json
import time
import datetime
import platform
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'syscheck')
RESULT_FILE = os.path.join(DATA_DIR, 'result.json')
BAR_FILE = os.path.join(DATA_DIR, 'bar.json')
IGNORE_FILE = os.path.join(DATA_DIR, 'ignore.json')

_is_scanning = False
_current_os = platform.system().lower()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(filepath, default=None):
    if default is None:
        default = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default


def _write_json(filepath, data):
    _ensure_dir()
    tmp = filepath + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(filepath):
        os.remove(filepath)
    os.rename(tmp, filepath)


def get_ignored():
    return _read_json(IGNORE_FILE, [])


def set_ignore(check_id, ignore=True):
    ignored = get_ignored()
    if ignore and check_id not in ignored:
        ignored.append(check_id)
    elif not ignore and check_id in ignored:
        ignored.remove(check_id)
    _write_json(IGNORE_FILE, ignored)
    saved = get_result()
    target_item = None
    for lst_key in ('risk', 'security', 'ignore'):
        found = [item for item in saved.get(lst_key, []) if item.get('check_id') == check_id]
        if found:
            target_item = found[0]
            saved[lst_key] = [item for item in saved.get(lst_key, []) if item.get('check_id') != check_id]
            break
    if target_item:
        if ignore:
            target_item['ignored'] = True
            saved.setdefault('ignore', []).append(target_item)
        else:
            target_item.pop('ignored', None)
            if target_item.get('status') is False:
                saved.setdefault('risk', []).append(target_item)
            else:
                saved.setdefault('security', []).append(target_item)
        saved['total'] = len(saved.get('risk', [])) + len(saved.get('security', [])) + len(saved.get('ignore', []))
        _recalc_score(saved)
        _write_json(RESULT_FILE, saved)
    return ignored


def get_progress():
    return _read_json(BAR_FILE, {'status': 'idle', 'percentage': 0, 'current': '', 'count': 0, 'score': 100})


def get_result():
    return _read_json(RESULT_FILE, {'score': 0, 'check_time': '', 'risk': [], 'security': [], 'ignore': [], 'total': 0})


def get_summary():
    result = get_result()
    return {
        'score': result.get('score', 0),
        'risk_count': len(result.get('risk', [])),
        'security_count': len(result.get('security', [])),
        'ignore_count': len(result.get('ignore', [])),
        'check_time': result.get('check_time', ''),
        'total': result.get('total', 0),
        'os': result.get('os', _current_os),
    }


def recheck_single(check_id):
    from .checks import get_all_checks
    checks = get_all_checks()
    target = None
    for c in checks:
        if c.check_id == check_id:
            target = c
            break
    if not target:
        return None
    result = target.execute()
    result['check_time'] = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    saved = get_result()
    for lst_key in ('risk', 'security', 'ignore'):
        saved[lst_key] = [item for item in saved.get(lst_key, []) if item.get('check_id') != check_id]
    ignored = get_ignored()
    if check_id in ignored:
        saved.setdefault('ignore', []).append(result)
    elif result.get('status') is False:
        saved.setdefault('risk', []).append(result)
    elif result.get('available') is not False:
        saved.setdefault('security', []).append(result)
    saved['total'] = len(saved.get('risk', [])) + len(saved.get('security', [])) + len(saved.get('ignore', []))
    _recalc_score(saved)
    _write_json(RESULT_FILE, saved)
    return result


def _recalc_score(data):
    score = 100
    for item in data.get('risk', []):
        score -= item.get('level', 1)
    data['score'] = max(score, 0)
    data['risk'] = sorted(data.get('risk', []), key=lambda x: x.get('level', 0), reverse=True)
    data['security'] = sorted(data.get('security', []), key=lambda x: x.get('level', 0), reverse=True)
    data['ignore'] = sorted(data.get('ignore', []), key=lambda x: x.get('level', 0), reverse=True)


def run_scan_async():
    global _is_scanning
    if _is_scanning:
        return False
    _is_scanning = True
    _ensure_dir()
    _write_json(BAR_FILE, {'status': 'scanning', 'percentage': 0, 'current': '', 'count': 0, 'score': 100})
    import threading
    t = threading.Thread(target=_do_scan, daemon=True)
    t.start()
    return True


def _do_scan():
    global _is_scanning
    try:
        from .checks import get_all_checks
        checks = get_all_checks()
        available_checks = [c for c in checks if c.is_available()]
        total = len(available_checks)
        ignored_set = set(get_ignored())
        result = {'score': 100, 'check_time': '', 'risk': [], 'security': [], 'ignore': [], 'total': total}
        for idx, check in enumerate(available_checks):
            pct = int((idx / total) * 100) if total > 0 else 100
            _write_json(BAR_FILE, {
                'status': 'scanning',
                'percentage': pct,
                'current': check.title,
                'count': idx + 1,
                'score': 100,
            })
            item = check.execute()
            item['check_time'] = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            check_id = item.get('check_id', '')
            if check_id in ignored_set:
                item['ignored'] = True
                result['ignore'].append(item)
            elif item.get('status') is False:
                result['risk'].append(item)
            else:
                result['security'].append(item)
        _recalc_score(result)
        result['check_time'] = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        result['os'] = _current_os
        _write_json(RESULT_FILE, result)
        _write_json(BAR_FILE, {
            'status': 'done',
            'percentage': 100,
            'current': '',
            'count': total,
            'score': result['score'],
        })
    except Exception as e:
        logger.error(f"安全扫描异常: {e}")
        _write_json(BAR_FILE, {'status': 'error', 'percentage': 0, 'current': str(e), 'count': 0, 'score': 0})
    finally:
        _is_scanning = False
