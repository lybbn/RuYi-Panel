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
    protocol_name = serializers.SerializerMethodField()
    def get_typename(self,obj):
        return obj.get_type_display()
    def get_protocol_name(self,obj):
        return obj.get_connect_protocol_display()

    class Meta:
        model = TerminalServer
        fields = "__all__"
        read_only_fields = ["id"]

class TerminalCreateUpdateServerSerializer(CustomModelSerializer):
    """
    终端服务器列表后台 简单序列化器
    """

    username = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        connect_protocol = attrs.get('connect_protocol')
        username = attrs.get('username')

        # SSH 协议时 username 必填
        if connect_protocol == 'ssh' and not username:
            raise serializers.ValidationError({"username": "SSH 连接时用户名不能为空"})

        return attrs

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
