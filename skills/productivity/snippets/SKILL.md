# 代码片段管理 (snippets)

## 用途
快速保存、搜索和复用常用代码片段。

## 核心操作

### 保存片段
```bash
# 格式: snippet save <name> <language> "<content>"
snippet save "hello-py" python 'print("Hello")'
```

### 搜索片段
```bash
snippet search <keyword>
```

### 列出所有片段
```bash
snippet list
```

### 使用片段
```bash
snippet use <name> | clipboard  # 复制到剪贴板
snippet use <name> --execute    # 直接执行
```

## 实现方式
- 存储位置: `~/.snippets/`
- 每个片段一个JSON文件
- 索引文件: `~/.snippets/index.json`

## 依赖
- jq (用于JSON处理)
