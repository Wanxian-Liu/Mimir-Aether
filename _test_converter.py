#!/usr/bin/env python3
"""Quick test of HTML→Feishu Card converter"""
import sys, json
sys.path.insert(0, '.')

from gateway.html_to_feishu_card import convert_or_fallback, USE_HTML_OUTPUT

# Simulate a real Mimir HTML output with proper markers
html = """<!-- MIMIR:HTML_OUTPUT template=dashboard -->
<h1>MimirAether Benchmark</h1>
<p>2026-05-14 · Score: 98.7/100</p>
<table>
<tr><th>维度</th><th>得分</th></tr>
<tr><td>工具编排</td><td>100%</td></tr>
<tr><td>代码生成</td><td>100%</td></tr>
</table>
<details><summary>详情</summary>更多信息...</details>
<!-- /MIMIR:HTML_OUTPUT -->"""

print('USE_HTML_OUTPUT:', USE_HTML_OUTPUT)
result = convert_or_fallback(html, 'Benchmark')
print('mode:', result['mode'])
if result['mode'] == 'card':
    payload = result['payload']
    print('msg_type:', payload.get('msg_type'))
    card = json.loads(payload['content'])
    print('header:', card.get('header',{}).get('title',{}).get('content','N/A'))
    print('elements count:', len(card.get('elements',[])))
    for i, el in enumerate(card.get('elements',[])):
        print(f'  el[{i}]: tag={el.get("tag")} preview={str(el)[:100]}')
    # Validate JSON
    serialized = json.dumps(payload, ensure_ascii=False)
    print(f'\n✅ Valid JSON: {len(serialized)} bytes')
else:
    print('fallback_reason:', result.get('fallback_reason','?'))
    print('payload preview:', str(result['payload'])[:300])
