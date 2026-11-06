# -*- coding: utf-8 -*-
"""メッセージ送信のたびに呼ばれ、基準を超えた時だけ警告を出す(標準出力がAIに渡る)。
同じ段階では繰り返さず、段階が変わった時だけ出す。

基準を変えたい時は、下の3行の数字を直す。"""
import json, time, pathlib, sys, datetime

HARD = 80          # この%以上で「上限が近い」警告
PACE_GAP = {"5時間枠": 25, "7日枠": 15}   # 期間の経過より何ポイント先行したら警告するか
PACE_MIN = 30      # 先行警告は、使用量がこの%以上の時だけ

HOME = pathlib.Path.home() / ".claude" / "usage-meter"
log, state = HOME / "usage-log.jsonl", HOME / "warn.state"
try:
    last = json.loads(log.read_text(encoding="utf-8-sig").strip().splitlines()[-1])
except Exception:
    sys.exit(0)

now = time.time()
msgs, key = [], []


WD = "月火水木金土日"


def when(ts):
    """時刻を「今日の夜」「金曜の深夜」のように、曜日と時間帯(朝・昼・夜・深夜)で言う。"""
    t = datetime.datetime.fromtimestamp(ts)
    h = t.hour
    band = "朝" if 5 <= h < 11 else "昼" if 11 <= h < 17 else "夜" if 17 <= h < 23 else "深夜"
    days = (t.date() - datetime.date.today()).days
    day = "今日" if days == 0 else "明日" if days == 1 else f"{WD[t.weekday()]}曜"
    return f"{day}の{band}"


def check(name, d, span_h):
    if not d or d.get("used_percentage") is None or d.get("resets_at", 0) < now:
        return
    used, rs = d["used_percentage"], d["resets_at"]
    elapsed = (1 - (rs - now) / (span_h * 3600)) * 100
    # 予測: 期間の10%以上たってから、今のペースで使い切る時刻を曜日と時間帯で言う
    proj = ""
    if elapsed >= 10 and used > 0:
        out = now + (100 - used) / (used / (now - (rs - span_h * 3600)))
        proj = (f"このペースだと{when(out)}に使い切る見込み。" if out < rs
                else "このペースならリセットまで持つ見込み。")
    reset = f"リセットは{when(rs)}。"
    if used >= HARD:
        msgs.append(f"{name}は上限が近い。{proj}{reset}")
        key.append(f"{name}H{int(used // 10)}")
    elif used >= PACE_MIN and used > elapsed + PACE_GAP[name]:
        msgs.append(f"{name}は期間の経過より使いすぎ。{proj}{reset}")
        key.append(f"{name}P{int(used // 10)}")


check("5時間枠", last.get("five_hour"), 5)
check("7日枠", last.get("seven_day"), 168)

k = ",".join(key)
prev = state.read_text(encoding="utf-8") if state.exists() else ""
if k != prev:
    state.write_text(k, encoding="utf-8")
    if msgs:
        print("【使用量警告】" + " ".join(msgs) +
              " 返答の冒頭で一言ユーザーに伝え、重い作業(大量の調査・同時にたくさんの作業)は始める前に確認すること。")
