import os
import json
import base64
import io
import time
from django.conf import settings
from utils.common import ReadFile, WriteFile

OTP_CONFIG_FILE = os.path.join(settings.RUYI_DATA_BASE_PATH, 'otp_config.json')
OTP_TEMP_TOKEN_DIR = os.path.join(settings.RUYI_DATA_BASE_PATH, 'otp_tokens')


def get_otp_config():
    if os.path.exists(OTP_CONFIG_FILE):
        try:
            content = ReadFile(OTP_CONFIG_FILE)
            return json.loads(content)
        except Exception:
            pass
    return {'otp_enable': False, 'otp_secret': ''}


def save_otp_config(config):
    WriteFile(OTP_CONFIG_FILE, json.dumps(config))


def generate_otp_secret():
    try:
        import pyotp
        return pyotp.random_base32()
    except ImportError:
        return None


def get_otp_qrcode_base64(secret, username="admin"):
    try:
        import pyotp
        import qrcode
        issuer_name = getattr(settings, 'APP_NAME', 'RuyiPanel')
        otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer_name
        )
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(otp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return "data:image/png;base64," + img_base64
    except ImportError:
        return None


def verify_otp_code(secret, code):
    if not secret or not code:
        return False
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except ImportError:
        return False


def is_otp_enabled():
    config = get_otp_config()
    return config.get('otp_enable', False) and bool(config.get('otp_secret', ''))


def disable_otp():
    config = get_otp_config()
    config['otp_enable'] = False
    config['otp_secret'] = ''
    save_otp_config(config)
    return True


def save_otp_temp_token(temp_token, user_id, username):
    if not os.path.exists(OTP_TEMP_TOKEN_DIR):
        os.makedirs(OTP_TEMP_TOKEN_DIR, exist_ok=True)
    token_file = os.path.join(OTP_TEMP_TOKEN_DIR, f'{temp_token}.json')
    data = {
        'user_id': user_id,
        'username': username,
        'created_at': time.time()
    }
    WriteFile(token_file, json.dumps(data))


def get_otp_temp_token(temp_token):
    token_file = os.path.join(OTP_TEMP_TOKEN_DIR, f'{temp_token}.json')
    if not os.path.exists(token_file):
        return None
    try:
        content = ReadFile(token_file)
        data = json.loads(content)
        if time.time() - data.get('created_at', 0) > 300:
            delete_otp_temp_token(temp_token)
            return None
        return data
    except Exception:
        return None


def delete_otp_temp_token(temp_token):
    token_file = os.path.join(OTP_TEMP_TOKEN_DIR, f'{temp_token}.json')
    try:
        if os.path.exists(token_file):
            os.remove(token_file)
    except Exception:
        pass


def clean_expired_otp_tokens():
    if not os.path.exists(OTP_TEMP_TOKEN_DIR):
        return
    now = time.time()
    for filename in os.listdir(OTP_TEMP_TOKEN_DIR):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(OTP_TEMP_TOKEN_DIR, filename)
        try:
            content = ReadFile(filepath)
            data = json.loads(content)
            if now - data.get('created_at', 0) > 300:
                os.remove(filepath)
        except Exception:
            try:
                os.remove(filepath)
            except Exception:
                pass
