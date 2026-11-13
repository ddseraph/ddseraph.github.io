# -*- coding: utf-8 -*-
"""把 notices.txt（每行一条公告）渲染成 index.html，供 Kindle 显示。"""
import html
import os
from datetime import datetime, timezone, timedelta

NOTICES_FILE = "notices.txt"
OUT_DIR = "_site"
OUT_FILE = os.path.join(OUT_DIR, "index.html")

def load_notices():
    try:
        with open(NOTICES_FILE, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        lines = []
    return lines

def render_notice(text):
    return (
        '<div style="border-bottom:1px solid #ccc; padding:16px 0;">'
        f'<div style="font-size:30px; line-height:1.4;">{html.escape(text)}</div>'
        '</div>'
    )

def build():
    notices = load_notices()
    now = datetime.now(timezone(timedelta(hours=8)))
    ts = now.strftime("%Y-%m-%d %H:%M")

    if notices:
        block = "\n".join(render_notice(n) for n in notices)
    else:
        block = '<div style="font-size:30px; color:#888;">（暂无公告）</div>'

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>家庭公告板</title>
</head>
<body style="margin:0; padding:0; background:#ffffff; color:#000000; font-family:sans-serif;">
<div style="text-align:center; padding:24px 12px 8px 12px; border-bottom:3px solid #000;">
  <span style="font-size:44px; font-weight:bold;">家庭公告板</span>
  <div style="font-size:20px; color:#333; margin-top:6px;">最后更新：{ts}</div>
</div>
<div style="padding:20px 16px;">
{block}
</div>
<div style="text-align:center; padding:12px; font-size:18px; color:#777;">
每 60 秒自动刷新
</div>
</body>
</html>'''

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"OK: generated {OUT_FILE} with {len(notices)} notices")

if __name__ == "__main__":
    build()
