import logging
import os
import uuid
import tempfile
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.sysai.tools.base import registry as tool_registry
from apps.sysai.skills import skill_manager
from apps.sysai.models import AIToolConfig

logger = logging.getLogger(__name__)


class AIToolInfoView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tools_info = tool_registry.get_all_tools_info()

        tool_configs = {}
        for config in AIToolConfig.objects.all():
            tool_configs[config.name] = config

        for info in tools_info:
            tool_name = info.get('name', '')
            config = tool_configs.get(tool_name)
            correct_category = info.get('category', 'default')
            if config:
                if config.tool_type != correct_category and correct_category:
                    config.tool_type = correct_category
                    config.save(update_fields=['tool_type'])
                info['is_visible'] = config.is_enabled
                info['is_enabled'] = config.is_enabled
                if config.display_name and config.display_name != tool_name:
                    info['display_name'] = config.display_name
                if config.description:
                    info['description'] = config.description
                info['category'] = correct_category
            else:
                info['is_visible'] = True
                info['is_enabled'] = True

        categories = {}
        for info in tools_info:
            cat = info.get('category', 'default')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(info)

        return SuccessResponse(data={
            'tools': tools_info,
            'categories': categories,
            'total': len(tools_info),
        })


class AISkillListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skills_info = skill_manager.get_all_skills_info()
        return SuccessResponse(data=skills_info, total=len(skills_info))


class AISkillToggleView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        name = req_data.get('name')
        enabled = req_data.get('enabled', True)

        if not name:
            return ErrorResponse(msg='缺少技能名称')

        result = skill_manager.set_skill_enabled(name, enabled)
        if result.get('status'):
            return DetailResponse(msg=result.get('msg', '设置成功'))
        return ErrorResponse(msg=result.get('msg', '设置失败'))


class AISkillImportView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        import_type = req_data.get('import_type', 'single')

        if import_type == 'single':
            name = req_data.get('name', '')
            content = req_data.get('content', '')
            description = req_data.get('description', '')

            if not name:
                return ErrorResponse(msg='缺少技能名称')
            if not content:
                return ErrorResponse(msg='缺少技能内容')

            result = skill_manager.import_skill_from_content(name, content, description)
            if result.get('status'):
                return SuccessResponse(msg=result.get('msg', '导入成功'), data={'name': result.get('name', name)})
            return ErrorResponse(msg=result.get('msg', '导入失败'))

        elif import_type == 'batch':
            skills = req_data.get('skills', [])
            if not skills or not isinstance(skills, list):
                return ErrorResponse(msg='缺少技能列表或格式不正确')

            result = skill_manager.import_skills_from_array(skills)
            return SuccessResponse(
                msg=result.get('msg', '导入完成'),
                data={
                    'success_count': result.get('success_count', 0),
                    'fail_count': result.get('fail_count', 0),
                    'results': result.get('results', []),
                }
            )

        elif import_type == 'json':
            json_content = req_data.get('json_content', '')
            if not json_content:
                return ErrorResponse(msg='缺少JSON配置内容')

            try:
                import json as json_module
                parsed = json_module.loads(json_content)
            except Exception as e:
                return ErrorResponse(msg=f'JSON格式错误: {e}')

            if isinstance(parsed, dict):
                if 'skills' in parsed and isinstance(parsed['skills'], list):
                    result = skill_manager.import_skills_from_array(parsed['skills'])
                else:
                    result = skill_manager.import_skill_from_json(parsed)
            elif isinstance(parsed, list):
                result = skill_manager.import_skills_from_array(parsed)
            else:
                return ErrorResponse(msg='JSON格式不正确，需要对象或数组')

            if result.get('status'):
                return SuccessResponse(msg=result.get('msg', '导入成功'), data={
                    'success_count': result.get('success_count', 1),
                    'fail_count': result.get('fail_count', 0),
                })
            return ErrorResponse(msg=result.get('msg', '导入失败'))

        elif import_type == 'archive':
            if 'file' not in request.FILES:
                return ErrorResponse(msg='缺少压缩包文件')

            upload_file = request.FILES['file']
            file_name_lower = upload_file.name.lower()
            if file_name_lower.endswith('.tar.gz'):
                file_ext = '.tar.gz'
            elif file_name_lower.endswith('.tar.bz2'):
                file_ext = '.tar.bz2'
            elif file_name_lower.endswith('.tgz'):
                file_ext = '.tgz'
            else:
                file_ext = os.path.splitext(upload_file.name)[1].lower()

            if file_ext not in ('.zip', '.gz', '.bz2', '.tar.gz', '.tgz', '.tar.bz2'):
                return ErrorResponse(msg='不支持的压缩格式，仅支持 zip/tar.gz/tar.bz2')

            max_size = 50 * 1024 * 1024
            if upload_file.size > max_size:
                return ErrorResponse(msg='文件大小不能超过50MB')

            temp_path = os.path.join(tempfile.gettempdir(), f"skill_{uuid.uuid4().hex}{file_ext}")
            try:
                with open(temp_path, 'wb+') as destination:
                    for chunk in upload_file.chunks():
                        destination.write(chunk)

                result = skill_manager.import_skill_from_archive(temp_path)
                if result.get('status'):
                    return SuccessResponse(msg=result.get('msg', '导入成功'), data={
                        'success_count': result.get('success_count', 0),
                        'fail_count': result.get('fail_count', 0),
                        'results': result.get('results', []),
                    })
                return ErrorResponse(msg=result.get('msg', '导入失败'), data={
                    'success_count': result.get('success_count', 0),
                    'fail_count': result.get('fail_count', 0),
                    'results': result.get('results', []),
                })
            except Exception as e:
                return ErrorResponse(msg=f'导入异常: {e}')
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

        else:
            return ErrorResponse(msg='不支持的导入类型')


class AISkillDeleteView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        name = req_data.get('name', '')

        if not name:
            return ErrorResponse(msg='缺少技能名称')

        result = skill_manager.delete_skill(name)
        if result.get('status'):
            return DetailResponse(msg=result.get('msg', '删除成功'))
        return ErrorResponse(msg=result.get('msg', '删除失败'))


class AISkillEvolutionHistoryView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from apps.sysai.agent.skill_evolution import skill_evolution
            limit = int(request.query_params.get('limit', 50))
            history = skill_evolution.get_session_history(limit=limit)
            return SuccessResponse(data=history, total=len(history))
        except Exception as e:
            logger.error(f'获取技能进化历史失败: {e}')
            return ErrorResponse(msg='获取技能进化历史失败')
