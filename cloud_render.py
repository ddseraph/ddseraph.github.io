# -*- coding: utf-8 -*-
"""云端渲染脚本：读取 notices.txt + 高德天气 + 日历，生成公告板 PNG。

供 GitHub Actions 定时调用，输出到 _site/frame.png，部署到 Pages。
天气 Key 从环境变量 GAODE_KEY 读取。
"""
import json
import os
import io
import calendar
import urllib.request
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

W, H = 758, 1024          # PW1 原生分辨率
CITY_ADCODE = "310000"    # 上海
CITY_NAME = "上海"
GAODE_KEY = os.environ.get("GAODE_KEY", "")

NOTICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notices.txt")
OUT_DIR = "_site"
OUT_FILE = os.path.join(OUT_DIR, "frame.png")


# ---------- 字体（兼容 Windows 本地 和 Linux 云端）----------
def load_font(size):
    candidates = [
        ("C:/Windows/Fonts/msyh.ttc", True),
        ("C:/Windows/Fonts/simhei.ttf", False),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", True),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", True),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", False),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", False),
    ]
    for p, is_ttc in candidates:
        try:
            if is_ttc:
                return ImageFont.truetype(p, size, index=0)
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------- 公告 ----------
def load_notices():
    # 优先从 Gitee API 拉取公告（带令牌，避免 raw 重定向问题）
    gitee_token = os.environ.get("GITEE_TOKEN", "")
    if gitee_token:
        try:
            import base64
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = "https://gitee.com/api/v5/repos/ddseraph/bulletin/contents/notices.txt"
            req = urllib.request.Request(url, headers={"Authorization": "token " + gitee_token, "User-Agent": "bulletin"})
            resp = opener.open(req, timeout=15)
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("content"):
                text = base64.b64decode(data["content"]).decode("utf-8")
                return [ln.strip() for ln in text.splitlines() if ln.strip()]
        except Exception as e:
            print("从 Gitee 拉取公告失败: %r" % e)
    # 回退到本地 notices.txt
    try:
        with open(NOTICES_FILE, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception:
        return ["（暂无公告）"]


# ---------- 天气 ----------
def get_weather():
    if not GAODE_KEY:
        print("天气未获取：GAODE_KEY 环境变量为空")
        return None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        url = "https://restapi.amap.com/v3/weather/weatherInfo?city=%s&key=%s&extensions=base&output=json" % (CITY_ADCODE, GAODE_KEY)
        resp = opener.open(urllib.request.Request(url), timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        live = data["lives"][0]
        desc = live["weather"]
        temp = live["temperature"]
        hum = live["humidity"]
        text = "%s  %s  %s°C  湿度%s%%" % (CITY_NAME, desc, temp, hum)
        # 最高/最低
        try:
            url2 = "https://restapi.amap.com/v3/weather/weatherInfo?city=%s&key=%s&extensions=all&output=json" % (CITY_ADCODE, GAODE_KEY)
            resp2 = opener.open(urllib.request.Request(url2), timeout=15)
            data2 = json.loads(resp2.read().decode("utf-8"))
            today = data2["forecasts"][0]["casts"][0]
            high = today["daytemp"]
            low = today["nighttemp"]
            text = "%s  %s  %s~%s°C  湿度%s%%" % (CITY_NAME, desc, low, high, hum)
        except Exception:
            pass
        return text
    except Exception as e:
        print("天气获取失败: %r" % e)
        return None


# ---------- 日历 ----------
def draw_calendar(d, y):
    now = datetime.now(timezone(timedelta(hours=8)))
    year, month = now.year, now.month
    d.text((W // 2, y), "%d年%d月" % (year, month), font=load_font(30), fill=0, anchor="mm")
    y += 40
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    cell_w = 76
    start_x = (W - cell_w * 7) // 2
    wd_font = load_font(20)
    for i, wd in enumerate(weekdays):
        d.text((start_x + i * cell_w + cell_w // 2, y), wd, font=wd_font, fill=128, anchor="mm")
    y += 28
    cal = calendar.Calendar(firstweekday=0)
    days = list(cal.itermonthdays(year, month))
    day_font = load_font(24)
    cell_h = 36
    for idx, day in enumerate(days):
        if day == 0:
            continue
        row, col = idx // 7, idx % 7
        x = start_x + col * cell_w + cell_w // 2
        yy = y + row * cell_h + cell_h // 2
        if day == now.day:
            d.rounded_rectangle([x - 16, yy - 16, x + 16, yy + 16], radius=7, fill=0)
            d.text((x, yy), str(day), font=day_font, fill=255, anchor="mm")
        else:
            d.text((x, yy), str(day), font=day_font, fill=0, anchor="mm")
    y += cell_h * 6 + 12
    return y


# ---------- 换行 ----------
def wrap_text(text, max_chars):
    out = []
    while len(text) > max_chars:
        out.append(text[:max_chars])
        text = text[max_chars:]
    out.append(text)
    return out if out else [""]


# ---------- 两栏公告 ----------
def render_notices_two_col(d, y, notices, max_y):
    """两栏渲染公告：奇数条左栏、偶数条右栏，字号自适应"""
    available = max_y - y
    if available < 60 or not notices:
        return y

    col_w = 340
    left_x = 40
    right_x = left_x + col_w + 18

    # 自适应字号：保证两栏都能放下
    font_size = 34
    while font_size >= 20:
        chars_per_line = max(6, int((col_w - 30) / font_size))
        line_h = int(font_size * 1.5)
        gap = int(font_size * 0.45)
        left_h = right_h = 0
        for i, n in enumerate(notices):
            h = len(wrap_text(n, chars_per_line)) * line_h + gap
            if i % 2 == 0:
                left_h += h
            else:
                right_h += h
        if max(left_h, right_h) <= available:
            break
        font_size -= 2

    chars_per_line = max(6, int((col_w - 30) / font_size))
    line_h = int(font_size * 1.5)
    gap = int(font_size * 0.45)
    body_font = load_font(font_size)

    left_y = right_y = y
    for i, notice in enumerate(notices):
        col_x = left_x if i % 2 == 0 else right_x
        col_y = left_y if i % 2 == 0 else right_y
        lines = wrap_text(notice, chars_per_line)
        bar_w = max(4, int(font_size * 0.12))
        bar_h = int(line_h * 0.85)
        d.rounded_rectangle([col_x, col_y + int(line_h * 0.12), col_x + bar_w, col_y + int(line_h * 0.12) + bar_h], radius=2, fill=0)
        indent = col_x + bar_w + 10
        d.text((indent, col_y), lines[0], font=body_font, fill=0)
        col_y += line_h
        for line in lines[1:]:
            d.text((indent, col_y), line, font=body_font, fill=0)
            col_y += line_h
        col_y += gap
        if i % 2 == 0:
            left_y = col_y
        else:
            right_y = col_y

    return max(left_y, right_y)


# ---------- 渲染 ----------
def render_png():
    notices = load_notices()
    now = datetime.now(timezone(timedelta(hours=8)))
    updated = now.strftime("%m-%d %H:%M")

    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    TOP_OFFSET = 25  # 顶部留白约 3 毫米，避开 Kindle 状态栏

    # 顶部标题（下移 TOP_OFFSET）
    d.rectangle([0, TOP_OFFSET, W, TOP_OFFSET + 108], fill=0)
    d.text((W // 2, TOP_OFFSET + 42), "2506公告板", font=load_font(46), fill=255, anchor="mm")
    d.text((W // 2, TOP_OFFSET + 88), "更新：%s" % updated, font=load_font(20), fill=200, anchor="mm")

    y = TOP_OFFSET + 108 + 14
    # 日历（最上）
    y = draw_calendar(d, y)
    d.line([(30, y), (W - 30, y)], fill=180, width=2)
    y += 12

    # 天气（中间，浅灰卡片样式）
    weather = get_weather()
    if weather:
        card_h = 66
        d.rounded_rectangle([30, y, W - 30, y + card_h], radius=14, fill=220)
        d.text((W // 2, y + card_h // 2), weather, font=load_font(38), fill=0, anchor="mm")
        y += card_h + 10
    else:
        y += 20
    d.line([(30, y), (W - 30, y)], fill=180, width=2)
    y += 12

    # 公告（最下，两栏，字号自适应）
    y = render_notices_two_col(d, y, notices, H - 60)

    d.text((W // 2, H - 25), "自动刷新", font=load_font(20), fill=160, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    png = render_png()
    with open(OUT_FILE, "wb") as f:
        f.write(png)
    print("OK: generated %s (%d bytes)" % (OUT_FILE, len(png)))
