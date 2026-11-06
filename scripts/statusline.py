# -*- coding: utf-8 -*-
"""ステータスライン: 5時間枠・7日枠・会話の長さを棒グラフで出し、値が変わった時だけログに1行足す。
Claude Codeが標準入力にJSONを渡して呼ぶ。標準ライブラリだけで動く。"""
import json, sys, time, pathlib, datetime as dt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = pathlib.Path.home() / ".claude" / "usage-meter"


# グラフの種類(config.json の "style" で選ぶ)。none は数字だけ。
STYLES = {
    "line": ("━", "─"),    # 細い線(初期設定)
    "block": ("█", "░"),   # 太いブロック
    "square": ("▰", "▱"),  # 四角
    "dot": ("●", "○"),     # 丸
    "none": None,          # グラフなし(数字だけ)
}


def style():
    try:
        s = json.loads((HOME / "config.json").read_text(encoding="utf-8-sig")).get("style", "line")
        return s if s in STYLES else "line"
    except Exception:
        return "line"


def bar(p):
    chars = STYLES[style()]
    if chars is None:
        return ""
    n = max(0, min(10, round(float(p) / 10)))
    return chars[0] * n + chars[1] * (10 - n)


def col(p, s):
    """80%以上はオレンジ、90%以上は赤にする(端末の色コード)。"""
    if p >= 90:
        return f"\x1b[31m{s}\x1b[0m"
    if p >= 80:
        return f"\x1b[38;5;208m{s}\x1b[0m"
    return f"\x1b[90m{s}\x1b[0m"   # ふだんは控えめな灰色


def fmt(label, w):
    if not w or w.get("used_percentage") is None:
        return None
    p = w["used_percentage"]
    s = " ".join(x for x in (label, bar(p), f"{round(p)}%") if x)
    if w.get("resets_at"):
        t = dt.datetime.fromtimestamp(w["resets_at"])
        s += f" (~{t.month}/{t.day} {t:%H:%M})"
    return col(p, s)


def log(j):
    try:
        rl, cw = j.get("rate_limits"), j.get("context_window") or {}
        if not rl:
            return
        HOME.mkdir(parents=True, exist_ok=True)
        key = "|".join(str(x) for x in (
            (rl.get("five_hour") or {}).get("used_percentage"),
            (rl.get("seven_day") or {}).get("used_percentage"),
            cw.get("total_input_tokens"), cw.get("total_output_tokens"), j.get("session_id")))
        st = HOME / "log.last"
        if st.exists() and st.read_text(encoding="utf-8") == key:
            return
        rec = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "session": j.get("session_id"), "model": (j.get("model") or {}).get("id"),
               "five_hour": rl.get("five_hour"), "seven_day": rl.get("seven_day"),
               "context_window": cw, "cost": j.get("cost")}
        with open(HOME / "usage-log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        st.write_text(key, encoding="utf-8")
    except Exception:
        pass


def main():
    try:
        j = json.loads(sys.stdin.read())
    except Exception:
        return
    parts = []
    name = (j.get("model") or {}).get("display_name")
    if name:
        parts.append(name)
    rl = j.get("rate_limits") or {}
    for label, k in (("5h", "five_hour"), ("7d", "seven_day")):
        s = fmt(label, rl.get(k))
        if s:
            parts.append(s)
    cp = (j.get("context_window") or {}).get("used_percentage")
    if cp is not None:
        parts.append(col(cp, " ".join(x for x in ("ctx", bar(cp), f"{round(cp)}%") if x)))
    print(" | ".join(parts))
    log(j)


main()
