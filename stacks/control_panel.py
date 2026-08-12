#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stacks 操作用 GUI（ダブルクリック想定）
セットアップ / 開始 / 停止 / ログ / モード切替機能トグル
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

STACKS_DIR = Path(__file__).resolve().parent
EXPECTED_DIR = Path.home() / "Desktop" / "stacks"

# 同じフォルダの mode_switch_settings を優先
if str(STACKS_DIR) not in sys.path:
    sys.path.insert(0, str(STACKS_DIR))

from mode_switch_settings import (  # noqa: E402
    read_enable_mode_switch,
    write_enable_mode_switch,
)


def run_cmd(args: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(STACKS_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 1, "タイムアウトしました。"
    except Exception as exc:  # noqa: BLE001
        return 1, f"実行エラー: {exc}"


def run_bash_script(name: str) -> tuple[int, str]:
    script = STACKS_DIR / name
    if not script.is_file():
        return 1, f"{name} が見つかりません: {script}"
    return run_cmd(["bash", str(script)])


class ControlPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("stacks 制御パネル")
        self.geometry("780x560")
        self.minsize(600, 420)

        warn = ""
        if STACKS_DIR != EXPECTED_DIR:
            warn = f"※ 想定場所は {EXPECTED_DIR} です（現在: {STACKS_DIR}）\n"

        header = tk.Label(
            self,
            text=warn + "ボタンを押すだけで操作できます（コマンド不要）",
            justify="left",
            anchor="w",
        )
        header.pack(fill="x", padx=12, pady=(12, 4))

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=12, pady=8)

        buttons = [
            ("① 初回セットアップ", self.do_setup, "#1b6ca8"),
            ("② 開始（start）", self.do_start, "#2e7d32"),
            ("③ 停止（stop）", self.do_stop, "#c62828"),
            ("④ 状態・ログを見る", self.do_logs, "#6a1b9a"),
        ]
        for i, (label, cmd, color) in enumerate(buttons):
            b = tk.Button(
                btn_frame,
                text=label,
                command=cmd,
                height=2,
                bg=color,
                fg="white",
                activebackground=color,
                font=("Sans", 11, "bold"),
            )
            b.grid(row=0, column=i, sticky="ew", padx=4)
            btn_frame.columnconfigure(i, weight=1)

        mode_frame = tk.Frame(self)
        mode_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.mode_btn = tk.Button(
            mode_frame,
            text=self._mode_button_label(),
            command=self.do_toggle_mode_switch,
            height=2,
            bg="#ef6c00",
            fg="white",
            activebackground="#ef6c00",
            font=("Sans", 11, "bold"),
        )
        self.mode_btn.pack(fill="x")

        self.status = tk.Label(self, text="準備完了", anchor="w")
        self.status.pack(fill="x", padx=12)

        self.log = scrolledtext.ScrolledText(self, wrap="word", height=20)
        self.log.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self._append(
            "この画面の使い方:\n"
            "・初めてそのラズパイに入れるとき → ① セットアップ\n"
            "・一時停止したいとき → ③ 停止\n"
            "・また動かしたいとき → ② 開始\n"
            "・おかしいとき → ④ ログ\n"
            "・黄ボタンの 3枚/2枚 切替機能を使うとき → ⑤（下のオレンジボタン）\n"
            "・本体の監視開始は、機械のボタン①です（この画面とは別）\n"
        )

    def _mode_button_label(self) -> str:
        on = read_enable_mode_switch(STACKS_DIR)
        state = "有効" if on else "無効"
        return f"⑤ モード切替機能: いま{state}（押すと切替）"

    def _refresh_mode_button(self) -> None:
        self.mode_btn.config(text=self._mode_button_label())

    def _append(self, text: str) -> None:
        self.log.insert("end", text.rstrip() + "\n\n")
        self.log.see("end")
        self.update_idletasks()

    def _set_busy(self, msg: str) -> None:
        self.status.config(text=msg)
        self.update_idletasks()

    def _run_and_show(self, title: str, script_name: str) -> None:
        if not messagebox.askokcancel("確認", f"{title} を実行しますか？"):
            return
        self._set_busy(f"{title} を実行中...")
        code, out = run_bash_script(script_name)
        self._append(f"===== {title} =====\n{out or '(出力なし)'}\n終了コード: {code}")
        self._set_busy("完了" if code == 0 else "エラーがありました（下のログを確認）")
        if code != 0:
            messagebox.showerror("エラー", f"{title} に失敗しました。\n下のログを確認してください。")
        else:
            messagebox.showinfo("完了", f"{title} が完了しました。")

    def do_setup(self) -> None:
        self._run_and_show("初回セットアップ", "setup.sh")

    def do_start(self) -> None:
        self._run_and_show("開始", "start.sh")

    def do_stop(self) -> None:
        self._run_and_show("停止", "stop.sh")

    def do_logs(self) -> None:
        self._set_busy("ログ取得中...")
        code, out = run_bash_script("show-logs.sh")
        self._append(f"===== 状態・ログ =====\n{out or '(出力なし)'}\n終了コード: {code}")
        self._set_busy("ログ表示完了")

    def do_toggle_mode_switch(self) -> None:
        current = read_enable_mode_switch(STACKS_DIR)
        new_value = not current
        new_label = "有効" if new_value else "無効"
        msg = (
            "機械は停止していますか？\n\n"
            f"モード切替機能を「{new_label}」に変更します。\n"
            "枚数検知プロセスをいったん停止し、設定反映のため再起動します。\n"
            "（ラズパイ本体の再起動は不要です）\n\n"
            "続行しますか？"
        )
        if not messagebox.askokcancel("モード切替機能の変更", msg):
            return

        self._set_busy(f"モード切替機能を {new_label} に変更中...")
        try:
            path = write_enable_mode_switch(new_value, STACKS_DIR)
        except OSError as exc:
            messagebox.showerror("エラー", f"設定ファイルを書けませんでした:\n{exc}")
            self._set_busy("エラー")
            return

        code, out = run_cmd(["sudo", "systemctl", "restart", "stacks.service"])
        self._append(
            f"===== モード切替機能 → {new_label} =====\n"
            f"conf: {path}\n{out or '(出力なし)'}\n"
            f"restart 終了コード: {code}"
        )
        self._refresh_mode_button()
        if code != 0:
            messagebox.showerror(
                "エラー",
                "設定は書き込みましたが、サービス再起動に失敗した可能性があります。\n"
                "④ ログで状態を確認するか、① セットアップ後にもう一度試してください。",
            )
            self._set_busy("再起動エラー（設定は保存済み）")
            return

        messagebox.showinfo(
            "完了",
            f"モード切替機能を「{new_label}」にしました。\n"
            "プロセスを再起動済みです。\n"
            "監視開始は機械のボタン①です。",
        )
        self._set_busy(f"モード切替機能: {new_label}")


def main() -> None:
    app = ControlPanel()
    app.mainloop()


if __name__ == "__main__":
    main()
