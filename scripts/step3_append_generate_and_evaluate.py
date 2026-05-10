#!/usr/bin/env python3
"""Step 3: Append generate_and_evaluate method to CapsuleGenerator.

The method signature matches mimircore_tool.py's call:
    generate_and_evaluate(input_text, capsule_type, auto_publish, metadata)

Pipeline inside:
    _generate_repair_capsule → _deduplicate_sections → _post_validate_repair → GDI scoring
"""

import hashlib
import time

CAPSULE_GENERATOR_PATH = "/home/rayliu/.openclaw/projects/MimirAether/mimicore/capsule_generator.py"

METHOD_SOURCE = """
    # ============ generate_and_evaluate (公共入口) ============

    def generate_and_evaluate(
        self,
        input_text: str,
        capsule_type: object = None,
        auto_publish: bool = True,
        metadata: dict = None
    ) -> dict:
        \"\"\"
        生成并评估胶囊（公共入口，供 mimircore_tool 调用）

        Pipeline:
            1. 类型识别（若 capsule_type=None 则自动识别）
            2. 生成内容（目前支持 repair，其他类型 fallback 到 repair 格式）
            3. 去重 + 后校验
            4. GDI 评分
            5. 返回胶囊 + 评分 + 是否发布

        Args:
            input_text: 输入知识内容
            capsule_type: 胶囊类型（None=auto，使用 GeneMapper 自动识别）
            auto_publish: 是否自动发布（GDI >= 0.7 时）
            metadata: 额外元数据

        Returns:
            dict: {capsule, gdi_score, should_publish, reason}
        \"\"\"
        if metadata is None:
            metadata = {}

        # ── 1. 类型识别 ──
        if capsule_type is None:
            # auto 模式：用 GeneMapper 自动识别
            cap_type, gene_match = self.gene_mapper.select_capsule_type(input_text)
        else:
            cap_type = capsule_type
            gene_match = None

        # ── 2. 生成胶囊内容 ──
        # 目前主要支持 repair 类型；其他类型复用 repair 格式框架
        context = {
            "symptoms": metadata.get("symptoms", ""),
            "root_cause": metadata.get("root_cause", ""),
            "solution": metadata.get("solution", ""),
            "steps": metadata.get("steps", ""),
            "verification": metadata.get("verification", ""),
        }
        content = self._generate_repair_capsule(input_text, context)

        # ── 3. 去重 + 后校验 ──
        content = self._deduplicate_sections(content)
        content = self._post_validate_repair(content)

        # ── 4. 构建胶囊对象 ──
        capsule_id = hashlib.md5((input_text + str(time.time())).encode()).hexdigest()[:16]

        # 从 gene_match 提取标签
        taxonomy_tags = metadata.get("tags", [])
        if gene_match and gene_match.matched_signals:
            for signal in gene_match.matched_signals:
                kw = signal.raw_signal[:20]
                if kw and kw not in taxonomy_tags:
                    taxonomy_tags.append(kw)

        capsule = Capsule(
            id=capsule_id,
            content=content,
            capsule_type=cap_type.value if hasattr(cap_type, 'value') else str(cap_type),
            memory_type="long_term",
            taxonomy_tags=taxonomy_tags[:10],
            knowledge_type=metadata.get("knowledge_type", {}),
            metadata={
                "source": metadata.get("source", "MimirAether"),
                "created_at": time.time(),
                "capsule_type": str(cap_type),
                **(metadata.get("extra", {})),
            },
        )

        # ── 5. GDI 评分 ──
        capsule_dict = capsule.to_dict()
        gdi_result = self.gdi_scorer.score(capsule_dict)
        capsule.gdi_score = gdi_result

        # ── 6. 发布决策 ──
        should_publish = gdi_result.should_publish()
        if not should_publish:
            reason = (
                f"GDI total {gdi_result.total:.3f} < threshold {GDIResult.PUBLISH_THRESHOLD}; "
                f"intrinsic={gdi_result.intrinsic:.3f}, usage={gdi_result.usage:.3f}, "
                f"social={gdi_result.social:.3f}, freshness={gdi_result.freshness:.3f}"
            )
        else:
            reason = (
                f"GDI total {gdi_result.total:.3f} >= threshold {GDIResult.PUBLISH_THRESHOLD}; "
                f"all dimensions OK"
            )

        return {
            "capsule": capsule,
            "gdi_score": gdi_result,
            "should_publish": should_publish,
            "reason": reason,
        }
"""


def main():
    print(f"Reading {CAPSULE_GENERATOR_PATH} ...")
    with open(CAPSULE_GENERATOR_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    # Find the last class-level element before EOF
    # We'll append the new method just before the final empty line(s)
    # Strip trailing whitespace, add method, restore final newline
    stripped = original.rstrip()

    appended = stripped + "\n" + METHOD_SOURCE + "\n"

    print(f"Writing {len(appended)} bytes (was {len(original)}) ...")
    with open(CAPSULE_GENERATOR_PATH, "w", encoding="utf-8") as f:
        f.write(appended)

    print("Done. Verifying import ...")
    # Verify
    import sys
    # Clear any cached modules
    for mod in list(sys.modules.keys()):
        if "mimicore" in mod or "capsule_generator" in mod:
            del sys.modules[mod]

    from mimicore.capsule_generator import CapsuleGenerator
    g = CapsuleGenerator()
    assert hasattr(g, "generate_and_evaluate"), "generate_and_evaluate not found!"
    print("SUCCESS: generate_and_evaluate method is now on CapsuleGenerator")


if __name__ == "__main__":
    main()
