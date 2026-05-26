from rest_framework import serializers
from apps.sysai.models import AIModel, AIChatSession, AIChatMessage, AIToolConfig


class AIModelSerializer(serializers.ModelSerializer):
    def validate_api_base(self, value):
        if value:
            value = value.strip()
            if value and not value.endswith('/v1') and not value.endswith('/v1/'):
                if value.endswith('/'):
                    value += 'v1'
                else:
                    value += '/v1'
        return value

    class Meta:
        model = AIModel
        fields = '__all__'
        read_only_fields = ['create_at', 'update_at']


class AIModelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = ['id', 'name', 'model_name', 'provider', 'model_type',
                  'api_base', 'api_key', 'max_tokens', 'temperature', 'top_p',
                  'api_version', 'api_secret', 'extra_params',
                  'is_enabled', 'is_default', 'sort_order']


class AIChatSessionSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True, default='')

    class Meta:
        model = AIChatSession
        fields = ['id', 'title', 'model', 'model_name', 'agent_id', 'user_id', 'message_count',
                  'total_tokens', 'is_pinned', 'is_archived', 'create_at', 'update_at']
        read_only_fields = ['id', 'user_id', 'message_count', 'total_tokens', 'create_at', 'update_at']


class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ['id', 'session', 'role', 'content', 'reasoning_content',
                  'tool_calls', 'tool_call_id', 'tool_name', 'tokens_used',
                  'is_stop', 'is_error', 'metadata', 'create_at']
        read_only_fields = ['id', 'create_at']


class AIToolConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIToolConfig
        fields = '__all__'
        read_only_fields = ['create_at', 'update_at']


class ChatRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    message = serializers.CharField(required=True)
    model_id = serializers.IntegerField(required=False, allow_null=True)
    agent_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    stream = serializers.BooleanField(default=True)
    re_chat = serializers.BooleanField(default=False)
    continue_chat = serializers.BooleanField(default=False)
    chat_record_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    enabled_tools = serializers.ListField(required=False, allow_null=True)
    web_search = serializers.BooleanField(default=False)
    smart_mode = serializers.BooleanField(default=False)
    attachments = serializers.ListField(required=False, allow_null=True)


class ChatStopSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=True)


class ChatResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    message_id = serializers.CharField()
    content = serializers.CharField()
    reasoning_content = serializers.CharField(required=False, default='')
    tool_calls = serializers.ListField(required=False, default=list)
    finish_reason = serializers.CharField(required=False, default='')
