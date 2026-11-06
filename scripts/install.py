# -*- coding: utf-8 -*-
"""使用量メーターを入れる/外す。設定ファイルは上書きせず、バックアップを取ってから足す。
使い方:
  python install.py            入れる(すでに別のステータスラインがあれば止まる)
  python install.py --force    すでにあるステータスラインを置き換える
  python install.py --uninstall  外す(ログは残す)
  python install.py --style line   グラフの種類を変える(line/block/square/dot/none)
"""
import json, shutil, sys, pathlib, datetime as dt

CLAUDE = pathlib.Path.home() / ".claude"
DEST = CLAUDE / "usage-meter"
SETTINGS = CLAUDE / "settings.json"
SRC = pathlib.Path(__file__).resolve().parent
FILES = ["statusline.py", "usage_warn.py", "usage_graph.py"]
MARK = "usage-meter"

py = pathlib.Path(sys.executable).as_posix()
cmd_status = f'"{py}" -X utf8 "{(DEST / "statusline.py").as_posix()}"'
cmd_warn = f'"{py}" -X utf8 "{(DEST / "usage_warn.py").as_posix()}"'


def load():
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
    return {}


def save(d):
    CLAUDE.mkdir(parents=True, exist_ok=True)
    if SETTINGS.exists():
        bk = SETTINGS.with_name(f"settings.json.bak-{dt.datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(SETTINGS, bk)
        print(f"バックアップ: {bk}")
    SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_hook(d):
    ups = d.get("hooks", {}).get("UserPromptSubmit", [])
    keep = [g for g in ups if not any(MARK in h.get("command", "") for h in g.get("hooks", []))]
    if keep:
        d["hooks"]["UserPromptSubmit"] = keep
    elif "hooks" in d:
        d["hooks"].pop("UserPromptSubmit", None)
        if not d["hooks"]:
            d.pop("hooks")


def uninstall():
    d = load()
    if MARK in d.get("statusLine", {}).get("command", ""):
        d.pop("statusLine")
    strip_hook(d)
    save(d)
    print("外しました。ログ(usage-meter フォルダ)は残してあります。再起動で反映されます。")


def set_style(name):
    """グラフの種類を config.json に書く(再起動なしで次の更新から反映)。"""
    if name not in ("line", "block", "square", "dot", "none"):
        sys.exit("style は line / block / square / dot / none のどれかです。")
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "config.json").write_text(json.dumps({"style": name}, ensure_ascii=False), encoding="utf-8")
    print(f"グラフの種類を {name} にしました。")


def install(force):
    d = load()
    cur = d.get("statusLine", {}).get("command", "")
    if cur and MARK not in cur and not force:
        print("すでに別のステータスラインが設定されています:\n  " + cur +
              "\n置き換えてよければ、本人に確認してから --force を付けて再実行してください。")
        sys.exit(2)
    DEST.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(SRC / f, DEST / f)
    d["statusLine"] = {"type": "command", "command": cmd_status}
    strip_hook(d)
    d.setdefault("hooks", {}).setdefault("UserPromptSubmit", []).append(
        {"hooks": [{"type": "command", "command": cmd_warn, "timeout": 5}]})
    save(d)
    print(f"入れました: {DEST}\nClaude Codeを再起動すると反映されます。")


if "--style" in sys.argv:
    set_style(sys.argv[sys.argv.index("--style") + 1])
elif "--uninstall" in sys.argv:
    uninstall()
else:
    install("--force" in sys.argv)
