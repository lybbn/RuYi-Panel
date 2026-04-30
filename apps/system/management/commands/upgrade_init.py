#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-21
# +-------------------------------------------------------------------

# ------------------------------
# 项目升级初始化
# ------------------------------
import os
import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-09-21
    @EditData:2024-09-21
    @Email:1042594286@qq.com
    @name:项目升级初始化命令: python manage.py upgrade_init
    @使用场景：面板升级后执行，检测并补充缺失的初始数据
    @特点：可重复执行，不会破坏已有数据
    """

    def handle(self, *args, **options):
        print("=" * 50)
        print("开始执行升级数据初始化...")
        print("=" * 50)
        
        # 1. 初始化计划任务（如果不存在）
        self.init_crontab_tasks()
        
        # 2. 初始化告警通知渠道配置（如果不存在）
        self.init_alert_notify_config()
        
        # 3. 初始化WAF数据配置（如果不存在）
        self.init_waf_data_config()
        
        print("=" * 50)
        print("升级数据初始化完成！")
        print("=" * 50)
    
    def init_crontab_tasks(self):
        """
        初始化计划任务
        特点：可重复执行，只创建不存在的数据，不删除或修改已有数据
        """
        print("\n 正在检查计划任务...")
        try:
            from apps.systask.init_data import init_crontab_tasks
            
            created_count, skipped_count = init_crontab_tasks(force=False)
            
            print(f"\n计划任务检查完成: 新建 {created_count} 个, 跳过 {skipped_count} 个")
            
        except Exception as e:
            print(f"初始化计划任务出错: {e}")
            logger.error(f"升级初始化计划任务失败: {e}")
    
    def init_alert_notify_config(self):
        """
        初始化告警通知渠道配置
        特点：可重复执行，只创建不存在的数据，不删除或修改已有数据
        """
        print("\n 正在检查告警通知渠道配置...")
        try:
            from apps.sysalert.init_data import init_alert_notify_config
            
            created_count, skipped_count = init_alert_notify_config(force=False)
            
            print(f"\n告警通知渠道配置检查完成: 新建 {created_count} 个, 跳过 {skipped_count} 个")
            
        except Exception as e:
            print(f"初始化告警通知渠道配置出错: {e}")
            logger.error(f"升级初始化告警通知渠道失败: {e}")
        
    def init_waf_data_config(self):
        """
        初始化WAF数据
        特点：可重复执行，只创建不存在的数据，不删除或修改已有数据
        """
        print("\n 正在检查WAF数据...")
        try:
            from apps.syswaf.init_data import init_waf_data
            categories, rules, config, ip_group, from_remote = init_waf_data(force=True)
            print(f"初始化完成【WAF数据】: 分类{categories}个, 规则{rules}条, 配置{config}, IP组{ip_group}")
            
        except Exception as e:
            print(f"初始化WAF数据出错: {e}")
            logger.error(f"升级初始化WAF数据失败: {e}")
        
        # 迁移现有站点配置，添加 extension include 语句
        self.migrate_sites_extension_include()
    
    def migrate_sites_extension_include(self):
        """
        迁移现有站点配置，添加扩展配置目录 include 语句
        特点：可重复执行，只处理没有 extension include 的老配置
        """
        print("\n 正在检查站点扩展配置迁移...")
        try:
            from utils.ruyiclass.nginxClass import NginxClient
            
            migrated_count, skipped_count, failed_count = NginxClient.migrate_all_sites_extension_include()
            
            print(f"\n站点扩展配置迁移完成: 迁移 {migrated_count} 个, 跳过 {skipped_count} 个, 失败 {failed_count} 个")
            
        except Exception as e:
            print(f"站点扩展配置迁移出错: {e}")
            logger.error(f"升级站点扩展配置迁移失败: {e}")
