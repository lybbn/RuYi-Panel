from django.db import models
from utils.models import BaseModel, make_uuid, table_prefix


from django.db.models import Q


class AIModelManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(Q(name='__sys_config__') | Q(model_name='__sys_config__'))


class AIModelAllManager(models.Manager):
    pass


class AIModel(BaseModel):
    provider_choices = (
        ('openai', 'OpenAI'),
        ('deepseek', 'DeepSeek'),
        ('ollama', 'Ollama'),
        ('longcat', 'Longcat'),
        ('vllm', 'vLLM'),
        ('openrouter', 'OpenRouter'),
        ('azure', 'Azure OpenAI'),
        ('anthropic', 'Anthropic'),
        ('google', 'Google Gemini'),
        ('zhipu', '智谱AI'),
        ('baidu', '百度文心'),
        ('alibaba', '阿里通义'),
        ('xiaomi', '小米MiMo'),
        ('custom', '自定义'),
    )

    model_type_choices = (
        ('LLM', '大语言模型'),
        ('EMBEDDING', '嵌入模型'),
        ('TTS', '语音合成'),
        ('STT', '语音识别'),
        ('IMAGE', '图像模型'),
    )

    name = models.CharField(max_length=200, verbose_name='显示名称')
    model_name = models.CharField(max_length=200, verbose_name='模型标识')
    provider = models.CharField(max_length=50, choices=provider_choices, verbose_name='厂商', db_index=True)
    model_type = models.CharField(max_length=50, choices=model_type_choices, default='LLM', verbose_name='模型类型')
    api_base = models.CharField(max_length=500, verbose_name='API地址', blank=True, default='')
    api_key = models.CharField(max_length=500, verbose_name='API密钥', blank=True, default='')
    api_secret = models.CharField(max_length=500, verbose_name='API Secret', blank=True, default='')
    api_version = models.CharField(max_length=50, verbose_name='API版本', blank=True, default='')
    max_tokens = models.IntegerField(default=4096, verbose_name='最大输出Token数')
    context_length = models.IntegerField(default=8192, verbose_name='上下文窗口大小')
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    top_p = models.FloatField(default=1.0, verbose_name='Top P')
    extra_params = models.JSONField(default=dict, verbose_name='额外参数')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    objects = AIModelManager()
    objects_all = AIModelAllManager()

    class Meta:
        db_table = table_prefix + 'ai_model'
        verbose_name = 'AI模型'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-create_at']
        base_manager_name = 'objects_all'

    def __str__(self):
        return f'{self.name} ({self.provider})'

    @staticmethod
    def get_sys_config():
        """获取AI全局系统配置，不存在则自动创建"""
        config_obj, _ = AIModel.objects_all.get_or_create(
            name='__sys_config__',
            defaults={
                'model_name': '__sys_config__',
                'provider': 'custom',
                'extra_params': {
                    'max_turns': 100,
                    'max_context_messages': 20,
                    'enable_web_search': False,
                    'require_command_confirm': 'medium_high',
                    'show_assistant': True,
                },
            }
        )
        return config_obj


class AIChatSession(BaseModel):
    id = models.CharField(max_length=64, primary_key=True, default=make_uuid, verbose_name='会话ID')
    title = models.CharField(max_length=200, verbose_name='会话标题', default='新对话')
    model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='使用模型')
    agent_id = models.CharField(max_length=64, verbose_name='智能体ID', default='', blank=True)
    user_id = models.IntegerField(verbose_name='用户ID', default=0)
    message_count = models.IntegerField(default=0, verbose_name='消息数量')
    total_tokens = models.IntegerField(default=0, verbose_name='总Token数')
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    is_archived = models.BooleanField(default=False, verbose_name='是否归档')

    class Meta:
        db_table = table_prefix + 'ai_chat_session'
        verbose_name = 'AI会话'
        verbose_name_plural = verbose_name
        ordering = ['-is_pinned', '-update_at']

    def __str__(self):
        return self.title


class AIChatMessage(BaseModel):
    role_choices = (
        ('user', '用户'),
        ('assistant', 'AI助手'),
        ('system', '系统'),
        ('tool', '工具'),
    )

    id = models.CharField(max_length=64, primary_key=True, default=make_uuid, verbose_name='消息ID')
    session = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, related_name='messages', verbose_name='所属会话')
    role = models.CharField(max_length=20, choices=role_choices, verbose_name='角色')
    content = models.TextField(verbose_name='消息内容')
    reasoning_content = models.TextField(verbose_name='思考内容', blank=True, default='')
    tool_calls = models.JSONField(default=list, verbose_name='工具调用')
    tool_call_id = models.CharField(max_length=100, verbose_name='工具调用ID', blank=True, default='')
    tool_name = models.CharField(max_length=100, verbose_name='工具名称', blank=True, default='')
    tokens_used = models.IntegerField(default=0, verbose_name='消耗Token')
    is_stop = models.BooleanField(default=False, verbose_name='是否已停止')
    stop_reason = models.CharField(max_length=20, blank=True, default='', verbose_name='停止原因')
    is_error = models.BooleanField(default=False, verbose_name='是否出错')
    metadata = models.JSONField(default=dict, verbose_name='元数据')

    class Meta:
        db_table = table_prefix + 'ai_chat_message'
        verbose_name = 'AI消息'
        verbose_name_plural = verbose_name
        ordering = ['create_at']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}'


class AIToolConfig(BaseModel):
    tool_type_choices = (
        ('system', '系统监控'),
        ('file', '文件管理'),
        ('service', '服务管理'),
        ('docker', '容器管理'),
        ('database', '数据库管理'),
        ('website', '网站管理'),
        ('security', '安全管理'),
        ('command', '命令执行'),
        ('panel', '面板集成'),
        ('custom', '自定义'),
    )

    name = models.CharField(max_length=100, verbose_name='工具名称', unique=True)
    display_name = models.CharField(max_length=200, verbose_name='显示名称')
    tool_type = models.CharField(max_length=50, choices=tool_type_choices, verbose_name='工具类型')
    description = models.TextField(verbose_name='工具描述', blank=True, default='')
    parameters_schema = models.JSONField(default=dict, verbose_name='参数定义')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    is_dangerous = models.BooleanField(default=False, verbose_name='是否危险操作')
    require_confirm = models.BooleanField(default=False, verbose_name='是否需要确认')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = table_prefix + 'ai_tool_config'
        verbose_name = 'AI工具配置'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'tool_type']

    def __str__(self):
        return self.display_name


class AICompactionLog(BaseModel):
    session = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, verbose_name='所属会话')
    summary = models.TextField(verbose_name='压缩摘要')
    compacted_count = models.IntegerField(default=0, verbose_name='压缩消息数')
    flushed_facts = models.IntegerField(default=0, verbose_name='刷新事实数')
    tokens_before = models.IntegerField(default=0, verbose_name='压缩前Token')
    tokens_after = models.IntegerField(default=0, verbose_name='压缩后Token')

    class Meta:
        db_table = table_prefix + 'ai_compaction_log'
        verbose_name = 'AI压缩日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_at']


class AIEmbedding(BaseModel):
    session = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, verbose_name='所属会话')
    content_text = models.TextField(verbose_name='原始文本')
    embedding = models.BinaryField(verbose_name='向量数据')
    embedding_model = models.CharField(max_length=128, verbose_name='嵌入模型', blank=True, default='')
    source = models.CharField(max_length=32, verbose_name='来源', default='memory')
    content_hash = models.CharField(max_length=64, verbose_name='内容哈希', db_index=True)
    metadata = models.JSONField(default=dict, verbose_name='元数据')

    class Meta:
        db_table = table_prefix + 'ai_embedding'
        verbose_name = 'AI向量嵌入'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['content_hash']),
        ]


class AIUsageLog(BaseModel):
    user_id = models.IntegerField(verbose_name='用户ID', default=0)
    model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, verbose_name='使用模型')
    session = models.ForeignKey(AIChatSession, on_delete=models.SET_NULL, null=True, verbose_name='会话')
    session_title = models.CharField(max_length=200, verbose_name='会话标题', default='', blank=True)
    prompt_tokens = models.IntegerField(default=0, verbose_name='输入Token')
    completion_tokens = models.IntegerField(default=0, verbose_name='输出Token')
    total_tokens = models.IntegerField(default=0, verbose_name='总Token')
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0, verbose_name='费用')
    model_name = models.CharField(max_length=200, verbose_name='模型名称')
    provider = models.CharField(max_length=50, verbose_name='厂商')

    class Meta:
        db_table = table_prefix + 'ai_usage_log'
        verbose_name = 'AI用量日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_at']
