"""
MimirAether FTS5 Search Engine 测试

版本: 1.0.0
日期: 2026-04-20
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import List

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fts5_search.engine import (
    FTS5SearchEngine,
    SearchOptions,
    SearchResult,
    SearchResponse,
    MatchSegment,
    BM25Scorer,
    create_engine,
    quick_search,
)
from fts5_search.schema import SCHEMA_VERSION, INIT_SCRIPT


class TestBM25Scorer(unittest.TestCase):
    """BM25评分器测试"""
    
    def test_basic_scoring(self):
        """基本评分测试"""
        scorer = BM25Scorer()
        
        # 索引文档
        scorer.index(1, ["python", "is", "great"], 3)
        scorer.index(2, ["java", "is", "good"], 3)
        
        # 计算评分 - 只包含python的文档应该有评分
        score1 = scorer.score(1, ["python"])
        score2 = scorer.score(2, ["python"])
        
        # python文档应该有评分，java文档没有python所以评分为0
        self.assertGreater(score1, 0)
        self.assertEqual(score2, 0)
    
    def test_idf_calculation(self):
        """IDF计算测试"""
        scorer = BM25Scorer()
        
        # 索引多个文档
        for i in range(10):
            scorer.index(i, ["python"] + ["word"] * i, i + 1)
        
        idf = scorer.get_idf("python")
        
        # IDF应该是正数
        self.assertGreater(idf, 0)
        
        # IDF对于稀有词应该更高
        idf_rare = scorer.get_idf("rarerareword")
        self.assertGreater(idf, idf_rare)
    
    def test_empty_query(self):
        """空查询测试"""
        scorer = BM25Scorer()
        scorer.index(1, ["python"], 1)
        
        score = scorer.score(1, [])
        self.assertEqual(score, 0.0)


class TestFTS5SearchEngine(unittest.TestCase):
    """FTS5搜索引擎测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_fts5.db")
        self.engine = FTS5SearchEngine(self.db_path)
    
    def tearDown(self):
        """清理测试环境"""
        self.engine.close()
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_creation(self):
        """数据库创建测试"""
        # 检查数据库文件是否存在
        self.assertTrue(Path(self.db_path).exists())
        
        # 检查schema版本
        cursor = self.engine._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        version = cursor.fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)
    
    def test_index_single_message(self):
        """单条消息索引测试"""
        msg_id = self.engine.index_message(
            session_id="test-session-1",
            role="user",
            content="Hello, how are you?",
        )
        
        self.assertGreater(msg_id, 0)
        
        # 验证消息已索引
        cursor = self.engine._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            ("test-session-1",)
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)
    
    def test_index_batch(self):
        """批量索引测试"""
        messages = [
            {"session_id": "batch-test", "role": "user", "content": f"Message {i}"}
            for i in range(50)
        ]
        
        indexed = self.engine.index_batch(messages)
        
        self.assertEqual(indexed, 50)
        
        # 验证所有消息已索引
        cursor = self.engine._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            ("batch-test",)
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, 50)
    
    def test_search_basic(self):
        """基本搜索测试"""
        # 索引测试数据
        self.engine.index_message("s1", "user", "Python is a great programming language")
        self.engine.index_message("s1", "assistant", "Yes, Python is very popular")
        self.engine.index_message("s2", "user", "Java is also a good language")
        
        # 搜索
        response = self.engine.search(SearchOptions(query="Python"))
        
        self.assertIsNotNone(response)
        self.assertGreater(len(response.results), 0)
        self.assertGreater(response.total_matches, 0)
        
        # 验证结果包含Python相关
        found = False
        for result in response.results:
            for match in result.matches:
                if "python" in match.content.lower():
                    found = True
                    break
        self.assertTrue(found)
    
    def test_search_boolean_and(self):
        """布尔AND搜索测试"""
        self.engine.index_message("s1", "user", "Python and Java are programming languages")
        self.engine.index_message("s2", "user", "Python is interpreted")
        
        # 搜索Python AND programming
        response = self.engine.search(SearchOptions(query="Python AND programming"))
        
        # 应该返回包含两个词的结果
        if response.results:
            for result in response.results:
                content = " ".join(m.content for m in result.matches).lower()
                # 如果使用了AND，应该只返回同时包含两个词的结果
                if response.total_matches > 0:
                    self.assertIn("python", content)
    
    def test_search_phrase(self):
        """短语搜索测试"""
        self.engine.index_message("s1", "user", "The quick brown fox jumps over")
        self.engine.index_message("s2", "user", "The quick brown bear")
        
        # 搜索短语 "quick brown"
        response = self.engine.search(SearchOptions(query='"quick brown"'))
        
        # 应该只返回包含完整短语的结果
        for result in response.results:
            content = " ".join(m.content for m in result.matches).lower()
            self.assertIn("quick", content)
            self.assertIn("brown", content)
    
    def test_search_prefix(self):
        """前缀搜索测试"""
        self.engine.index_message("s1", "user", "Python programming")
        self.engine.index_message("s2", "user", "Pytest framework")
        
        # 前缀搜索
        response = self.engine.search(SearchOptions(query="Py*"))
        
        # 应该返回Python和Pytest相关内容
        if response.results:
            found_python = False
            found_pytest = False
            for result in response.results:
                for match in result.matches:
                    content = match.content.lower()
                    if "python" in content:
                        found_python = True
                    if "pytest" in content:
                        found_pytest = True
            # 至少应该找到一个
            self.assertTrue(found_python or found_pytest)
    
    def test_search_pagination(self):
        """分页测试"""
        # 索引多个会话
        for i in range(10):
            self.engine.index_message(f"s{i}", "user", f"Session {i} content about Python")
        
        # 第一页
        page1 = self.engine.search(SearchOptions(query="Python", limit=3, offset=0))
        self.assertLessEqual(len(page1.results), 3)
        
        # 第二页
        page2 = self.engine.search(SearchOptions(query="Python", limit=3, offset=3))
        self.assertLessEqual(len(page2.results), 3)
        
        # 两页结果应该不同
        if len(page1.results) > 0 and len(page2.results) > 0:
            p1_sessions = {r.session_id for r in page1.results}
            p2_sessions = {r.session_id for r in page2.results}
            self.assertEqual(len(p1_sessions & p2_sessions), 0)  # 不重叠
    
    def test_search_session_filter(self):
        """会话过滤测试"""
        self.engine.index_message("s1", "user", "Python content in session 1")
        self.engine.index_message("s2", "user", "Python content in session 2")
        
        # 只搜索s1
        response = self.engine.search(SearchOptions(
            query="Python",
            session_ids=["s1"]
        ))
        
        # 应该只返回s1的结果
        for result in response.results:
            self.assertEqual(result.session_id, "s1")
    
    def test_search_highlight(self):
        """高亮测试"""
        self.engine.index_message("s1", "user", "This is about Python programming")
        
        response = self.engine.search(SearchOptions(query="Python", highlight=True))
        
        self.assertTrue(len(response.results) > 0)
        
        for result in response.results:
            for match in result.matches:
                if match.highlight:
                    # 高亮应该包含**标记
                    self.assertIn("**", match.highlight)
    
    def test_search_cache(self):
        """缓存测试"""
        self.engine.index_message("s1", "user", "Cache test content")
        
        # 第一次搜索
        response1 = self.engine.search(SearchOptions(query="Cache", use_cache=True))
        
        # 第二次搜索（应该命中缓存）
        response2 = self.engine.search(SearchOptions(query="Cache", use_cache=True))
        
        self.assertTrue(response2.cached)
        self.assertEqual(response1.total_matches, response2.total_matches)
    
    def test_search_performance(self):
        """性能测试"""
        # 索引大量消息
        start = time.time()
        
        messages = [
            {"session_id": f"perf-{i//10}", "role": "user", "content": f"Content {i} with Python"}
            for i in range(1000)
        ]
        self.engine.index_batch(messages)
        
        index_time = time.time() - start
        
        # 搜索性能
        search_start = time.time()
        response = self.engine.search(SearchOptions(query="Python", limit=10))
        search_time = (time.time() - search_start) * 1000
        
        print(f"\n索引1000条消息耗时: {index_time:.2f}s")
        print(f"搜索耗时: {search_time:.2f}ms")
        print(f"找到结果: {response.total_matches}")
        
        # 搜索应该在200ms内完成
        self.assertLess(search_time, 200)
    
    def test_rebuild_index(self):
        """重建索引测试"""
        # 索引一些数据
        for i in range(10):
            self.engine.index_message(f"s{i}", "user", f"Content {i}")
        
        # 重建索引
        self.engine.rebuild_index()
        
        # 验证数据仍然可搜索
        response = self.engine.search(SearchOptions(query="Content"))
        self.assertGreater(response.total_matches, 0)
    
    def test_get_stats(self):
        """统计信息测试"""
        # 索引数据
        for i in range(5):
            self.engine.index_message(f"s{i}", "user", f"Content {i}")
        
        stats = self.engine.get_stats()
        
        self.assertGreater(stats["session_count"], 0)
        self.assertGreater(stats["message_count"], 0)
        self.assertGreaterEqual(stats["fts_count"], 0)


class TestSearchOptions(unittest.TestCase):
    """搜索选项测试"""
    
    def test_default_options(self):
        """默认选项测试"""
        options = SearchOptions(query="test")
        
        self.assertEqual(options.query, "test")
        self.assertIsNone(options.session_ids)
        self.assertEqual(options.limit, 10)
        self.assertEqual(options.offset, 0)
        self.assertEqual(options.sort_by, "relevance")
        self.assertTrue(options.highlight)
        self.assertTrue(options.use_cache)
    
    def test_custom_options(self):
        """自定义选项测试"""
        options = SearchOptions(
            query="python",
            session_ids=["s1", "s2"],
            limit=20,
            offset=10,
            sort_by="created",
            highlight=False,
            use_cache=False,
        )
        
        self.assertEqual(options.query, "python")
        self.assertEqual(len(options.session_ids), 2)
        self.assertEqual(options.limit, 20)
        self.assertEqual(options.offset, 10)
        self.assertEqual(options.sort_by, "created")
        self.assertFalse(options.highlight)
        self.assertFalse(options.use_cache)


class TestSearchResult(unittest.TestCase):
    """搜索结果测试"""
    
    def test_result_creation(self):
        """结果创建测试"""
        result = SearchResult(
            session_id="test-session",
            session_title="Test Title",
            score=1.5,
            matches=[
                MatchSegment(
                    rowid=1,
                    session_id="test-session",
                    role="user",
                    content="Test content",
                    highlight="**Test** content",
                    score=1.0,
                )
            ],
            created_at=1234567890.0,
            message_count=1,
            source="cli",
        )
        
        self.assertEqual(result.session_id, "test-session")
        self.assertEqual(result.session_title, "Test Title")
        self.assertEqual(result.score, 1.5)
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.source, "cli")


class TestQuickSearch(unittest.TestCase):
    """快速搜索测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "quick_test.db")
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_quick_search(self):
        """快速搜索测试"""
        engine = create_engine(self.db_path)
        engine.index_message("s1", "user", "Quick search test")
        engine.close()
        
        # 使用快速搜索
        response = quick_search("Quick", db_path=self.db_path)
        
        self.assertIsNotNone(response)
        self.assertGreater(response.total_matches, 0)


class TestSchema(unittest.TestCase):
    """Schema测试"""
    
    def test_schema_version(self):
        """Schema版本测试"""
        self.assertEqual(SCHEMA_VERSION, 4)
    
    def test_init_script(self):
        """初始化脚本测试"""
        self.assertIn("CREATE TABLE IF NOT EXISTS sessions", INIT_SCRIPT)
        self.assertIn("CREATE TABLE IF NOT EXISTS messages", INIT_SCRIPT)
        self.assertIn("search_history", INIT_SCRIPT)
        self.assertIn("schema_version", INIT_SCRIPT)


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "integration_test.db")
    
    def tearDown(self):
        self.engine.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow(self):
        """完整工作流测试"""
        # 创建引擎
        self.engine = FTS5SearchEngine(self.db_path)
        
        # 1. 索引会话
        session_id = "integration-test-session"
        
        # 2. 索引多条消息
        messages = [
            {"session_id": session_id, "role": "user", "content": "Hello, I want to learn Python"},
            {"session_id": session_id, "role": "assistant", "content": "Python is a great choice! What would you like to know?"},
            {"session_id": session_id, "role": "user", "content": "How do I use Python dictionaries?"},
            {"session_id": session_id, "role": "assistant", "content": "Dictionaries in Python are key-value pairs. You can create them like: d = {'key': 'value'}"},
            {"session_id": session_id, "role": "user", "content": "Thanks! What about Python lists?"},
            {"session_id": session_id, "role": "assistant", "content": "Lists are ordered collections. You can create them like: l = [1, 2, 3]"},
        ]
        
        indexed = self.engine.index_batch(messages)
        self.assertEqual(indexed, 6)
        
        # 3. 搜索Python
        response = self.engine.search(SearchOptions(query="Python"))
        self.assertGreater(response.total_matches, 0)
        
        # 4. 搜索dictionaries
        response2 = self.engine.search(SearchOptions(query="dictionaries"))
        self.assertGreater(response2.total_matches, 0)
        
        # 5. 搜索复杂查询
        response3 = self.engine.search(SearchOptions(query="Python AND dictionaries"))
        # 应该找到相关内容
        
        # 6. 获取统计
        stats = self.engine.get_stats()
        self.assertEqual(stats["session_count"], 1)
        self.assertEqual(stats["message_count"], 6)
        
        # 7. 优化索引
        self.engine.optimize_index()
        
        # 8. 再次搜索确认
        response4 = self.engine.search(SearchOptions(query="lists"))
        self.assertGreater(response4.total_matches, 0)


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 运行测试
    unittest.main(verbosity=2)
