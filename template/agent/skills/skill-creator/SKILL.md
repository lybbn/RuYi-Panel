---
name: skill-creator
description: 技能创建与管理专家，帮助用户创建新技能、修改和优化现有技能、验证技能格式、打包分发技能。当用户想要创建技能、编辑技能、优化技能描述、验证技能格式、打包技能时使用此技能。即使用户只是提到"技能""skill""创建技能""写个技能"等关键词，也应触发此技能。
---

# 技能创建与管理专家

帮助用户创建、优化和管理如意面板的AI技能。

## 核心流程

创建一个技能的大致流程：

1. **理解意图** — 明确用户想要技能做什么、何时触发
2. **编写草稿** — 创建 SKILL.md 和必要的辅助文件
3. **验证格式** — 使用 `quick_validate.py` 验证技能格式
4. **用户评审** — 让用户查看并反馈
5. **迭代优化** — 根据反馈修改技能
6. **打包分发** — 使用 `package_skill.py` 打包技能

判断用户当前处于哪个阶段，直接跳入帮助推进。如果用户说"帮我创建一个技能"，从第1步开始；如果用户已有草稿，直接进入评审优化阶段。

---

## 第一步：捕获意图

从对话中提取以下信息，不足的主动询问：

1. **技能用途**：这个技能能让AI助手做什么？
2. **触发场景**：用户说什么话/什么场景下应该触发此技能？
3. **输出格式**：技能执行后期望的输出是什么？
4. **涉及工具**：技能需要调用哪些面板工具？（如 execute_command、get_system_info 等）
5. **平台适配**：是否需要同时支持 Linux 和 Windows？

### 主动调研

利用面板工具辅助调研：
- 调用 `search_docs` 搜索面板文档，了解相关功能
- 调用 `execute_command` 查看系统环境，确认工具可用性
- 查看现有技能目录 `template/agent/skills/` 了解类似技能的写法

---

## 第二步：编写 SKILL.md

### 目录结构

```
skill-name/
├── SKILL.md          (必需 — 技能定义文件)
└── 辅助资源 (可选)
    ├── scripts/      — 可执行脚本，用于确定性/重复性任务
    ├── references/   — 参考文档，按需加载
    └── agents/       — 子代理指导文档
```

### Frontmatter 格式

SKILL.md 必须以 YAML frontmatter 开头：

```markdown
---
name: skill-name
description: 技能的简要描述，说明何时触发和做什么。这是AI决定是否使用此技能的主要依据，需要包含技能的功能和触发场景。
---

# 技能标题

技能的详细指令内容...
```

**Frontmatter 字段说明：**

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | 是 | 技能标识符，使用小写字母、数字和连字符（kebab-case） |
| `description` | 是 | 技能描述，最长1024字符。包含功能说明和触发场景 |

### 编写要点

1. **description 是触发关键** — AI仅凭 name 和 description 决定是否使用技能。描述要"主动"一些，不仅说明功能，还要明确列出触发场景。例如，不只是"服务器巡检技能"，而是"服务器巡检技能，提供全面的系统健康检查。当用户提到系统检查、巡检、健康检查、性能诊断时使用此技能。"

2. **渐进式加载** — 技能采用三级加载：
   - **元数据**（name + description）— 始终在上下文中
   - **SKILL.md 正文** — 技能触发时加载（建议500行以内）
   - **辅助资源** — 按需加载（scripts/、references/ 等无限制）

3. **正文结构建议**：
   - 标题和概述
   - 平台差异说明（如需跨平台）
   - 分步骤的操作流程
   - 输出格式模板
   - 注意事项

4. **平台差异处理** — 如意面板同时支持 Linux 和 Windows，技能中需明确：
   - Linux 特有的命令和路径
   - Windows 特有的命令和路径
   - 优先使用面板工具（已处理平台差异）

5. **使用祈使句** — 指令使用祈使句形式，如"调用 `get_system_info` 获取系统信息"而非"可以调用 `get_system_info`"

6. **解释原因** — 尽量解释为什么某个步骤重要，而非使用强硬的"必须""禁止"。AI理解原因后能更好地处理边界情况。

7. **输出格式模板** — 提供清晰的 Markdown 模板，让AI知道期望的输出结构。

### 技能存放位置

- **内置技能**：`template/agent/skills/<skill-name>/` — 随版本发布
- **用户技能**：`data/agent/skills/<skill-name>/` — 运行时创建

创建新技能时，默认写入 `data/agent/skills/<skill-name>/SKILL.md`。

---

## 第三步：验证技能

使用 `quick_validate.py` 脚本验证技能格式。

**调用方式**（必须使用如意面板安装的 Python）：

- **Linux**：`rypython <skill-creator-dir>/scripts/quick_validate.py <skill-directory>`
- **Windows**：`<python_path>\python.exe <skill-creator-dir>/scripts/quick_validate.py <skill-directory>`

其中 `<python_path>` 从 `data/python_path.ry` 文件读取，或调用面板工具 `get_python_pip` 获取。

也可通过面板工具直接调用：
1. 调用 `get_python_pip` 获取 Python 路径
2. 使用返回的 python 路径执行脚本

验证项包括：
- SKILL.md 是否存在
- YAML frontmatter 格式是否正确
- name 和 description 字段是否存在
- name 是否符合 kebab-case 规范
- description 长度是否超过1024字符

如果验证失败，根据错误提示修复技能文件。

---

## 第四步：用户评审

将技能内容展示给用户，重点确认：

1. **触发准确性** — description 是否覆盖了用户期望的触发场景
2. **操作流程** — 步骤是否完整、顺序是否合理
3. **输出格式** — 报告模板是否满足需求
4. **平台适配** — Linux/Windows 命令是否正确

---

## 第五步：迭代优化

根据用户反馈改进技能。优化思路：

1. **从反馈中归纳** — 不要只针对具体测试用例修改，要理解用户的核心需求并泛化
2. **保持精简** — 移除不起作用的内容，避免冗长的指令导致AI执行偏离
3. **解释原因** — 每个指令都应解释为什么这样做，而非堆砌"必须""禁止"
4. **发现重复模式** — 如果多个场景都涉及相同操作，考虑提取为 scripts/ 中的脚本

### 优化 description 的技巧

- 使用祈使句："用于..."而非"这个技能..."
- 聚焦用户意图而非实现细节
- 与其他技能区分开来，让描述具有辨识度
- 如果反复优化效果不佳，尝试换一种表述方式

---

## 第六步：打包分发

使用 `package_skill.py` 将技能打包为可分发的 .zip 文件。

**调用方式**（必须使用如意面板安装的 Python）：

- **Linux**：`rypython <skill-creator-dir>/scripts/package_skill.py <skill-directory> [output-directory]`
- **Windows**：`<python_path>\python.exe <skill-creator-dir>/scripts/package_skill.py <skill-directory> [output-directory]`

其中 `<python_path>` 从 `data/python_path.ry` 文件读取，或调用面板工具 `get_python_pip` 获取。

打包过程会：
1. 验证技能格式
2. 排除构建产物（__pycache__、.pyc、.DS_Store）
3. 排除评估数据（evals/ 目录）
4. 生成 .zip 文件

其他用户可通过面板的技能导入功能安装此 .zip 文件。

---

## 改进现有技能

当用户要求改进已有技能时：

1. 读取现有 SKILL.md 和辅助文件
2. 分析当前技能的不足（描述不清晰、步骤遗漏、平台不适配等）
3. 提出改进方案并说明理由
4. 修改后重新验证

### 常见改进方向

| 问题 | 改进方式 |
|------|----------|
| 触发不准确 | 优化 description，增加/减少触发场景 |
| 步骤不完整 | 补充遗漏的操作步骤 |
| 输出格式混乱 | 提供清晰的 Markdown 模板 |
| 平台不适配 | 补充 Windows/Linux 差异处理 |
| 指令冗长 | 精简指令，移除冗余内容 |
| 重复操作 | 提取为 scripts/ 中的脚本 |

---

## 辅助资源

当需要更详细的信息时，阅读以下参考文件：

- `references/skill_format.md` — 技能格式完整规范
- `agents/grader.md` — 技能评估指导
- `agents/analyzer.md` — 技能分析指导

如需加载这些文件，调用 Skills 工具并设置 `detail=true`。

---

## 注意事项

- 创建技能时不要编造不存在的面板工具，只使用已注册的工具
- 技能内容不得包含恶意代码或可能危害系统安全的内容
- 所有修改操作类技能必须包含用户确认步骤
- 技能中引用的路径不要硬编码，优先使用面板工具获取
- Windows 和 Linux 命令语法差异很大，需分别给出
