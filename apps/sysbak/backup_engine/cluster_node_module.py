import os
import json
from utils.common import ReadFile, WriteFile
from apps.sysbak.backup_engine.base import BaseBackupModule


class ClusterNodeBackupModule(BaseBackupModule):
    """多机管理节点备份模块 - 集群节点列表"""

    def get_data_list(self):
        from apps.sysnode.models import ClusterNode
        result = []
        for cn in ClusterNode.objects.all().order_by('-id'):
            result.append({
                'id': cn.id,
                'name': cn.name,
                'type': cn.get_node_type_display(),
                'host': cn.server_ip or cn.address,
            })
        return result

    def backup(self, item_ids=None):
        from apps.sysnode.models import ClusterNode

        config_dir = os.path.join(self.backup_dir, 'cluster_nodes')
        os.makedirs(config_dir, exist_ok=True)
        results = {}

        try:
            self.report_progress('cluster_nodes', 'all', 1, '正在备份多机管理节点列表')
            self.log('开始备份多机管理节点列表')
            nodes = ClusterNode.objects.filter(id__in=item_ids) if item_ids else ClusterNode.objects.all()
            node_data = []
            for cn in nodes:
                node_data.append({
                    'name': cn.name,
                    'address': cn.address,
                    'server_ip': cn.server_ip,
                    'node_type': cn.node_type,
                    'api_key': cn.api_key,
                    'ssh_conf': cn.ssh_conf,
                    'category_id': cn.category_id,
                    'remarks': cn.remarks,
                    'is_local': cn.is_local,
                })
            WriteFile(os.path.join(config_dir, 'cluster_nodes.json'), json.dumps(node_data, ensure_ascii=False))
            self.report_progress('cluster_nodes', 'all', 2, '多机管理节点列表备份完成')
            self.log('多机管理节点列表备份完成')
            results['cluster_nodes'] = {'status': 2, 'error_msg': ''}
        except Exception as e:
            self.report_progress('cluster_nodes', 'all', 3, f'多机管理节点列表备份失败: {str(e)}')
            self.log(f'多机管理节点列表备份失败: {str(e)}')
            results['cluster_nodes'] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        config_dir = os.path.join(backup_dir, 'cluster_nodes')
        if not os.path.exists(config_dir):
            self.log('未找到多机管理节点备份文件')
            return

        node_file = os.path.join(config_dir, 'cluster_nodes.json')
        if not os.path.exists(node_file):
            self.log('未找到多机管理节点备份文件')
            return

        try:
            from apps.sysnode.models import ClusterNode
            node_data = json.loads(ReadFile(node_file))
            for nd in node_data:
                existing = ClusterNode.objects.filter(
                    address=nd['address'], node_type=nd['node_type']
                ).first()
                if existing:
                    if conflict_strategy == 'skip':
                        self.log(f'跳过已存在的节点: {nd["name"]}')
                        continue
                    elif conflict_strategy == 'overwrite':
                        existing.name = nd['name']
                        existing.server_ip = nd.get('server_ip', '')
                        existing.api_key = nd.get('api_key', '')
                        existing.ssh_conf = nd.get('ssh_conf', '{}')
                        existing.remarks = nd.get('remarks', '')
                        existing.save()
                        continue
                    elif conflict_strategy == 'rename':
                        nd['name'] = f"{nd['name']}_restored"
                ClusterNode.objects.create(
                    name=nd['name'],
                    address=nd.get('address', ''),
                    server_ip=nd.get('server_ip', ''),
                    node_type=nd.get('node_type', 'api'),
                    api_key=nd.get('api_key', ''),
                    ssh_conf=nd.get('ssh_conf', '{}'),
                    category_id=nd.get('category_id'),
                    remarks=nd.get('remarks', ''),
                    is_local=nd.get('is_local', False),
                )
            self.log('多机管理节点列表还原完成')
        except Exception as e:
            self.log(f'还原多机管理节点失败: {str(e)}')

        self.report_progress('cluster_nodes', 'all', 2, '多机管理节点列表还原完成')
