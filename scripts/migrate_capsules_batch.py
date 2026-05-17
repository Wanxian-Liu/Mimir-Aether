#!/usr/bin/env python3
"""Migrate .md capsules from mimicore/public/ to ~/.mimiraether/memory/capsules/ as .html.
Usage: python3 scripts/migrate_capsules_batch.py [batch_size]
Default batch_size=10.
"""
import os, re, hashlib, sys
from datetime import datetime, timezone, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'mimicore', 'public')
DST = os.path.expanduser('~/.mimiraether/memory/capsules')

os.makedirs(DST, exist_ok=True)

batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10

md_files = sorted([f for f in os.listdir(SRC) if f.endswith('.md')])
html_files = set(os.listdir(DST))

# Find missing
missing = []
for fname in md_files:
    if re.match(r'^[0-9a-f]{12}_', fname):
        cid = fname[:12]
    else:
        cid = hashlib.md5(fname.encode()).hexdigest()[:12]
    if not any(h.startswith(cid) for h in html_files):
        missing.append((fname, cid))
    if len(missing) >= batch_size:
        break

now = datetime.now(timezone(timedelta(hours=8)))
count = 0

for fname, cid in missing:
    with open(os.path.join(SRC, fname)) as f:
        content = f.read()

    # Parse frontmatter
    parts = content.split('---', 2)
    frontmatter = {}
    body = content
    if len(parts) >= 3 and content.startswith('---'):
        try:
            import yaml
            frontmatter = yaml.safe_load(parts[1]) or {}
        except Exception:
            pass
        body = parts[2].strip()

    title = frontmatter.get('title', fname.replace('.md', '').replace('_', ' '))
    gdi = frontmatter.get('gdi', 'N/A')
    source = frontmatter.get('source', 'MimirAether')
    imported = frontmatter.get('imported_at', now.isoformat())
    ctype = frontmatter.get('capsule_type', frontmatter.get('category', 'optimize'))
    tags = frontmatter.get('tags', [])
    summary = frontmatter.get('summary', '')

    # Simple markdown -> HTML
    html_body = body
    html_body = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
    html_body = re.sub(r'^- (.+)$', r'<li>\1</li>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', html_body, flags=re.MULTILINE)

    paragraphs = html_body.split('\n\n')
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<h') or p.startswith('<li'):
            wrapped.append(p)
        else:
            wrapped.append(f'<p>{p}</p>')
    html_body = '\n'.join(wrapped)

    tags_html = ', '.join(tags) if tags else ''

    meta_tags = ''
    if tags_html:
        meta_tags += f'<meta name="mimir-tags" content="{tags_html}">\n'
    if summary:
        meta_tags += f'<meta name="mimir-summary" content="{summary}">\n'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="mimir-kind" content="capsule">
<meta name="mimir-id" content="{cid}">
<meta name="mimir-created" content="{now.isoformat()}">
<meta name="mimir-updated" content="{now.isoformat()}">
<meta name="mimir-source" content="{source}">
{meta_tags}</head>
<body>
<h1>{title}</h1>
<dl>
<dt>GDI</dt><dd>{gdi}</dd><dt>capsule_type</dt><dd>{ctype}</dd><dt>source</dt><dd>{source}</dd><dt>imported_at</dt><dd>{imported}</dd>
</dl>
<article>
{html_body}
</article>
</body>
</html>'''

    out_name = f'{cid}_{fname.replace(".md", "")}.html'
    out_path = os.path.join(DST, out_name)
    with open(out_path, 'w') as f:
        f.write(html)
    count += 1
    print(f'  ✅ {fname} -> {out_name}')

remaining = len(md_files) - len(html_files) - count
print(f'\nBatch: {count}/{batch_size} | Remaining: {remaining}')
