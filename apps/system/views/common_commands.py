from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from apps.system.models import CommonCommands

# ================================================= #
# ************** 后台常用命令 view  ************** #
# ================================================= #

class CommonCommandsSerializer(CustomModelSerializer):
    """
    后台常用命令 简单序列化器
    """

    class Meta:
        model = CommonCommands
        fields = "__all__"
        read_only_fields = ["id"]

class CommonCommandsViewSet(CustomModelViewSet):
    """
    后台常用命令后台接口
    list:查询(根据type值获取不同类型的轮播图片)
    create:新增
    update:修改
    retrieve:单例
    destroy:删除
    """
    queryset = CommonCommands.objects.all().order_by('-create_at')
    serializer_class = CommonCommandsSerializer
    search_fields = ('name',)