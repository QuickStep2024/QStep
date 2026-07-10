# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import logging
import tkinter as tk

def patched_setup_notice_widgets(self):
    """[1.3.3 패치] 공지사항의 글자 크기를 18로 확대하고, 상하 분산배치하며 좌우 여백을 80px 주어 중앙정렬합니다."""
    # Title
    self.title_label = tk.Label(
        self.notice_frame, 
        text=f"퀵스텝 {self.config.get('지점명', '')}",
        font=("경기천년제목 Bold", 22, "bold"), 
        bg="#121212", 
        fg="#00BCD4",
        justify=tk.CENTER
    )
    self.title_label.pack(pady=(12, 5), padx=10, fill="x")

    # Entries Frame
    self.entries_frame = tk.Frame(self.notice_frame, bg="#1E1E1E")
    self.entries_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    # Load notices from config
    notices_str = [self.config.get(f'notice{i}', '') for i in range(1, 6)]

    for i, notice_entry_str in enumerate(notices_str):
        if not notice_entry_str.strip():
            continue

        entry_item_frame = tk.Frame(self.entries_frame, bg="#1E1E1E")
        entry_item_frame.pack(fill="x", expand=True, anchor="w", padx=(80, 80))

        title_text, description_text = "", ""
        if ":" in notice_entry_str:
            parts = notice_entry_str.split(":", 1)
            title_text = parts[0].strip()
            description_text = parts[1].strip()
        else:
            title_text = notice_entry_str.strip()

        line_frame = tk.Frame(entry_item_frame, bg="#1E1E1E")
        line_frame.pack(fill="x", anchor="w")

        actual_title_label = tk.Label(
            line_frame, 
            text=title_text,
            font=("맑은 고딕", 18, "bold"),
            bg="#1E1E1E", 
            fg="#FFEB3B",
            anchor="nw", 
            justify="left"
        )
        actual_title_label.pack(side=tk.LEFT, anchor="nw")

        if description_text:
            colon_label = tk.Label(
                line_frame, 
                text=": ",
                font=("맑은 고딕", 18, "bold"),
                bg="#1E1E1E", 
                fg="#FFEB3B",
                anchor="nw", 
                justify="left"
            )
            colon_label.pack(side=tk.LEFT, anchor="nw")

            desc_label = tk.Label(
                line_frame, 
                text=description_text,
                font=("맑은 고딕", 18, "bold"),
                bg="#1E1E1E", 
                fg="#E0E0E0",
                anchor="nw", 
                justify="left",
                wraplength=self.width - 200
            )
            desc_label.pack(side=tk.LEFT, anchor="nw", fill=tk.X, expand=True, padx=(3, 0))

def apply_patch(main_win):
    """런타임 핫패치 진입점:
    - [1.3.3 패치] 공지사항 레이아웃 및 여백/폰트 크기 교정 주입
    """
    logging.info("[핫패치] active_patch.py 로딩 및 실행 시작...")

    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    current_ver_str = getattr(quickstep_mod, "CURRENT_VERSION", "1.0.0")
    try:
        ver_parts = [int(x) for x in current_ver_str.split(".")]
    except Exception as e:
        logging.warning(f"[핫패치] 버전 확인 중 예외 발생: {e}")
        ver_parts = [1, 0, 0]

    # 6. InstagramApp 공지사항 글자 크기 및 위치 교정 핫패치 (v1.3.3 이하 버전에 모두 적용)
    if ver_parts <= [1, 3, 3]:
        try:
            import instagram_app
            instagram_app.InstagramApp.setup_notice_widgets = patched_setup_notice_widgets
            logging.info("[핫패치] InstagramApp 공지사항 글자 크기 및 위치 교정 핫픽스 패치 완료.")
        except Exception as ex_insta_hot:
            logging.error(f"[핫패치] InstagramApp 공지사항 핫픽스 주입 중 오류 발생: {ex_insta_hot}", exc_info=True)

    logging.info("[핫패치] 원격 핫패치가 실시간으로 메모리에 주입되었습니다. 🔥")
