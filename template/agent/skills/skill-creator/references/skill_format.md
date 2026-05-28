# 如意面板技能格式规范

本文档定义如意面板技能的完整格式规范。

---

## 目录结构

```
skill-name/
├── SKILL.md          (必需 — 技能定义文件)
└── 辅助资源 (可选)
    ├── scripts/      — 可执行脚本
    ├── references/   — 参考文档
    └── agents/       — 子代理指导文档
```

---

## SKILL.md 格式

### 基本结构

```markdown
---
name: skill-name
description: 技能描述，说明功能和触发场景
---

# 技能标题

技能正文内容...
```

### Frontmatter 字段

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `name` | 是 | string | 技能标识符，kebab-case 格式（小写字母、数字、连字符），最长64字符 |
| `description` | 是 | string | 技能描述，最长1024字符，不能包含尖括号 |
| `category` | 否 | string | 技能分类（如 system、security、database） |
| `toolsets` | 否 | string | 依赖的工具集，逗号分隔 |
| `tools` | 否 | string | 依赖的具体工具，逗号分隔 |
| `preset_questions` | 否 | string | 预设问题，竖线分隔 |

### name 命名规范

- 使用 kebab-case：小写字母、数字、连字符
- 不能以连字符开头或结尾
- 不能包含连续连字符
- 也支持中文和下划线
- 最长64字符

合法示例：`system-inspection`、`ssl_management`、`日志分析`

非法示例：`System-Inspection`、`-ssl`、`ssl--management`

### description 编写规范

description 是 AI 决定是否使用技能的主要依据，需要同时包含：

1. **功能说明** — 技能做什么
2. **触发场景** — 什么情况下应该使用此技能

示例：
```
服务器系统巡检技能，提供全面的系统健康检查、性能分析、安全审计和优化建议。当用户提到系统检查、巡检、健康检查、性能诊断时使用此技能。
```

长度限制：最长1024字符。建议100-200字，既要覆盖触发场景又不能过长。

---

## 渐进式加载

如意面板的技能采用三级加载机制：

### Level 1：元数据（始终加载）

name + description，约100字，始终在 AI 上下文中。AI 根据此信息决定是否使用技能。

### Level 2：SKILL.md 正文（触发时加载）

技能触发后加载完整的 SKILL.md 正文。建议控制在500行以内。

如果内容超过500行，考虑：
- 将详细参考信息移入 references/ 目录
- 将重复操作提取为 scripts/ 中的脚本
- 在正文中用指针引导 AI 按需读取

### Level 3：辅助资源（按需加载）

通过 Skills 工具的 `detail=true` 参数加载，包括：
- scripts/ 中的脚本内容和路径
- references/ 中的参考文档
- agents/ 中的指导文档

无大小限制，AI 根据需要选择性地读取。

---

## 正文编写规范

### 结构模板

```markdown
---
name: skill-name
description: 技能描述
---

# 技能标题

简要概述技能的功能。

## 平台差异说明

- **Linux**：Linux 特有的命令和路径
- **Windows**：Windows 特有的命令和路径
- **优先使用面板工具**：已处理平台差异的工具列表

## 操作流程

### 第一步：xxx
1. 调用 `tool_name` 执行操作
2. 分析结果

### 第二步：xxx
1. ...

## 输出格式

\```markdown
# 报告标题

## 章节1
| 项目 | 值 |
|------|------|
| xxx | xxx |
\```

## 注意事项
- 注意事项1
- 注意事项2
```

### 编写原则

1. **使用祈使句** — "调用 `get_system_info` 获取系统信息" 而非 "可以调用..."
2. **解释原因** — 说明为什么某个步骤重要，而非堆砌"必须""禁止"
3. **提供模板** — 给出清晰的输出格式模板
4. **平台适配** — 明确 Linux/Windows 差异
5. **安全优先** — 危险操作必须包含确认步骤

---

## 辅助资源规范

### scripts/ 目录

存放可执行脚本，用于：
- 确定性/重复性任务（如格式验证、数据统计）
- 复杂的计算逻辑
- 需要精确控制的操作流程

脚本要求：
- 包含 shebang 行（`#!/usr/bin/env python3`）
- 有清晰的命令行参数说明
- 有错误处理和退出码
- 不依赖非标准库（或明确声明依赖）

### references/ 目录

存放参考文档，用于：
- 详细的配置说明
- JSON Schema 定义
- 最佳实践指南
- 外部文档摘录

文档要求：
- 使用 Markdown 格式
- 包含目录（超过300行时）
- 在 SKILL.md 中明确引用时机

### agents/ 目录

存放子代理指导文档，用于：
- 评估指导（grader）
- 分析指导（analyzer）
- 比较指导（comparator）

---

## 技能存放路径

| 类型 | 路径 | 说明 |
|------|------|------|
| 内置技能 | `template/agent/skills/<name>/` | 随版本发布，只读 |
| 用户技能 | `data/agent/skills/<name>/` | 运行时创建，可读写 |
| 进化技能 | `data/agent/evolved_skills/<name>/` | 自动沉淀生成 |

加载优先级：data/ 目录优先于 template/ 目录（同名技能以 data/ 为准）。

---

## 技能状态管理

技能启用/禁用状态存储在 `data/agent/skills_state.json`：

```json
{
  "disabled_skills": ["skill-name-1", "skill-name-2"]
}
```

不在 `disabled_skills` 列表中的技能默认启用。

---

## 打包格式

技能打包为 .zip 文件，结构如下：

```
skill-name.zip
└── skill-name/
    ├── SKILL.md
    ├── scripts/
    │   └── ...
    ├── references/
    │   └── ...
    └── agents/
        └── ...
```

打包时排除：
- `__pycache__/`、`node_modules/`
- `*.pyc`、`.DS_Store`
- `evals/` 目录（评估数据不随技能分发）
