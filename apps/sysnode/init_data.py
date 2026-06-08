import json
import logging

logger = logging.getLogger(__name__)


def get_default_node_categories():
    return [
        {"id": 1, "name": "默认分类", "sort": 0},
        {"id": 2, "name": "生产环境", "sort": 1},
        {"id": 3, "name": "测试环境", "sort": 2},
    ]


def init_node_data(force=False):
    from apps.sysnode.models import NodeCategory

    created_count = 0
    skipped_count = 0

    if force:
        NodeCategory.objects.all().delete()

    categories = get_default_node_categories()
    for cat_data in categories:
        _, created = NodeCategory.objects.get_or_create(
            id=cat_data["id"],
            defaults=cat_data,
        )
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return created_count, skipped_count
