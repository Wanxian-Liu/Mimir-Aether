# tests/fixtures/example_fixture.py
"""示例 fixture：创建临时技能目录供测试使用"""

import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_skill_dir():
    """在 tmp_path 下创建临时技能目录。
    
    Structure:
        tmp_path/
        └── skills/
            └── test-skill/
                └── SKILL.md
    """
    tmp = Path(tempfile.mkdtemp(prefix="test_skill_"))
    skill_dir = tmp / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: Test skill\n---\n\n# Test\nContent\n"
    )
    yield skill_dir
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
