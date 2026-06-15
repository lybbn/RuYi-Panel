from django.db import models
from utils.models import table_prefix, BaseModel


class NodeCategory(BaseModel):

    name = models.CharField(max_length=128, verbose_name='分类名称')
    sort = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = table_prefix + "node_category"
        verbose_name = '节点分类'
        verbose_name_plural = verbose_name
        ordering = ('sort', '-create_at')
        app_label = "sysnode"

    def __str__(self):
        return self.name


class ClusterNode(BaseModel):
    NODE_TYPE_CHOICES = (
        ("api", "API节点"),
        ("ssh", "SSH节点"),
    )
    STATUS_CHOICES = (
        (0, "正常"),
        (1, "连接失败"),
        (2, "获取数据失败"),
        (3, "未连接"),
        (4, "重启中"),
    )

    name = models.CharField(max_length=255, verbose_name='节点名称')
    address = models.CharField(max_length=512, verbose_name='节点地址', blank=True, default='')
    server_ip = models.CharField(max_length=128, verbose_name='服务器IP', blank=True, default='')
    node_type = models.CharField(max_length=16, choices=NODE_TYPE_CHOICES, default='api', verbose_name='节点类型')
    api_key = models.CharField(max_length=512, verbose_name='API Key', blank=True, default='')
    ssh_conf = models.TextField(verbose_name='SSH配置', blank=True, default='{}')
    category = models.ForeignKey(NodeCategory, null=True, blank=True, verbose_name='所属分类', on_delete=models.SET_NULL, db_constraint=False)
    status = models.IntegerField(choices=STATUS_CHOICES, default=3, verbose_name='节点状态')
    remarks = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')
    is_local = models.BooleanField(default=False, verbose_name='是否本机节点')
    os_info = models.CharField(max_length=255, verbose_name='操作系统', blank=True, default='')
    cpu_info = models.CharField(max_length=255, verbose_name='CPU信息', blank=True, default='')
    cpu_count = models.IntegerField(default=0, verbose_name='CPU核心数')
    cpu_usage = models.FloatField(default=0, verbose_name='CPU使用率')
    mem_total = models.BigIntegerField(default=0, verbose_name='内存总量(MB)')
    mem_used = models.BigIntegerField(default=0, verbose_name='内存已用(MB)')
    mem_usage = models.FloatField(default=0, verbose_name='内存使用率')
    disk_total = models.BigIntegerField(default=0, verbose_name='磁盘总量(GB)')
    disk_used = models.BigIntegerField(default=0, verbose_name='磁盘已用(GB)')
    disk_usage = models.FloatField(default=0, verbose_name='磁盘使用率')
    uptime = models.BigIntegerField(default=0, verbose_name='运行时间(秒)')
    last_monitor_time = models.DateTimeField(null=True, blank=True, verbose_name='最后监控时间')
    error_msg = models.TextField(verbose_name='错误信息', blank=True, default='')
    error_num = models.IntegerField(default=0, verbose_name='错误次数')

    class Meta:
        db_table = table_prefix + "cluster_node"
        verbose_name = '集群节点'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.name


class UpstreamResource(BaseModel):
    ALGORITHM_CHOICES = (
        ("round_robin", "轮询"),
        ("least_conn", "最少连接"),
        ("ip_hash", "IP Hash"),
    )
    LOAD_TYPE_CHOICES = (
        ("http", "HTTP"),
        ("tcp", "TCP"),
        ("udp", "UDP"),
    )

    name = models.CharField(max_length=128, verbose_name='资源名称', unique=True)
    load_type = models.CharField(max_length=16, choices=LOAD_TYPE_CHOICES, default='http', verbose_name='协议类型')
    algorithm = models.CharField(max_length=32, choices=ALGORITHM_CHOICES, default='round_robin', verbose_name='调度算法')
    keepalive = models.IntegerField(default=32, verbose_name='保持连接数')
    proxy_next_upstream = models.CharField(max_length=512, verbose_name='故障转移策略', blank=True, default='error timeout http_500 http_502 http_503 http_504')
    proxy_connect_timeout = models.CharField(max_length=16, verbose_name='连接超时', default='30s')
    proxy_read_timeout = models.CharField(max_length=16, verbose_name='读取超时', default='30s')
    proxy_send_timeout = models.CharField(max_length=16, verbose_name='发送超时', default='30s')
    ps = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')
    status = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = table_prefix + "upstream_resource"
        verbose_name = 'Upstream资源组'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.name


class UpstreamServer(BaseModel):
    NODE_FLAG_CHOICES = (
        ("", "在线"),
        ("backup", "备份"),
        ("down", "下线"),
    )

    resource = models.ForeignKey(UpstreamResource, on_delete=models.CASCADE, verbose_name='所属资源', db_constraint=False, related_name='servers')
    server = models.CharField(max_length=256, verbose_name='服务器地址(IP:Port)')
    weight = models.IntegerField(default=1, verbose_name='权重')
    max_fails = models.IntegerField(default=2, verbose_name='最大失败次数')
    fail_timeout = models.CharField(max_length=16, default='10s', verbose_name='失败超时')
    max_conns = models.IntegerField(default=0, verbose_name='最大连接数(0=不限)')
    flag = models.CharField(max_length=16, choices=NODE_FLAG_CHOICES, default='', blank=True, verbose_name='节点标记')
    ps = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')

    class Meta:
        db_table = table_prefix + "upstream_server"
        verbose_name = 'Upstream后端服务器'
        verbose_name_plural = verbose_name
        ordering = ('create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.server


class LoadBalanceSite(BaseModel):
    LOCATION_MATCH_CHOICES = (
        ("prefix", "前缀匹配(/)"),
        ("exact", "精确匹配(=)"),
        ("regex_case", "区分大小写正则(~)"),
        ("regex_nocase", "不区分大小写正则(~*)"),
    )

    site = models.ForeignKey('system.Sites', on_delete=models.DO_NOTHING, verbose_name='关联站点', db_constraint=False, related_name='lb_sites')
    upstream = models.ForeignKey(UpstreamResource, on_delete=models.CASCADE, verbose_name='Upstream资源', db_constraint=False, related_name='lb_sites')
    location_path = models.CharField(max_length=255, verbose_name='匹配路径', default='/')
    location_match = models.CharField(max_length=16, choices=LOCATION_MATCH_CHOICES, default='prefix', verbose_name='匹配方式')
    proxy_host = models.CharField(max_length=255, verbose_name='发送域名', default='$host')
    enable_websocket = models.BooleanField(default=False, verbose_name='启用WebSocket')
    enable_cache = models.BooleanField(default=False, verbose_name='启用缓存')
    cache_time = models.CharField(max_length=32, verbose_name='缓存时间', blank=True, default='1d')
    cache_suffix = models.TextField(verbose_name='缓存后缀', blank=True, default='css,js,jpg,jpeg,gif,png,webp,woff,eot,ttf,svg,ico')
    custom_conf = models.TextField(verbose_name='自定义配置', blank=True, default='')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    ps = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')

    class Meta:
        db_table = table_prefix + "load_balance_site"
        verbose_name = '负载均衡站点'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return f"{self.site.name} -> {self.upstream.name}"


class MysqlReplication(BaseModel):
    REPLICATE_MODE_CHOICES = (
        ("async", "异步复制"),
        ("semi_sync", "半同步复制"),
    )
    BINLOG_MODE_CHOICES = (
        ("traditional", "传统模式(文件位置)"),
        ("gtid", "GTID模式"),
    )
    CONFIG_STATUS_CHOICES = (
        ("pending", "待配置"),
        ("configuring", "配置中"),
        ("done", "已完成"),
        ("failed", "配置失败"),
    )
    RUN_STATUS_CHOICES = (
        ("running", "运行中"),
        ("stopped", "已停止"),
        ("error", "异常"),
    )

    name = models.CharField(max_length=255, verbose_name='复制名称')
    master_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='主库节点', db_constraint=False, related_name='mysql_master_nodes')
    slave_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='从库节点', db_constraint=False, related_name='mysql_slave_nodes')
    master_ip = models.CharField(max_length=128, verbose_name='主库IP')
    master_port = models.IntegerField(default=3306, verbose_name='主库端口')
    slave_ip = models.CharField(max_length=128, verbose_name='从库IP')
    slave_port = models.IntegerField(default=3306, verbose_name='从库端口')
    db_user = models.CharField(max_length=128, verbose_name='复制用户', default='repl')
    db_pass = models.CharField(max_length=255, verbose_name='复制密码', blank=True, default='')
    root_user = models.CharField(max_length=128, verbose_name='Root用户', default='root')
    root_pass = models.CharField(max_length=255, verbose_name='Root密码', blank=True, default='')
    replicate_db = models.CharField(max_length=512, verbose_name='复制数据库(多个逗号分隔)', blank=True, default='')
    replicate_mode = models.CharField(max_length=16, choices=REPLICATE_MODE_CHOICES, default='async', verbose_name='复制模式')
    binlog_mode = models.CharField(max_length=16, choices=BINLOG_MODE_CHOICES, default='gtid', verbose_name='Binlog模式')
    skip_errors = models.CharField(max_length=512, verbose_name='跳过错误码', blank=True, default='1007,1050')
    config_status = models.CharField(max_length=16, choices=CONFIG_STATUS_CHOICES, default='pending', verbose_name='配置状态')
    run_status = models.CharField(max_length=16, choices=RUN_STATUS_CHOICES, default='stopped', verbose_name='运行状态')
    io_status = models.CharField(max_length=16, verbose_name='IO线程状态', blank=True, default='')
    sql_status = models.CharField(max_length=16, verbose_name='SQL线程状态', blank=True, default='')
    master_log_file = models.CharField(max_length=255, verbose_name='主库日志文件', blank=True, default='')
    master_log_pos = models.BigIntegerField(default=0, verbose_name='主库日志位置')
    executed_gtid_set = models.TextField(verbose_name='已执行GTID集合', blank=True, default='')
    seconds_behind_master = models.IntegerField(default=-1, verbose_name='延迟秒数(-1=未知)')
    last_check_time = models.DateTimeField(null=True, blank=True, verbose_name='最后检查时间')
    error_msg = models.TextField(verbose_name='错误信息', blank=True, default='')
    current_step = models.IntegerField(default=0, verbose_name='当前步骤索引')
    config_log = models.TextField(verbose_name='配置日志', blank=True, default='')
    ps = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')

    class Meta:
        db_table = table_prefix + "mysql_replication"
        verbose_name = 'MySQL主从复制'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.name


class RedisReplication(BaseModel):
    CONFIG_STATUS_CHOICES = (
        ("pending", "待配置"),
        ("configuring", "配置中"),
        ("done", "已完成"),
        ("failed", "配置失败"),
    )
    RUN_STATUS_CHOICES = (
        ("running", "运行中"),
        ("stopped", "已停止"),
        ("error", "异常"),
    )

    name = models.CharField(max_length=255, verbose_name='复制组名称')
    master_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='主库节点', db_constraint=False, related_name='redis_master_nodes')
    master_ip = models.CharField(max_length=128, verbose_name='主库IP')
    master_port = models.IntegerField(default=6379, verbose_name='主库端口')
    master_password = models.CharField(max_length=255, verbose_name='主库密码', blank=True, default='')
    config_status = models.CharField(max_length=16, choices=CONFIG_STATUS_CHOICES, default='pending', verbose_name='配置状态')
    run_status = models.CharField(max_length=16, choices=RUN_STATUS_CHOICES, default='stopped', verbose_name='运行状态')
    slave_count = models.IntegerField(default=0, verbose_name='从库数量')
    normal_slaves = models.IntegerField(default=0, verbose_name='正常从库数')
    avg_lag = models.FloatField(default=0, verbose_name='平均延迟(ms)')
    last_check_time = models.DateTimeField(null=True, blank=True, verbose_name='最后检查时间')
    error_msg = models.TextField(verbose_name='错误信息', blank=True, default='')
    ps = models.CharField(max_length=512, verbose_name='备注', blank=True, default='')

    class Meta:
        db_table = table_prefix + "redis_replication"
        verbose_name = 'Redis主从复制'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.name


class RedisReplicationSlave(BaseModel):
    replication = models.ForeignKey(RedisReplication, on_delete=models.CASCADE, verbose_name='所属复制组', db_constraint=False, related_name='slaves')
    slave_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='从库节点', db_constraint=False)
    slave_ip = models.CharField(max_length=128, verbose_name='从库IP')
    slave_port = models.IntegerField(default=6379, verbose_name='从库端口')
    slave_password = models.CharField(max_length=255, verbose_name='从库密码', blank=True, default='')
    link_status = models.CharField(max_length=32, verbose_name='连接状态', blank=True, default='')
    offset = models.BigIntegerField(default=0, verbose_name='复制偏移量')
    lag = models.BigIntegerField(default=0, verbose_name='延迟(字节)')

    class Meta:
        db_table = table_prefix + "redis_replication_slave"
        verbose_name = 'Redis从库节点'
        verbose_name_plural = verbose_name
        ordering = ('create_at',)
        app_label = "sysnode"

    def __str__(self):
        return f"{self.slave_ip}:{self.slave_port}"


class FileTransferTask(BaseModel):
    TASK_ACTION_CHOICES = (
        ("upload", "上传"),
        ("download", "下载"),
    )
    TASK_STATUS_CHOICES = (
        ("pending", "等待中"),
        ("running", "传输中"),
        ("complete", "已完成"),
        ("failed", "失败"),
        ("cancelled", "已取消"),
    )
    DEFAULT_MODE_CHOICES = (
        ("cover", "覆盖"),
        ("ignore", "跳过"),
        ("rename", "重命名"),
    )

    source_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='源节点', db_constraint=False, related_name='source_transfer_tasks')
    target_node = models.ForeignKey(ClusterNode, on_delete=models.CASCADE, verbose_name='目标节点', db_constraint=False, related_name='target_transfer_tasks')
    task_action = models.CharField(max_length=16, choices=TASK_ACTION_CHOICES, default='upload', verbose_name='任务类型')
    status = models.CharField(max_length=16, choices=TASK_STATUS_CHOICES, default='pending', verbose_name='任务状态')
    source_path_list = models.TextField(verbose_name='源文件路径列表', blank=True, default='[]')
    target_path = models.CharField(max_length=1024, verbose_name='目标路径')
    default_mode = models.CharField(max_length=16, choices=DEFAULT_MODE_CHOICES, default='cover', verbose_name='冲突处理方式')
    total_files = models.IntegerField(default=0, verbose_name='总文件数')
    total_size = models.BigIntegerField(default=0, verbose_name='总文件大小(字节)')
    transferred_files = models.IntegerField(default=0, verbose_name='已传输文件数')
    transferred_size = models.BigIntegerField(default=0, verbose_name='已传输大小(字节)')
    progress = models.FloatField(default=0, verbose_name='进度百分比')
    speed = models.FloatField(default=0, verbose_name='传输速度(字节/秒)')
    error_msg = models.TextField(verbose_name='错误信息', blank=True, default='')
    created_by = models.CharField(max_length=255, verbose_name='创建者', blank=True, default='')

    class Meta:
        db_table = table_prefix + "file_transfer_task"
        verbose_name = '文件传输任务'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysnode"

    def __str__(self):
        return f"{self.source_node.name} -> {self.target_node.name}"


class FileTransferRecord(BaseModel):
    RECORD_STATUS_CHOICES = (
        ("pending", "等待中"),
        ("transferring", "传输中"),
        ("complete", "已完成"),
        ("failed", "失败"),
        ("skipped", "已跳过"),
    )

    task = models.ForeignKey(FileTransferTask, on_delete=models.CASCADE, verbose_name='所属任务', db_constraint=False, related_name='records')
    src_file = models.CharField(max_length=1024, verbose_name='源文件路径')
    dst_file = models.CharField(max_length=1024, verbose_name='目标文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    is_dir = models.BooleanField(default=False, verbose_name='是否目录')
    status = models.CharField(max_length=16, choices=RECORD_STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.FloatField(default=0, verbose_name='进度百分比')
    transferred_size = models.BigIntegerField(default=0, verbose_name='已传输大小(字节)')
    speed = models.FloatField(default=0, verbose_name='传输速度(字节/秒)')
    error_msg = models.TextField(verbose_name='错误信息', blank=True, default='')

    class Meta:
        db_table = table_prefix + "file_transfer_record"
        verbose_name = '文件传输记录'
        verbose_name_plural = verbose_name
        ordering = ('create_at',)
        app_label = "sysnode"

    def __str__(self):
        return self.src_file
