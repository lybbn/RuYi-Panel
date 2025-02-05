from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from apps.system.models import TerminalServer

# ================================================= #
# ************** 后台终端服务 view  ************** #
# ================================================= #

class TerminalServerSerializer(CustomModelSerializer):
    """
    终端服务器列表后台 简单序列化器
    """
    typename = serializers.SerializerMethodField()
    def get_typename(self,obj):
        return obj.get_type_display()

    class Meta:
        model = TerminalServer
        fields = "__all__"
        read_only_fields = ["id"]

class TerminalCreateUpdateServerSerializer(CustomModelSerializer):
    """
    终端服务器列表后台 简单序列化器
    """

    class Meta:
        model = TerminalServer
        fields = "__all__"
        read_only_fields = ["id"]

class TerminalServerViewSet(CustomModelViewSet):
    """
    终端服务器列表后台接口
    """
    queryset = TerminalServer.objects.all().order_by('-create_at')
    serializer_class = TerminalServerSerializer
    create_serializer_class = TerminalCreateUpdateServerSerializer
    update_serializer_class = TerminalCreateUpdateServerSerializer
    search_fields = ('host',)