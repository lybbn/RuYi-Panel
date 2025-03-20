from django.core.management.base import BaseCommand
from diskcache import Cache
from django.conf import settings

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2025-03-11
    @EditData:2025-03-11
    @Email:1042594286@qq.com
    @name:清理如意缓存: python manage.py clearCache
    """

    def handle(self, *args, **options):
        print(f"开始清理缓存...")
        cache_location = settings.CACHES['default']['LOCATION']
        cache = Cache(cache_location)
        cache.clear()
        print("清理缓存结束！")