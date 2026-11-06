# -*- coding: utf-8 -*-
"""使用量ログから、メーターと推移グラフのHTMLを作ってブラウザで開く。
使い方: python usage_graph.py [--no-open]"""
import json, datetime as dt, pathlib, sys, webbrowser

HOME = pathlib.Path.home() / ".claude" / "usage-meter"
LOG = HOME / "usage-log.jsonl"
OUT = HOME / "usage-graph.html"

if not LOG.exists():
    sys.exit("まだログがありません。ステータスラインが動いて少し使うと貯まり始めます。")
rows = []
for line in LOG.read_text(encoding="utf-8-sig").splitlines():
    try:
        r = json.loads(line)
        r["_t"] = dt.datetime.fromisoformat(r["ts"])
        rows.append(r)
    except Exception:
        pass
if not rows:
    sys.exit("ログが空です。")
rows.sort(key=lambda r: r["_t"])
last = rows[-1]


def pct(r, k): return (r.get(k) or {}).get("used_percentage")


def reset(r, k):
    v = (r.get(k) or {}).get("resets_at")
    return dt.datetime.fromtimestamp(v).strftime("%m/%d %H:%M") if v else "-"


# 推定: 同じセッション内で、コストの増え方 ÷ 7日枠%の増え方
dcost = dpct = 0.0
for a, b in zip(rows, rows[1:]):
    if a.get("session") != b.get("session"):
        continue
    pa, pb = pct(a, "seven_day"), pct(b, "seven_day")
    ca = (a.get("cost") or {}).get("total_cost_usd")
    cb = (b.get("cost") or {}).get("total_cost_usd")
    if None in (pa, pb, ca, cb) or pb < pa or cb < ca:
        continue
    dcost += cb - ca
    dpct += pb - pa
if dpct >= 3:
    per, left = dcost / dpct, 100 - (pct(last, "seven_day") or 0)
    est = f"7日枠の1%あたり約 ${per:.2f} 相当(API換算)。残り{left:.0f}%は約 ${per * left:.1f} 分。"
else:
    est = f"データ不足(7日枠が合計{dpct:.0f}%しか動いていません。3%以上動くと推定が出ます)。"

W, H, L, R, T, B = 760, 280, 44, 16, 16, 40
t0, t1 = rows[0]["_t"], rows[-1]["_t"]
span = max((t1 - t0).total_seconds(), 1)


def X(t): return L + (t - t0).total_seconds() / span * (W - L - R)
def Y(p): return T + (100 - p) / 100 * (H - T - B)


def path(k):
    pts = [(X(r["_t"]), Y(pct(r, k))) for r in rows if pct(r, k) is not None]
    return " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))


grid = "".join(f'<line x1="{L}" x2="{W-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="g"/>'
               f'<text x="{L-6}" y="{Y(v)+4:.1f}" text-anchor="end" class="ax">{v}%</text>'
               for v in (0, 25, 50, 75, 100))
xl = "".join(f'<text x="{X(t0 + (t1 - t0) * i / 4):.1f}" y="{H-14}" text-anchor="middle" class="ax">'
             f'{(t0 + (t1 - t0) * i / 4).strftime("%m/%d %H:%M")}</text>' for i in range(5))


def gauge(label, k, color):
    p = pct(last, k) or 0
    return (f'<div class="card"><div class="lab">{label}</div><div class="big">{p:.0f}%</div>'
            f'<div class="bar"><i style="width:{p}%;background:var({color})"></i></div>'
            f'<div class="sub">リセット {reset(last, k)}</div></div>')


html = f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>使用量グラフ</title>
<style>
:root{{--bg:#fff;--fg:#1b2430;--mut:#6b7684;--card:#f3f5f8;--c1:#e8590c;--c2:#1c64f2;--grid:#dde2e8}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12161c;--fg:#e6eaf0;--mut:#9aa5b1;--card:#1c222b;--c1:#ff8a3d;--c2:#6ea0ff;--grid:#2c3440}}}}
body{{margin:0;padding:20px 16px;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"Yu Gothic",sans-serif;max-width:800px;margin:auto}}
h1{{font-size:20px;margin:0 0 12px}}.row{{display:flex;gap:12px;flex-wrap:wrap}}
.card{{flex:1;min-width:220px;background:var(--card);border-radius:12px;padding:14px 16px}}
.lab{{color:var(--mut);font-size:13px}}.big{{font-size:36px;font-weight:700}}
.bar{{height:10px;background:var(--grid);border-radius:5px;overflow:hidden}}.bar i{{display:block;height:100%}}
.sub{{color:var(--mut);font-size:13px;margin-top:6px}}svg{{width:100%;height:auto;margin-top:16px}}
.g{{stroke:var(--grid)}}.ax{{fill:var(--mut);font-size:11px}}.note{{background:var(--card);border-radius:12px;padding:12px 16px;margin-top:16px}}
.leg span{{margin-right:16px;font-size:13px}}
</style>
<h1>Claude 使用量</h1>
<div class="row">{gauge("5時間枠", "five_hour", "--c1")}{gauge("7日枠", "seven_day", "--c2")}</div>
<div class="leg" style="margin-top:16px"><span style="color:var(--c1)">━ 5時間枠</span><span style="color:var(--c2)">━ 7日枠</span></div>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="使用量の推移">{grid}{xl}
<path d="{path('five_hour')}" fill="none" stroke="var(--c1)" stroke-width="2"/>
<path d="{path('seven_day')}" fill="none" stroke="var(--c2)" stroke-width="2"/></svg>
<div class="note"><b>消費の推定</b><br>{est}<br>
<span class="sub">%は整数表示のため粗い目安です。トークン数は取れないため、コストの増え方で代用しています。最終更新 {last['_t'].strftime('%m/%d %H:%M')}(記録 {len(rows)} 件)</span></div>
</html>"""

OUT.write_text(html, encoding="utf-8")
print(OUT)
if "--no-open" not in sys.argv:
    webbrowser.open(OUT.as_uri())
