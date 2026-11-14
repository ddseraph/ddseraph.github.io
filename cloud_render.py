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
    try:
        with open(NOTICES_FILE, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception:
        return ["（暂无公告）"]


# ---------- 天气 ----------
def get_weather():
    if not GAODE_KEY:
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
    except Exception:
        return None


# ---------- 日历 ----------
def draw_calendar(d, y):
    now = datetime.now(timezone(timedelta(hours=8)))
    year, month = now.year, now.month
    d.text((W // 2, y), "%d年%d月" % (year, month), font=load_font(40), fill=0, anchor="mm")
    y += 52
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    cell_w = 100
    start_x = (W - cell_w * 7) // 2
    wd_font = load_font(28)
    for i, wd in enumerate(weekdays):
        d.text((start_x + i * cell_w + cell_w // 2, y), wd, font=wd_font, fill=128, anchor="mm")
    y += 40
    cal = calendar.Calendar(firstweekday=0)
    days = list(cal.itermonthdays(year, month))
    day_font = load_font(32)
    cell_h = 48
    for idx, day in enumerate(days):
        if day == 0:
            continue
        row, col = idx // 7, idx % 7
        x = start_x + col * cell_w + cell_w // 2
        yy = y + row * cell_h + cell_h // 2
        if day == now.day:
            d.rectangle([x - 20, yy - 20, x + 20, yy + 20], fill=0)
            d.text((x, yy), str(day), font=day_font, fill=255, anchor="mm")
        else:
            d.text((x, yy), str(day), font=day_font, fill=0, anchor="mm")
    y += cell_h * 6 + 14
    return y


# ---------- 换行 ----------
def wrap_text(text, max_chars):
    out = []
    while len(text) > max_chars:
        out.append(text[:max_chars])
        text = text[max_chars:]
    out.append(text)
    return out if out else [""]


# ---------- 渲染 ----------
def render_png():
    notices = load_notices()
    now = datetime.now(timezone(timedelta(hours=8)))
    updated = now.strftime("%m-%d %H:%M")

    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    # 顶部标题
    d.rectangle([0, 0, W, 108], fill=0)
    d.text((W // 2, 42), "2506公告板", font=load_font(46), fill=255, anchor="mm")
    d.text((W // 2, 88), "更新：%s" % updated, font=load_font(20), fill=200, anchor="mm")

    y = 122
    # 日历（最上）
    y = draw_calendar(d, y)
    d.line([(30, y), (W - 30, y)], fill=180, width=2)
    y += 12

    # 天气（中间）
    weather = get_weather()
    if weather:
        d.text((W // 2, y), weather, font=load_font(40), fill=0, anchor="mm")
        y += 56
    else:
        y += 20
    d.line([(30, y), (W - 30, y)], fill=180, width=2)
    y += 12

    # 公告（最下）
    body_font = load_font(56)
    for notice in notices:
        lines = wrap_text(notice, 11)
        d.rectangle([40, y + 22, 56, y + 38], fill=0)
        d.text((70, y), lines[0], font=body_font, fill=0)
        y += 88
        for line in lines[1:]:
            d.text((70, y), line, font=body_font, fill=0)
            y += 88
        y += 28
        if y > H - 60:
            break

    d.text((W // 2, H - 25), "每 60 秒自动刷新", font=load_font(20), fill=160, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    png = render_png()
    with open(OUT_FILE, "wb") as f:
        f.write(png)
    print("OK: generated %s (%d bytes)" % (OUT_FILE, len(png)))
