# Hermes 技能全量清单

> 对照 MimirAether 现有 77 技能，标注导入状态  
> **生成日期**：2026-05-11 | **数据源**：`hermes-agent` 源码 + `~/.hermes/skills` + `~/.hermes/optional-skills`

## 图例

| 标记 | 含义 |
|------|------|
| ✅ | 已导入 MimirAether |
| 📥 | 缺失，值得研究 |
| ❌ | 跳过（已删除/不需要/不适用） |
| 🔀 | 有对应但实现不同 |

---

## 1. apple/（4个）

| 技能 | 状态 | 备注 |
|------|------|------|
| apple-notes | ❌ | Apple 生态绑定 |
| apple-reminders | ❌ | Apple 生态绑定 |
| findmy | ❌ | Apple 生态绑定 |
| imessage | ❌ | Apple 生态绑定 |

---

## 2. autonomous-ai-agents/（4个）

| 技能 | 状态 | 备注 |
|------|------|------|
| claude-code | ❌ | 已删除 |
| codex | ❌ | 已删除 |
| hermes-agent | ❌ | 已删除 |
| opencode | ❌ | 已删除 |

---

## 3. creative/（19个）

| 技能 | 状态 | 一句话 | 研究优先级 |
|------|------|--------|------------|
| architecture-diagram | ✅ | 深色SVG架构图（AWS/GCP/K8s）— 已导入 2026-05-11 | ⭐⭐⭐ |
| ascii-art | ✅ | pyfiglet/cowsay/boxes ASCII艺术 — 已导入 2026-05-11 | ⭐ |
| ascii-video | 📥 | 视频转彩色ASCII动画MP4 | ⭐ |
| baoyu-comic | ✅ | 知识漫画（教育/传记/教程）— 已导入 2026-05-11 | ⭐⭐ |
| baoyu-infographic | ✅ | 信息图：21布局×21风格（宝玉）— 已导入 2026-05-11 | ⭐⭐ |
| claude-design | ✅ | 一次性HTML制品（landing/deck）— 已导入 2026-05-11 | ⭐⭐ |
| comfyui | ❌ | AI图像/视频/音频生成工作流 — 跳过（重依赖：本地ComfyUI安装） | ⭐⭐⭐ |
| creative-ideation | ✅ | 约束驱动创意构思 — 已导入 2026-05-11 | ⭐ |
| design-md | ✅ | Google DESIGN.md token规范 — 已导入 2026-05-11 | ⭐ |
| excalidraw | ✅ | 手绘风格JSON图表（架构/流程/时序）— 已导入 2026-05-11 | ⭐⭐⭐ |
| humanizer | ✅ | AI文本去味，注入真人声音 — 已导入 2026-05-11 | ⭐⭐⭐ |
| manim-video | ❌ | 3Blue1Brown风格数学动画 — 跳过（重依赖：LaTeX~2GB） | ⭐⭐⭐ |
| p5js | ✅ | 生成艺术/着色器/交互3D — 已导入 2026-05-11 | ⭐⭐ |
| pixel-art | ✅ | 像素艺术（NES/GameBoy/PICO-8调色板）— 已导入 2026-05-11 | ⭐ |
| popular-web-designs | ✅ | 54个真实设计系统（Stripe/Linear/Vercel）HTML/CSS — 已导入 2026-05-11 | ⭐⭐ |
| pretext | ✅ | @chenglou/pretext 文字即几何demo — 已导入 2026-05-11 | ⭐ |
| sketch | ✅ | 一次性HTML原型（2-3设计变体对比）— 已导入 2026-05-11 | ⭐⭐ |
| songwriting-and-ai-music | ✅ | 歌词创作+Suno AI音乐提示词 — 已导入 2026-05-11 | ⭐⭐ |
| touchdesigner-mcp | 📥 | 控制TouchDesigner via MCP | ⭐ |

---

## 4. data-science/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| jupyter-live-kernel | 📥 | Jupyter实时内核交互 | ⭐⭐ |

---

## 5. devops/（3个）

| 技能 | 状态 | 备注 |
|------|------|------|
| kanban-orchestrator | 📥 | 看板编排器 | ⭐⭐ |
| kanban-worker | 📥 | 看板执行器 | ⭐⭐ |
| webhook-subscriptions | 📥 | Webhook订阅管理 | ⭐⭐ |

---

## 6. diagramming/（空类别）

> 只有 DESCRIPTION.md，无子技能。

---

## 7. dogfood/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| dogfood | 📥 | Hermes团队内部自用技能（含模板/参考） | ⭐ |

---

## 8. email/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| himalaya | 📥 | 终端邮件客户端（CLI收发邮件） | ⭐ |

---

## 9. gaming/（2个）

| 技能 | 状态 | 备注 |
|------|------|------|
| minecraft-modpack-server | ✅ | 已导入 |
| pokemon-player | ✅ | 已导入 |

---

## 10. github/（6个）

| 技能 | 状态 | 备注 |
|------|------|------|
| codebase-inspection | ✅ | 已导入 |
| github-auth | ✅ | 已导入 |
| github-code-review | ✅ | 已导入 |
| github-issues | ✅ | 已导入 |
| github-pr-workflow | ✅ | 已导入 |
| github-repo-management | ✅ | 已导入 |

---

## 11. mcp/（2-3个）

| 技能 | 状态 | 来源 | 备注 |
|------|------|------|------|
| native-mcp | ✅ | 源码 | 已导入 |
| mcporter | ✅ | ~/.hermes | 已导入 |
| fastmcp | ❌ | optional | 可选，暂不导入 |

---

## 12. media/（5个）

| 技能 | 状态 | 备注 |
|------|------|------|
| gif-search | ✅ | 已导入 |
| heartmula | ✅ | 已导入 |
| songsee | ✅ | 已导入 |
| spotify | ✅ | 已导入 |
| youtube-content | ✅ | 已导入 |

---

## 13. mlops/（约30个，含子类别）

### 13a. 已导入（源码+~/.hermes合并）

| 技能 | 子类 | 状态 |
|------|------|------|
| huggingface-hub | / | ✅ |
| lm-evaluation-harness | evaluation | ✅ |
| weights-and-biases | evaluation | ✅ |
| llama-cpp | inference | ✅ |
| obliteratus | inference | ✅ |
| outlines | inference | ✅ |
| vllm | inference | ✅ |
| gguf | inference | ✅（~/.hermes） |
| guidance | inference | ✅（~/.hermes） |
| audiocraft | models | ✅ |
| segment-anything | models | ✅ |
| clip | models | ✅（~/.hermes） |
| stable-diffusion | models | ✅（~/.hermes） |
| whisper | models | ✅（~/.hermes） |
| dspy | research | ✅ |
| axolotl | training | ✅ |
| trl-fine-tuning | training | ✅ |
| unsloth | training | ✅ |
| modal | cloud | ✅（~/.hermes） |
| grpo-rl-training | training | ✅（~/.hermes） |
| peft | training | ✅（~/.hermes） |
| pytorch-fsdp | training | ✅（~/.hermes） |

### 13b. 缺失（optional-skills）

| 技能 | 子类 | 状态 | 备注 |
|------|------|------|------|
| accelerate | / | ❌ | HF Accelerate，低频 |
| chroma | / | ❌ | 向量数据库，低频 |
| faiss | / | ❌ | 向量数据库，低频 |
| flash-attention | / | ❌ | 高效注意力，低频 |
| hermes-atropos-environments | / | ❌ | Hermes特定环境 |
| huggingface-tokenizers | / | ❌ | Tokenizer库，低频 |
| instructor | / | ❌ | 结构化输出，低频 |
| lambda-labs | / | ❌ | GPU云，低频 |
| llava | / | ❌ | 多模态模型，低频 |
| nemo-curator | / | ❌ | 数据策展，低频 |
| pinecone | / | ❌ | 向量数据库，低频 |
| pytorch-lightning | / | ❌ | 训练框架，低频 |
| qdrant | / | ❌ | 向量数据库，低频 |
| saelens | / | ❌ | SAE分析，低频 |
| simpo | / | ❌ | 对齐方法，低频 |
| slime | / | ❌ | 训练优化，低频 |
| tensorrt-llm | / | ❌ | NVIDIA推理，低频 |
| torchtitan | / | ❌ | 大规模训练，低频 |

---

## 14. note-taking/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| obsidian | ✅ | 已导入 |

---

## 15. productivity/（额外有optional-skills）

### 15a. 已导入

| 技能 | 状态 |
|------|------|
| google-workspace | ✅ |
| linear | ✅ |
| nano-pdf | ✅ |
| notion | ✅ |
| ocr-and-documents | ✅ |
| powerpoint | ✅ |

### 15b. MimirAether 独有（非Hermes来源）

| 技能 | 备注 |
|------|------|
| session-tracker | 自研 |
| snippets | 自研 |
| skills-qa | 自研 |
| insights | 自研 |
| delegate-subagent | 自研 |

### 15c. 缺失（Hermes有但我们没有）

| 技能 | 状态 | 备注 |
|------|------|------|
| airtable | 📥 | 低代码数据库 | ⭐⭐ |
| maps | 📥 | 地图服务 | ⭐⭐ |
| canvas | ❌ | optional，画布 | ⭐ |
| memento-flashcards | ❌ | optional，记忆卡片 | ⭐ |
| siyuan | ❌ | optional，思源笔记 | ⭐ |
| telephony | ❌ | optional，电话服务 | ⭐ |

---

## 16. red-teaming/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| godmode | ✅ | 已导入 |

---

## 17. research/（5+7 optional）

### 17a. 已导入

| 技能 | 状态 |
|------|------|
| arxiv | ✅ |
| blogwatcher | ✅ |
| llm-wiki | ✅ |
| polymarket | ✅ |
| research-paper-writing | ✅ |

### 17b. 缺失（optional）

| 技能 | 状态 | 备注 |
|------|------|------|
| bioinformatics | ❌ | 生信，领域限定 |
| domain-intel | ❌ | 领域情报 |
| drug-discovery | ❌ | 药物发现 |
| duckduckgo-search | ❌ | DDG搜索，已有web_search |
| gitnexus-explorer | ❌ | Git探索 |
| parallel-cli | ❌ | 并行CLI |
| qmd | ❌ | QMD工具 |
| scrapling | ❌ | 爬虫 |

---

## 18. smart-home/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| openhue | ✅ | 已导入 |

---

## 19. social-media/（1-2个）

| 技能 | 状态 | 来源 | 备注 |
|------|------|------|------|
| xurl | 🔀 | 源码 | Hermes版X客户端 |
| xitter | ✅ | ~/.hermes | MimirAether已用此版 |

---

## 20. software-development/（11个）

| 技能 | 状态 | 备注 |
|------|------|------|
| debugging-hermes-tui-commands | ✅ | 已导入 |
| hermes-agent-skill-authoring | ✅ | 已导入 |
| node-inspect-debugger | ✅ | 已导入 |
| plan | ✅ | 已导入（Hermes版） |
| python-debugpy | ✅ | 已导入 |
| requesting-code-review | ✅ | 已导入 |
| spike | ✅ | 已导入 |
| subagent-driven-development | ✅ | 已导入 |
| systematic-debugging | ✅ | 已导入 |
| test-driven-development | ✅ | 已导入 |
| writing-plans | ✅ | 已导入 |

> MimirAether 额外有：`tdd`（中文版，与test-driven-development重复）

---

## 21. yuanbao/（1个）

| 技能 | 状态 | 备注 |
|------|------|------|
| yuanbao | ❌ | 腾讯元宝，平台绑定 |

---

## 22. 额外类别（仅 ~/.hermes/skills）

| 技能 | 类别 | 状态 | 备注 |
|------|------|------|------|
| find-nearby | leisure | ✅ | 已导入 |

---

## 23. optional-skills 中有趣的非ML项（9个）

| 技能 | 类别 | 备注 |
|------|------|------|
| base | blockchain | Solana 二层 | ❌ |
| solana | blockchain | Solana 区块链 | ❌ |
| blender-mcp | creative | Blender 3D建模 via MCP | 📥 ⭐⭐ |
| meme-generation | creative | 梗图生成 | 📥 ⭐ |
| cli | devops | CLI工具管理 | ❌ |
| docker-management | devops | Docker管理 | ❌ |
| agentmail | email | Agent邮件 | ❌ |
| one-three-one-rule | communication | 沟通法则 | ❌ |
| fitness-nutrition | health | 健身营养 | ❌ |
| neuroskill-bci | health | 脑机接口 | ❌ |
| openclaw-migration | migration | OpenClaw迁移 | ❌ |
| 1password | security | 密码管理 | ❌ |
| oss-forensics | security | 开源取证 | ❌ |
| sherlock | security | 用户名搜索 | ❌ |

---

## 📊 汇总

| 分类 | 总数 | ✅已导入 | 📥值得研究 | ❌跳过 |
|------|------|----------|------------|--------|
| apple | 4 | 0 | 0 | 4 |
| autonomous-ai-agents | 4 | 0 | 0 | 4 |
| **creative** | 19 | 0 | **19** | 0 |
| data-science | 1 | 0 | 1 | 0 |
| devops | 3 | 0 | 3 | 0 |
| dogfood | 1 | 0 | 1 | 0 |
| email | 1 | 0 | 1 | 0 |
| gaming | 2 | 2 | 0 | 0 |
| github | 6 | 6 | 0 | 0 |
| mcp | 2 | 2 | 0 | 0 |
| media | 5 | 5 | 0 | 0 |
| mlops | 40 | 22 | 0 | 18 |
| note-taking | 1 | 1 | 0 | 0 |
| productivity | 12 | 6 | 2 | 4 |
| red-teaming | 1 | 1 | 0 | 0 |
| research | 13 | 5 | 0 | 8 |
| smart-home | 1 | 1 | 0 | 0 |
| social-media | 2 | 1 | 0 | 1 |
| software-development | 11 | 11 | 0 | 0 |
| leisure | 1 | 1 | 0 | 0 |
| **总计** | **130** | **64** | **27** | 39 |

### 📥 值得研究的 27 个（按优先级分组）

**P1 — 高度契合 MimirAether（6个）：**
1. `creative/excalidraw` — 手绘图表
2. `creative/architecture-diagram` — 架构图
3. `creative/humanizer` — 文本去AI味
4. `creative/manim-video` — 数学动画
5. `creative/comfyui` — AI图像工作流
6. `creative/sketch` — HTML原型

**P2 — 有价值（10个）：**
7. `creative/claude-design` — HTML制品
8. `creative/baoyu-comic` — 知识漫画
9. `creative/baoyu-infographic` — 信息图
10. `creative/p5js` — 生成艺术
11. `creative/popular-web-designs` — 设计系统参考
12. `creative/songwriting-and-ai-music` — AI音乐
13. `creative/pixel-art` — 像素艺术
14. `data-science/jupyter-live-kernel` — Jupyter
15. `productivity/airtable` — 低代码DB
16. `productivity/maps` — 地图

**P3 — 场景限定（11个）：**
17-27: ascii-art, ascii-video, creative-ideation, design-md, pretext, touchdesigner-mcp, kanban-*, webhook-subscriptions, dogfood, himalaya, blender-mcp, meme-generation
