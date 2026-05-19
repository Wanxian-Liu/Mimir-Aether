"""Tests for Feishu card table column name normalization."""

from gateway.html_to_feishu_card import _html_table_to_card, _normalize_table_column_name


def test_normalize_table_column_name_empty_to_em_dash():
    assert _normalize_table_column_name("") == "—"
    assert _normalize_table_column_name("   ") == "—"
    assert _normalize_table_column_name("&nbsp;") == "—"


def test_normalize_table_column_name_preserves_non_empty():
    assert _normalize_table_column_name("维度") == "维度"
    assert _normalize_table_column_name(" 得分 ") == "得分"


def test_html_table_to_card_replaces_empty_headers():
    html = """<table>
<tr><th>列A</th><th></th><th>列C</th></tr>
<tr><td>1</td><td>2</td><td>3</td></tr>
</table>"""
    card = _html_table_to_card(html)
    assert card is not None
    names = [cell["content"] for cell in card["header"]]
    assert names == ["列A", "—", "列C"]
    assert all(name.strip() for name in names)
