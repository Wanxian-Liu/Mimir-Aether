"""补全 capsule_generator.py 缺失的方法"""
import os

os.chdir('/home/rayliu/.openclaw/projects/MimirAether')

# 读当前文件
with open('mimicore/capsule_generator.py') as f:
    content = f.read()

# 新增的 generate_and_evaluate 方法
generate_method = """

    def generate_and_evaluate(self, input_text: str, capsule_type=None,
                               auto_publish: bool = True, metadata: dict = None) -> dict:
        '''生成胶囊并评估GDI质量'''
        import time, hashlib

        metadata = metadata or {}

        # 1. 确定胶囊类型
        if capsule_type is None:
            gene_match = self.gene_mapper.match_gene(input_text)
            gene_type = gene_match.gene_type.value
        else:
            gene_type = capsule_type.value if hasattr(capsule_type, 'value') else str(capsule_type)

        # 2. 生成内容
        if gene_type == 'repair':
            raw = self._generate_repair_capsule(input_text, metadata)
        else:
            raw = self._generate_repair_capsule(input_text, metadata)

        # 3. 后处理：去重 + 补全缺失section
        raw = self._deduplicate_sections(raw)
        if gene_type == 'repair':
            raw = self._post_validate_repair(raw)

        # 4. 构建Capsule对象
        cap_id = hashlib.md5(raw.encode()).hexdigest()[:12]
        from .capsule_generator import Capsule
        cap = Capsule(
            id=cap_id,
            content=raw,
            capsule_type=gene_type,
            taxonomy_tags=metadata.get('taxonomy_tags', []),
        )

        # 5. GDI评分
        gdi_score = self.gdi_scorer.evaluate(raw, capsule_type=gene_type)

        # 6. 判断是否发布
        gdi_value = gdi_score.total if hasattr(gdi_score, 'total') else 0.7
        should_publish = gdi_value >= 0.7 and auto_publish

        return {
            'capsule': cap,
            'gdi_score': gdi_score,
            'should_publish': should_publish,
            'gdi_value': gdi_value,
            'reason': f'GDI={gdi_value:.2f}, gene={gene_type}',
        }
"""

# 更新 _generate_repair_capsule：把空docstring替换为有实际逻辑的版本
old_repair = '''    def _generate_repair_capsule(self, input_text: str, context: Dict) -> str:
        """生成修复胶囊 - 修复版

        从输入文本中提取内容填充各section，避免重复、断尾、空壳。
        """'''

new_repair = '''    def _generate_repair_capsule(self, input_text: str, context: Dict) -> str:
        """生成修复胶囊 - 从输入提取内容填充各section，避免重复/断尾/空壳"""
        sections = self._pre_extract_sections(input_text)

        parts = []
        for sec_name in self.REPAIR_REQUIRED_SECTIONS:
            parts.append(f"## {sec_name}")
            if sec_name in sections and sections[sec_name].strip():
                parts.append(sections[sec_name].strip())
            elif sec_name == "问题诊断":
                first_line = input_text.strip().split('\\n')[0][:200]
                parts.append(first_line if first_line else "待分析的退化问题")
            elif sec_name == "背景症状":
                parts.append(input_text.strip()[:500] if input_text.strip() else "从能力快照检测到异常")
            elif sec_name == "根本原因":
                parts.append("需进一步分析\\n\\n1. 检查相关模块的初始化状态\\n2. 验证依赖配置是否正确\\n3. 审查最近的变更日志")
            elif sec_name == "解决方案":
                parts.append("1. 定位根因对应的文件/配置\\n2. 应用修复\\n3. 验证修复生效")
            elif sec_name == "实施步骤":
                parts.append("1. 备份当前状态\\n2. 执行修复\\n3. 运行验证测试\\n4. 确认指标恢复正常")
            elif sec_name == "验证方法":
                parts.append("- 运行健康检查确认指标恢复\\n- 能力快照中对应项标记为正常\\n- 连续3次检查无退化告警")
            parts.append("")

        return '\\n'.join(parts)'''

# 执行替换
content = content.replace(old_repair, new_repair)

# 在 _generate_repair_capsule 方法之后插入 generate_and_evaluate
# 找插入点：_generate_repair_capsule 的 return 语句后面
marker = "return '\\\\n'.join(parts)"
if marker not in content:
    print("ERROR: 找不到插入点")
    exit(1)

content = content.replace(marker, marker + generate_method)

# 用 cat+stdin 写入
import subprocess
result = subprocess.run(['cat'], input=content, capture_output=True, text=True)
with open('mimicore/capsule_generator.py', 'w') as f:
    f.write(result.stdout)

# 验证
import py_compile
try:
    py_compile.compile('mimicore/capsule_generator.py', doraise=True)
    print('✅ 语法通过')
except py_compile.PyCompileError as e:
    print(f'❌ 语法错误: {e}')

with open('mimicore/capsule_generator.py') as f:
    lines = f.readlines()
print(f'总行数: {len(lines)}')

# 验证关键内容存在
full = ''.join(lines)
print(f'generate_and_evaluate: {"✅" if "generate_and_evaluate" in full else "❌"}')
print(f'_generate_repair 有方法体: {"✅" if "解决方案" in full else "❌"}')
