from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('systask', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='crontabtask',
            name='ai_prompt',
            field=models.TextField(blank=True, null=True, verbose_name='AI任务提示词', help_text='AI执行模式的提示词，AI将根据此提示自主完成任务'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='ai_deliver',
            field=models.CharField(default='none', max_length=100, verbose_name='结果投递渠道', help_text='任务执行结果投递到哪个通知渠道，逗号分隔多个渠道'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='ai_silent',
            field=models.BooleanField(default=False, verbose_name='静默模式', help_text='AI返回[SILENT]时不投递通知'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='ai_context_from',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='上游任务ID', help_text='从指定任务的最近执行结果获取上下文'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='ai_timeout',
            field=models.IntegerField(default=300, verbose_name='AI执行超时(秒)', help_text='AI Agent执行超时时间，默认300秒'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='ai_last_result',
            field=models.TextField(blank=True, null=True, verbose_name='最近AI执行结果'),
        ),
        migrations.AddField(
            model_name='crontabtask',
            name='run_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='一次性执行时间', help_text='period_type=9时指定执行时间'),
        ),
        migrations.AlterField(
            model_name='crontabtask',
            name='type',
            field=models.SmallIntegerField(
                choices=[(0, 'shell'), (1, 'bk_database'), (2, 'bk_website'), (3, 'bk_dir'), (4, 'access_url'), (5, 'ai_task')],
                default=0,
                verbose_name='类型',
            ),
        ),
        migrations.AlterField(
            model_name='crontabtask',
            name='period_type',
            field=models.SmallIntegerField(
                choices=[(0, ''), (1, '每天'), (2, '每周'), (3, '每月'), (4, '每小时'), (5, '每隔N天'), (6, '每隔N时'), (7, '每隔N分'), (8, '每隔N秒'), (9, '一次性')],
                default=0,
                verbose_name='周期类型',
            ),
        ),
    ]
