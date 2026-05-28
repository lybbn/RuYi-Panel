---
name: linux_vuln_check
description: Linux服务器内核漏洞检测技能，检查Copy Fail、Dirty Frag、Fragnesia等高危本地提权漏洞，评估风险并提供缓解方案
trigger_keywords: 漏洞,内核漏洞,提权,CVE,Dirty Frag,Copy Fail,Fragnesia,安全漏洞,内核安全
platforms: linux
source: builtin
---

# Linux 服务器内核漏洞检测

针对 Linux 服务器进行内核级高危漏洞检测，重点检查近期公开的本地提权（LPE）漏洞，评估系统风险并提供缓解方案。

## 适用场景

- 用户要求检查服务器是否存在已知内核漏洞
- 安全审计时需要评估内核漏洞风险
- 用户提到 CVE 编号或漏洞名称（如 Dirty Frag、Copy Fail、Fragnesia）
- 系统安全巡检中需要内核漏洞扫描环节

## 漏洞知识库

### Copy Fail (CVE-2026-31431)

| 属性 | 值 |
|------|------|
| CVE | CVE-2026-31431 |
| 名称 | Copy Fail |
| CVSS | 7.8 (High) |
| 类型 | 本地提权 (LPE) |
| 披露日期 | 2026-04-29 |
| 影响内核 | 4.14 - 6.18.21（自2017年起几乎所有发行版） |
| 漏洞模块 | `algif_aead`（内核加密子系统 AF_ALG 接口） |
| 攻击原理 | `authencesn` 模板在 AEAD 就地操作时越界写入4字节到页缓存，可修改 setuid 二进制文件内存页获取 root |
| PoC 状态 | 已公开（732字节 Python 脚本） |
| 利用条件 | 本地普通用户权限，无需竞态条件 |
| 上游补丁 | commit `a664bf3d603dc3bdcf9ae47cc21e0daec706d7a5`（2026-04-01 合入） |
| 缓解方案 | 禁用 `algif_aead` 模块 |

### Dirty Frag (QVD-2026-24699 / CVE-2026-43284 + CVE-2026-43500)

| 属性 | 值 |
|------|------|
| CVE | CVE-2026-43284 (xfrm-ESP) + CVE-2026-43500 (RxRPC) |
| 名称 | Dirty Frag |
| CVSS | 8.8 / 7.8 (High) |
| 类型 | 本地提权 (LPE) |
| 披露日期 | 2026-05-07 |
| 影响内核 | CVE-2026-43284: cac2661c53f3 (2017) 至今; CVE-2026-43500: 2dc334f1a63a (2023-06) 至今 |
| 漏洞模块 | `esp4`/`esp6`（IPsec ESP）+ `rxrpc`（AFS 远程调用） |
| 攻击原理 | 通过 splice() 零拷贝路径将页缓存页注入 sk_buff frag，内核就地解密时直接覆写共享页缓存，可修改 /etc/passwd 或 setuid 二进制文件 |
| PoC 状态 | 已公开 |
| 利用条件 | CVE-2026-43284 需用户命名空间权限; CVE-2026-43500 仅需普通用户权限 |
| 上游补丁 | CVE-2026-43284 已有补丁; CVE-2026-43500 尚未完全修补 |
| 缓解方案 | 禁用 `esp4`、`esp6`、`rxrpc` 模块 |

### Fragnesia (CVE-2026-46300)

| 属性 | 值 |
|------|------|
| CVE | CVE-2026-46300 |
| 名称 | Fragnesia |
| CVSS | 7.8 (High) |
| 类型 | 本地提权 (LPE) |
| 披露日期 | 2026-05-13 |
| 影响内核 | 与 Dirty Frag 相同范围，已打 Dirty Frag 补丁的内核同样受影响 |
| 漏洞模块 | XFRM ESP-in-TCP（`esp4`/`esp6`/`espintcp`） |
| 攻击原理 | `skb_try_coalesce()` 合并 skb 时丢失 `SKBFL_SHARED_FRAG` 标记，ESP-in-TCP 解密就地写入共享页缓存，可修改 /usr/bin/su 等获取 root |
| PoC 状态 | 已公开 |
| 利用条件 | 本地普通用户 + 用户命名空间权限（Ubuntu AppArmor 可能部分阻断） |
| 上游补丁 | 2026-05-13 提交至 netdev，待合入主线 |
| 缓解方案 | 禁用 `esp4`、`esp6`、`rxrpc` 模块（与 Dirty Frag 缓解方案相同） |

## 检测流程

### 第一步：获取内核版本信息

调用 `execute_command` 执行以下命令：

```bash
uname -r
```

记录当前内核版本，用于后续漏洞影响范围判断。

### 第二步：检查漏洞模块加载状态

调用 `execute_command` 执行以下命令：

```bash
lsmod | grep -E 'algif_aead|esp4|esp6|espintcp|rxrpc' || echo "NO_VULN_MODULES_LOADED"
```

如果输出包含模块名，说明危险模块已加载，系统暴露于攻击面。

### 第三步：检查模块是否已禁用（缓解措施是否生效）

调用 `execute_command` 执行以下命令：

```bash
cat /etc/modprobe.d/*.conf 2>/dev/null | grep -E 'install.*(algif_aead|esp4|esp6|rxrpc).*/bin/false' || echo "NO_MITIGATION_FOUND"
```

如果输出包含 `install xxx /bin/false` 配置，说明对应模块已被禁用缓解。

### 第四步：检查内核包更新状态

调用 `execute_command` 执行以下命令：

```bash
if command -v apt &>/dev/null; then apt list --upgradable 2>/dev/null | grep -i linux-image; elif command -v dnf &>/dev/null; then dnf check-update kernel 2>/dev/null; elif command -v yum &>/dev/null; then yum check-update kernel 2>/dev/null; else echo "UNKNOWN_PKG_MANAGER"; fi
```

检查是否有可用的内核安全更新。

### 第五步：检查用户命名空间限制（Ubuntu AppArmor）

调用 `execute_command` 执行以下命令：

```bash
cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "NOT_AVAILABLE"; cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo "NOT_AVAILABLE"
```

- `unprivileged_userns_clone = 0` 或 `max_user_namespaces = 0` 表示用户命名空间已限制，可部分缓解 Fragnesia 和 Dirty Frag (CVE-2026-43284) 的利用

### 第六步：生成漏洞检测报告

根据收集的信息，按照以下格式生成报告：

```markdown
# Linux 内核漏洞检测报告

## 系统信息
| 项目 | 值 |
|------|------|
| 内核版本 | x.x.x-xxx-generic |
| 操作系统 | Ubuntu 24.04 LTS / CentOS 9 / ... |
| 漏洞模块状态 | 已加载 / 未加载 / 已禁用 |
| 缓解措施 | 已生效 / 未配置 |

## 漏洞检测结果

| 漏洞 | CVE | 状态 | 风险等级 | 说明 |
|------|-----|------|----------|------|
| Copy Fail | CVE-2026-31431 | 受影响/已缓解/已修补 | 高 | ... |
| Dirty Frag | QVD-2026-24699 | 受影响/已缓解/已修补 | 高 | ... |
| Fragnesia | CVE-2026-46300 | 受影响/已缓解/已修补 | 高 | ... |

## 状态判定规则
- **已修补**：内核版本包含对应补丁 commit
- **已缓解**：漏洞模块已禁用（/etc/modprobe.d/ 中配置 install xxx /bin/false 且模块未加载）
- **受影响**：漏洞模块已加载且未应用补丁或缓解措施

## 风险详情
针对每个"受影响"的漏洞，提供：
- 漏洞原理简述
- 攻击影响（本地提权到 root）
- 利用难度评估

## 缓解建议
按优先级排序：

### 紧急缓解（无需重启，立即生效）
1. 禁用 Copy Fail 漏洞模块：
   ```bash
   echo "install algif_aead /bin/false" | sudo tee /etc/modprobe.d/copy-fail.conf
   sudo rmmod algif_aead 2>/dev/null; true
   ```

2. 禁用 Dirty Frag / Fragnesia 漏洞模块：
   ```bash
   printf 'install esp4 /bin/false\ninstall esp6 /bin/false\ninstall rxrpc /bin/false\n' | sudo tee /etc/modprobe.d/dirty-frag.conf
   sudo rmmod esp4 esp6 rxrpc 2>/dev/null; true
   ```

3. 更新 initramfs 防止开机加载：
   ```bash
   sudo update-initramfs -u -k all 2>/dev/null || sudo dracut -f 2>/dev/null; true
   ```

### 根本修复（需要重启）
1. 更新内核至已修补版本：
   ```bash
   sudo apt update && sudo apt upgrade   # Debian/Ubuntu
   sudo dnf update kernel                # RHEL/Fedora
   sudo yum update kernel                # CentOS
   ```
2. 重启系统加载新内核

### 验证缓解效果
```bash
grep -qE '^(algif_aead|esp4|esp6|rxrpc) ' /proc/modules && echo "警告：漏洞模块仍在加载" || echo "安全：漏洞模块未加载"
```

## 注意事项
- 禁用 esp4/esp6 模块会影响 IPsec VPN 功能（如 StrongSwan）
- 禁用 rxrpc 模块会影响 AFS 分布式文件系统
- 禁用 algif_aead 模块会影响内核硬件加速加密，应用会回退到用户态加密
- 缓解措施在内核更新后可移除
```

## 判定逻辑

### Copy Fail (CVE-2026-31431)
1. 内核版本 < 补丁版本 AND `algif_aead` 模块可加载 → **受影响**
2. `algif_aead` 已在 modprobe.d 中禁用且未加载 → **已缓解**
3. 内核版本 >= 补丁版本 → **已修补**

### Dirty Frag (QVD-2026-24699)
1. 内核版本 < 补丁版本 AND (`esp4`/`esp6` 或 `rxrpc` 模块可加载) → **受影响**
2. 所有三个模块已在 modprobe.d 中禁用且未加载 → **已缓解**
3. 内核版本 >= 补丁版本（注意：CVE-2026-43500 尚未完全修补）→ **部分修补**

### Fragnesia (CVE-2026-46300)
1. 内核版本 < 补丁版本 AND `esp4`/`esp6` 模块可加载 → **受影响**
2. Dirty Frag 缓解方案（禁用 esp4/esp6/rxrpc）同样适用于 Fragnesia → **已缓解**
3. 内核版本 >= 2026-05-13 补丁版本 → **已修补**

## 注意事项

- 本技能仅适用于 Linux 系统，Windows 系统不适用
- 漏洞检测只做检查和报告，不自动执行任何缓解操作
- 所有缓解操作必须经用户确认后方可执行
- 禁用内核模块可能影响现有业务功能，需提前评估
- 漏洞知识库需要持续更新，关注新披露的内核漏洞
