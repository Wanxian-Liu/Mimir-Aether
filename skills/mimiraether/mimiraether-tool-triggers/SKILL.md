---
auto_load: false
description: MimirAether Tool Triggers — 工具触发规则
---


# MimirAether Tool Triggers — 工具触发规则

## 问题诊断

工具能力在任务解析阶段没有充分展开——知识是惰性的。我知道工具存在，但不知道该什么时候调用。

## 核心原则

**在任务解析阶段，必须先过一遍工具清单，逐一问："这个任务是否触发了此工具的必用条件？"**

---

## 工具触发规则

### web_search

**必用场景（只要命中一条就必须用）：**

1. **知识边界之外**：被问到的API、库、框架、协议、工具不在训练数据中，或者不确定最新的版本/语法/配置
2. **实时信息**：问的是"最近""当前""最新"的事情，或涉及可能已变化的状态（价格、政策、事件）
3. **验证假设**：你在推理中做了某个假设但不确定是否正确
4. **首次接触**：用户提到一个你从未见过的工具名、项目名、术语——先搜再答
5. **代码集成前**：要写调用外部API/服务的代码时，先搜该API的文档/最新用法
6. **错误排查**：遇到一个无法从第一性原理推导的错误信息，先搜

**降级策略（web_search不可用时）：**
- 优先检查是否有对应skill（skill_view）
- **execute_code + curl 调用结构化API**（首选，可解析JSON）：
  - GitHub API: `curl -s https://api.github.com/search/repositories?q=关键词`
  - 用 Python 的 `subprocess` + `json.loads` 解析响应，过滤关键字段
  - 注意：GitHub 未认证限速 60次/小时，仅用于关键查询
- **terminal + curl 调用搜索API**（次选，仅当 execute_code 也不可用）：
  - DuckDuckGo: `curl -s "https://api.duckduckgo.com/?q=关键词&format=json"`
- 承认知识边界，明确告知用户"我对此不确定，且搜索暂不可用"
- 绝不降级为"凭记忆猜测"

**反模式（禁止行为）：**
- 凭记忆猜测API端点、参数格式、配置字段
- 对不熟悉的工具直接假设它的用法
- 遇到未知术语不求证直接跳过
- web_search失败后直接放弃搜索，转而猜测

**触发自检问题：** "我对这个问题的答案有100%把握吗？如果没有，先搜。"

---

### skill_view

**必用场景：**

1. **任务领域匹配**：任务涉及的关键词与某个skill名称/描述有部分重叠（如"PR"→github-pr-workflow，"PDF"→ocr-and-documents，"视频"→youtube-content）
2. **复杂任务（预计3+步骤）**：动手前先扫描skills_list，加载可能相关的技能
3. **文件格式操作**：涉及.pptx/.pdf/.docx等格式时，一定有对应的skill
4. **上次做过但记不清**：如果某个操作之前做过但现在不记得具体步骤，说明可能已有skill
5. **用户说"帮我管理X"**：X通常对应一个skill类别（github/email/media/productivity）

**反模式：**
- 看到任务后直接动手，不检查是否有skill
- 只用web_search查方法，不先看有没有skill封装了最佳实践
- 知道有skill但觉得"手动也能做"就不加载

**触发自检问题：** "这个任务有没有现成的skill？即使只部分相关也先加载。"

---

### execute_code

**必用场景：**

1. **代码正确性验证**：写完一段代码后，在给用户之前先执行测试
2. **假设验证**：对系统行为有假设（"这个命令应该返回X"），执行验证
3. **数据处理**：需要计算、转换、分析数据时
4. **快速原型**：不确定某个方案是否可行，先写最小代码验证
5. **读取非文本文件**：二进制文件、特殊格式
6. **安装/检查依赖**：需要确认某个包是否存在、版本是否正确

**反模式：**
- 写了一段代码直接给用户，从未执行过
- 用"理论上应该能跑"替代实际测试
- 对行为不确定时不写小测试验证

**触发自检问题：** "我写的这段代码，我确定它能跑吗？不确定就执行测试。"

---

### terminal

**适用场景（区别于execute_code）：**

1. **系统级操作**：git、包管理、进程管理、网络检查
2. **构建和测试**：make、npm/pip install、test suite
3. **文件系统操作**：移动/复制/删除/权限
4. **服务管理**：启动/停止守护进程
5. **长时间任务**：用background=true跑大任务

**注意：不要用terminal读文件（用read_file）或搜索（用search_files）。**

**反模式：**
- 用terminal的cat/grep替代read_file/search_files
- 用echo/cat heredoc创建文件替代write_file

**触发自检问题：** "这个操作是shell命令还是文件操作？shell→terminal，文件→专用工具。"

---

### skill_manage

**必用场景：**

1. **复杂任务完成（5+次工具调用）后**：主动询问是否保存为skill
2. **修复了棘手的错误**：学到了教训，固化下来
3. **加载的skill有问题**：缺少步骤、命令不对、有坑——立即patch
4. **发现非平凡工作流**：走了几个工具组合才解决的问题，封装成skill
5. **用户明确要求**：创建/更新/删除skill

**反模式：**
- 经历辛苦调试后忘记固化经验
- 发现skill有错但只是临时绕过，不patch

**触发自检问题：** "刚才那个任务，下次还会遇到吗？会→存为skill。"

**完整固化流程（路径、命名、frontmatter、create/patch 步骤、质量清单）：** `skill_view('mimiraether-skill-solidify')`

---

### read_file

**必用场景：**

1. **编辑前必读**：修改任何文件前先读取当前内容
2. **分析代码**：理解逻辑、找bug、评估结构
3. **检查配置**：查看环境配置、项目设置
4. **引用上下文中提到的文件**：用户说"看看那个文件"

**反模式：**
- 不读文件直接编辑（基于记忆或假设）
- 用terminal的cat读取文件

---

### write_file

**必用场景：**

1. **创建新文件**
2. **完整覆盖现有文件**
3. **用户要求保存输出**

**注意：小范围修改用patch，不要整文件重写。**

---

### get_env

**必用场景：**

1. **需要确认环境变量是否存在**（白名单限制）
2. **配置检查**：API密钥、路径等

---

### Capsule系列（produce_capsule, list_capsules, get_capsule_by_id, improve_capsule）

**必用场景：**

1. **produce_capsule**：完成复杂任务后，产生了有价值的知识/经验/解决方案→生成胶囊
2. **list_capsules**：需要查看已有知识积累时
3. **get_capsule_by_id**：需要检索特定胶囊内容时
4. **improve_capsule**：发现已有胶囊可以改进时

**反模式：**
- 完成了有价值的分析但不生成胶囊（知识流失）

---

## 决策链（工具组合模式）

### 模式1：未知→搜索→skill
```
遇到未知工具/概念 → web_search → 发现对应工具/skill → skill_view加载
```

### 模式2：编码→验证→固化为skill
```
写代码 → execute_code测试 → 通过 → skill_manage保存模式
```

### 模式3：文件编辑前确保当前状态
```
read_file读取 → 分析 → 小改patch / 大改write_file
```

### 模式4：任务解析时扫描技能
```
收到任务 → skills_list扫描 → skill_view加载匹配的技能 → 按技能指引执行
```

### 模式5：搜索降级链
```
web_search失败 → skill_view查相关领域skill → execute_code + curl调结构化API → terminal + curl调搜索API → 承认边界
```

**execute_code + curl 代码模板：**
```python
import subprocess, json

def github_search(query, endpoint="repositories"):
    """GitHub API 搜索（未认证，限速60次/小时）"""
    url = f"https://api.github.com/search/{endpoint}?q={query}"
    result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=15)
    data = json.loads(result.stdout)
    if endpoint == "repositories":
        return [(r["full_name"], r["stargazers_count"], r["description"], r["html_url"]) 
                for r in data.get("items", [])[:5]]
    return data
```

---

## 任务解析自检清单（每次收到任务时执行）

**元规则（优先于所有其他规则）：**

0. □ 收到任务后，在分析任何内容之前，先加载本技能（mimiraether-tool-triggers）→ skill_view("mimiraether-tool-triggers")
   - 本技能是所有工具调用的总纲，必须先加载
   - 加载后，逐条执行下面的清单
   - 这是打破"技能沉默"的第一把钥匙
   - **跨会话验证**：如果 memory-context 中有 `persistent.json` 或 `data/persistent.json` 的引用，立即读取它们恢复上次会话状态
   - **会话恢复路径**：先读 data/persistent.json 获取 pending_tasks，再读 memory/persistent.json 获取历史决策
   - **plan-mode联动**：完成上述检查后，评估任务复杂度。如果预计需要3+步工具调用：
     a. 自动加载 mimiraether-plan-mode：skill_view("mimiraether-plan-mode")
     b. 按 plan-mode 的 5 阶段流程（Context Analysis → Task Breakdown → Dependency Mapping → Risk Identification → Plan Document）输出计划
     c. 等待用户批准后再执行
     d. **注意**：如果用户明确要求"直接做"或"不需要计划"，跳过此联动

0.5. □ 复杂度评估：当前任务预计需要几步工具调用？
   - 1-2步 → 直接执行（跳过plan-mode）
   - 3+步 → 进入plan-mode（加载 mimiraether-plan-mode 并按流程输出计划）
   - 不确定 → 按3+步处理（宁可多计划，不可少规划）

1. □ 这个任务涉及我不确定的知识吗？→ web_search
2. □ 有相关的skill吗？→ skills_list → skill_view
3. □ 需要写代码吗？写完后→ execute_code测试
4. □ 需要读/写文件吗？→ read_file / write_file（不要用terminal替代）
5. □ 任务复杂度≥5步吗？完成后→ 考虑skill_manage固化
6. □ 产生了有价值的经验吗？→ produce_capsule
7. □ 复杂任务（5+工具调用）完成后→ 用 produce_capsule 固化关键经验/解决方案/知识
   - 这是"经验不流失"的最后一环：工具调用链完成了，但知识还没沉淀
   - 固化时机：任务结果交给用户后，立即调用 produce_capsule
   - 输入内容：刚刚解决的问题、关键决策、代码模式、踩过的坑
   - capsule_type 选择：auto（一般经验）/ optimize（优化方案）/ repair（修复记录）/ innovate（新模式）
   - 反模式：任务做完就结束，不固化经验
