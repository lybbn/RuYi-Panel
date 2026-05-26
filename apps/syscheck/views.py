from utils.customView import CustomAPIView
from utils.jsonResponse import DetailResponse, ErrorResponse
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic
from . import scanner


class SyscheckScanView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        started = scanner.run_scan_async()
        if not started:
            return ErrorResponse(msg='扫描任务正在运行中，请稍后再试')
        return DetailResponse(msg='扫描已启动')


class SyscheckProgressView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return DetailResponse(data=scanner.get_progress())


class SyscheckResultView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return DetailResponse(data=scanner.get_result())


class SyscheckSummaryView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return DetailResponse(data=scanner.get_summary())


class SyscheckIgnoreView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        params = get_parameter_dic(request)
        check_id = params.get('check_id', '')
        ignore = params.get('ignore', True)
        if not check_id:
            return ErrorResponse(msg='参数check_id不能为空')
        scanner.set_ignore(check_id, ignore)
        return DetailResponse(msg=f'已{"忽略" if ignore else "取消忽略"}')


class SyscheckRecheckView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        params = get_parameter_dic(request)
        check_id = params.get('check_id', '')
        if not check_id:
            return ErrorResponse(msg='参数check_id不能为空')
        result = scanner.recheck_single(check_id)
        if not result:
            return ErrorResponse(msg='未找到该检查项')
        return DetailResponse(data=result, msg='重新检测完成')
