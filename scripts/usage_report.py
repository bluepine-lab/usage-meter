# -*- coding: utf-8 -*-
"""使用量ログから、確定した数字だけを出す(感想や提案はAIが書く)。
使い方: python usage_report.py
見ているもの: 時間帯別・曜日別のコスト、モデル別の「7日枠1%あたりのコスト」、重かったセッション、キャッシュの割合。"""
import json, sys, pathlib, datetime as dt
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LOG = pathlib.Path.home() / ".claude" / "usage-meter" / "usage-log.jsonl"
if not LOG.exists():
    sys.exit("まだログがありません。")
rows = []
for line in LOG.read_text(encoding="utf-8-sig").splitlines():
    try:
        r = json.loads(line)
        r["_t"] = dt.datetime.fromisoformat(r["ts"])
        rows.append(r)
    except Exception:
        pass
rows.sort(key=lambda r: r["_t"])
if len(rows) < 2:
    sys.exit("記録が少なすぎます。もう少し使ってから、もう一度どうぞ。")

WD = "月火水木金土日"
def band(h): return "朝(5-11時)" if 5 <= h < 11 else "昼(11-17時)" if 11 <= h < 17 else "夜(17-23時)" if 17 <= h < 23 else "深夜(23-5時)"
def cost(r): return (r.get("cost") or {}).get("total_cost_usd")
def p7(r): return (r.get("seven_day") or {}).get("used_percentage")

by_band, by_wd, by_model = defaultdict(float), defaultdict(float), defaultdict(lambda: [0.0, 0.0])
for a, b in zip(rows, rows[1:]):
    if a.get("session") != b.get("session"):
        continue
    ca, cb = cost(a), cost(b)
    if None in (ca, cb) or cb < ca:
        continue
    d = cb - ca
    by_band[band(b["_t"].hour)] += d
    by_wd[WD[b["_t"].weekday()]] += d
    pa, pb = p7(a), p7(b)
    if None not in (pa, pb) and pb >= pa:
        m = b.get("model") or "不明"
        by_model[m][0] += d
        by_model[m][1] += pb - pa

days = (rows[-1]["_t"] - rows[0]["_t"]).total_seconds() / 86400
print(f"【使用量レポート】記録 {len(rows)} 件 / 期間 {rows[0]['_t']:%m/%d %H:%M} 〜 {rows[-1]['_t']:%m/%d %H:%M}(約{days:.1f}日分)")
if days < 3:
    print("※ 3日分に満たないので、傾向はまだ当てになりません。\n")

def table(title, d, order=None):
    tot = sum(d.values()) or 1
    print(f"\n■ {title}(コスト = API換算ドル)")
    for k in (order or sorted(d, key=d.get, reverse=True)):
        v = d.get(k, 0.0)
        print(f"  {k:<10} ${v:6.2f}  {v / tot * 100:4.0f}%  " + "█" * round(v / tot * 20))

table("時間帯別", by_band, ["朝(5-11時)", "昼(11-17時)", "夜(17-23時)", "深夜(23-5時)"])
table("曜日別", by_wd, [w for w in WD if w in by_wd])

print("\n■ モデル別 7日枠1%あたりのコスト")
any_m = False
for m, (c, p) in by_model.items():
    if p >= 3:
        print(f"  {m:<22} 約 ${c / p:.2f}/1%  (7日枠が計{p:.0f}%動いた分から算出)")
        any_m = True
if not any_m:
    print("  データ不足(7日枠が3%以上動いたモデルがまだありません)")

sess = {}
for r in rows:
    s = r.get("session")
    if s and cost(r) is not None:
        o = sess.setdefault(s, {"start": r["_t"], "model": r.get("model"), "max": 0.0, "lines": 0})
        o["max"] = max(o["max"], cost(r))
        o["lines"] = max(o["lines"], (r.get("cost") or {}).get("total_lines_added") or 0)
print("\n■ 重かったセッション上位5件")
for s, o in sorted(sess.items(), key=lambda kv: kv[1]["max"], reverse=True)[:5]:
    print(f"  {o['start']:%m/%d %H:%M}開始  ${o['max']:.2f}  追加{o['lines']}行  {o['model']}  ({s[:8]})")

hits = []
for r in rows:
    u = (r.get("context_window") or {}).get("current_usage") or {}
    tot = sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    if tot:
        hits.append(u.get("cache_read_input_tokens", 0) / tot)
if hits:
    print(f"\n■ キャッシュ読み取りの割合(平均) {sum(hits) / len(hits) * 100:.0f}%  (高いほど同じ作業が安く済む)")
print("\n※ %は整数、コストはAPI換算の目安です。スマホだけで使った分は入っていません。")
