from django.apps import AppConfig


class SyswafConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.syswaf'
    verbose_name = 'WAF防火墙'

    def ready(self):
        import apps.syswaf.signals
        self._ensure_waf_token()

    def _ensure_waf_token(self):
        from django.conf import settings
        import os
        token_file = os.path.join(settings.RUYI_WAF_DATA_PATH, 'internal_token.ry')
        if not os.path.exists(token_file):
            os.makedirs(os.path.dirname(token_file), exist_ok=True)
            from utils.common import GetRandomSet
            token = GetRandomSet(32)
            with open(token_file, 'w') as f:
                f.write(token)
