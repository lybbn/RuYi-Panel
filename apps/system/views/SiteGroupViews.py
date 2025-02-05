from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from apps.system.models import SiteGroup
from utils.common import get_parameter_dic
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse

# ================================================= #
# ************** 网站分组 view  ************** #
# ================================================= #

class SiteGroupSerializer(CustomModelSerializer):
    """
    网站分组 简单序列化器
    """

    class Meta:
        model = SiteGroup
        fields = "__all__"
        read_only_fields = ["id"]

class SiteGroupCreateUpdateServerSerializer(CustomModelSerializer):
    """
    网站分组 简单序列化器
    """

    class Meta:
        model = SiteGroup
        fields = "__all__"
        read_only_fields = ["id"]

class SiteGroupViewSet(CustomModelViewSet):
    """
    网站分组接口
    """
    queryset = SiteGroup.objects.all().order_by('-create_at')
    serializer_class = SiteGroupSerializer
    create_serializer_class = SiteGroupCreateUpdateServerSerializer
    update_serializer_class = SiteGroupCreateUpdateServerSerializer
    search_fields = ('name',)

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name","")
        if SiteGroup.objects.filter(name=name).exists():
            return ErrorResponse(msg="存在同名分组")
        reqData['is_default'] = False
        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return DetailResponse(data=serializer.data, msg="新增成功")
    
    def update(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name","")
        reqData['is_default'] = False
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.is_default:
            return ErrorResponse(msg="默认分组禁止编辑")
        if SiteGroup.objects.exclude(id=instance.id).filter(name=name).exists():
            return ErrorResponse(msg="存在同名分组")
        serializer = self.get_serializer(instance, data=reqData, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return DetailResponse(data=serializer.data, msg="更新成功")
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object_list()
        if instance[0].is_default:
            return ErrorResponse(msg="默认分组禁止删除")
        self.perform_destroy(instance)
        return DetailResponse(data=[], msg="删除成功")

