from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sysai', '0010_add_max_output_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aimodel',
            name='provider',
            field=models.CharField(choices=[('openai', 'OpenAI'), ('deepseek', 'DeepSeek'), ('ollama', 'Ollama'), ('longcat', 'Longcat'), ('vllm', 'vLLM'), ('openrouter', 'OpenRouter'), ('azure', 'Azure OpenAI'), ('anthropic', 'Anthropic'), ('google', 'Google Gemini'), ('zhipu', '智谱AI'), ('baidu', '百度文心'), ('alibaba', '阿里通义'), ('custom', '自定义')], db_index=True, max_length=50, verbose_name='厂商'),
        ),
    ]