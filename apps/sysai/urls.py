from django.urls import path
from apps.sysai.views.chat import (
    AIChatSessionViewSet, AIChatMessageViewSet, AIChatStreamView,
    AIChatStopView, AIChatConfirmView, AIChatFormSubmitView, AIModelViewSet, AIToolsView,
    AIModelDiscoverView, AIAgentListView, AIAgentAutoCollectView, AICustomAgentView,
    AIToolToggleView, AICompactChatView,
    AIFileUploadView, AIServerFileBrowseView,
    AIMCPStatusView, AIToolsetInfoView,
)
from apps.sysai.views.tools import AIToolInfoView, AISkillListView, AISkillToggleView, AISkillImportView, AISkillDeleteView
from apps.sysai.views.config import AIConfigView, AIUsageView, AIUsageExportView, AIUsageResetView, AIChatExportView

urlpatterns = [
    path('sessions/', AIChatSessionViewSet.as_view(), name='ai_sessions'),
    path('messages/', AIChatMessageViewSet.as_view(), name='ai_messages'),
    path('chat/', AIChatStreamView.as_view(), name='ai_chat'),
    path('chat/stop/', AIChatStopView.as_view(), name='ai_chat_stop'),
    path('chat/confirm/', AIChatConfirmView.as_view(), name='ai_chat_confirm'),
    path('chat/form-submit/', AIChatFormSubmitView.as_view(), name='ai_chat_form_submit'),
    path('chat/compact/', AICompactChatView.as_view(), name='ai_chat_compact'),
    path('models/', AIModelViewSet.as_view(), name='ai_models'),
    path('models/discover/', AIModelDiscoverView.as_view(), name='ai_models_discover'),
    path('tools/', AIToolsView.as_view(), name='ai_tools'),
    path('tools/info/', AIToolInfoView.as_view(), name='ai_tool_info'),
    path('tools/toggle/', AIToolToggleView.as_view(), name='ai_tool_toggle'),
    path('skills/', AISkillListView.as_view(), name='ai_skills'),
    path('skills/toggle/', AISkillToggleView.as_view(), name='ai_skill_toggle'),
    path('skills/import/', AISkillImportView.as_view(), name='ai_skill_import'),
    path('skills/delete/', AISkillDeleteView.as_view(), name='ai_skill_delete'),
    path('agents/', AIAgentListView.as_view(), name='ai_agents'),
    path('agents/auto-collect/', AIAgentAutoCollectView.as_view(), name='ai_agent_auto_collect'),
    path('agents/custom/', AICustomAgentView.as_view(), name='ai_agent_custom'),
    path('config/', AIConfigView.as_view(), name='ai_config'),
    path('usage/', AIUsageView.as_view(), name='ai_usage'),
    path('usage/export/', AIUsageExportView.as_view(), name='ai_usage_export'),
    path('usage/reset/', AIUsageResetView.as_view(), name='ai_usage_reset'),
    path('chat/export/', AIChatExportView.as_view(), name='ai_chat_export'),
    path('files/upload/', AIFileUploadView.as_view(), name='ai_file_upload'),
    path('files/browse/', AIServerFileBrowseView.as_view(), name='ai_file_browse'),
    path('mcp/', AIMCPStatusView.as_view(), name='ai_mcp'),
    path('toolsets/', AIToolsetInfoView.as_view(), name='ai_toolsets'),
]
