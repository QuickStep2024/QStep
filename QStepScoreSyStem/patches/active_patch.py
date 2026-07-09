# -*- coding: utf-8 -*-
"""
QStep Runtime Hot-patch v1.2.8
- [1.2.8 핫픽스] MainWindow.closeEvent 내 중복 'import os'로 인한 UnboundLocalError 원천 해결
"""

import sys
import os
import types
import logging
from datetime import datetime
from queue import Queue
from PIL import Image, ImageDraw, ImageFont, ImageTk

def patched_close_event(self, event):
    """메인 윈도우가 닫힐 때 호출되는 이벤트 핸들러. 종료 확인 및 정리 작업을 수행합니다.
    [1.2.8 패치] UnboundLocalError: local variable 'os' referenced before assignment 오류를 원천 픽스함.
    """
    import sys
    import os
    import subprocess
    from PyQt5.QtWidgets import QMessageBox
    from datetime import datetime
    from queue import Queue

    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    
    # 모듈 객체로부터 전역 변수 및 헬퍼 함수 가져오기
    shutdown_event = getattr(quickstep_mod, 'shutdown_event', None)
    data_processing_queue = getattr(quickstep_mod, 'data_processing_queue', None)
    original_stdout = getattr(quickstep_mod, 'original_stdout', None)
    original_stderr = getattr(quickstep_mod, 'original_stderr', None)
    StreamRedirector = getattr(quickstep_mod, 'StreamRedirector', None)
    resource_path = getattr(quickstep_mod, 'resource_path', lambda x: x)
    cleanup_fonts = getattr(quickstep_mod, 'cleanup_fonts', lambda: None)

    # 업데이트 다운로드 중이면 취소
    if self.update_downloader:
        self.update_downloader.cancel()

    if getattr(self, '_force_close', False) or getattr(self, 'is_updating', False):
        reply = QMessageBox.Yes
    else:
        reply = QMessageBox.question(self, '종료 확인',
                                     "프로그램을 종료하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No,  # 예/아니오 버튼
                                     QMessageBox.No)  # 기본 선택 '아니오'
    if reply == QMessageBox.Yes:  # '예'를 선택한 경우
        import logging
        logging.info("애플리케이션 종료 절차 시작...")
        if self.queue_window:
            try:
                self.queue_window._force_close = True
                self.queue_window.close()
            except Exception:
                pass
        self.save_window_settings()  # 현재 창 설정 저장 (CCTV 가시성 제외)

        if shutdown_event:
            shutdown_event.set()  # 모든 스레드에 종료 신호 전송

        # 무결성 검사 워커 종료
        if hasattr(self, 'integrity_worker'):
            self.integrity_worker.stop()
            
        # 실시간 동기화 워커 종료
        if hasattr(self, 'realtime_sync_worker'):
            self.realtime_sync_worker.stop()

        # 하이퍼랩스 스레드 풀 정리
        logging.info("하이퍼랩스 스레드 풀 정리 시작...")
        self.hyperlapse_thread_pool.clear()  # 큐에 대기 중인 작업 취소
        self.hyperlapse_thread_pool.waitForDone()  # 현재 실행 중인 작업 완료 대기
        logging.info("하이퍼랩스 스레드 풀 정리 완료.")

        # Tkinter GUI 종료 요청
        if hasattr(self, 'tk_root_window') and self.tk_root_window:
            try:
                if self.tk_root_window.winfo_exists():  # Tkinter 윈도우가 아직 존재하면
                    # Tkinter 스레드에서 안전하게 종료하기 위해 after 사용
                    self.tk_root_window.after(0, self.tk_root_window.quit)
            except Exception as e_tk_quit:
                logging.error(f"Tkinter 종료(quit) 요청 중 오류: {e_tk_quit}", exc_info=True)
                # after 실패 시 직접 호출 시도 (폴백)
                try:
                    self.tk_root_window.quit()
                except:
                    pass

        # Tkinter 스레드 완료 대기 (타임아웃 설정)
        if hasattr(self, 'tk_thread') and self.tk_thread.is_alive():
            logging.info("Tkinter 스레드 완료 대기 중 (최대 5초)...")
            self.tk_thread.join(timeout=5.0)
            if self.tk_thread.is_alive():
                logging.warning("Tkinter 스레드가 지정된 시간 내에 완료되지 않았습니다.")
            else:
                logging.info("Tkinter 스레드 정상적으로 완료됨.")

        # 폰트 리소스 강제 정리 (안전장치)
        cleanup_fonts()

        # 내부 데이터 처리 큐에 종료 신호(None) 전송
        if data_processing_queue and isinstance(data_processing_queue, Queue):
            try:
                data_processing_queue.put_nowait(None)  # 큐가 꽉 찼을 때 블로킹되지 않도록 nowait 사용
            except Exception as e_queue_put_none:
                logging.warning(f"closeEvent에서 내부 큐에 종료 신호(None) 추가 중 오류: {e_queue_put_none}")

        # Qt 종료 전 로깅 리소스 정리 (핸들러 제거, 스트림 복원)
        logging.info("종료 준비: Qt 의존 로깅 핸들러 제거 및 표준 스트림 복원 시도.")

        # QtLogHandler 제거
        if self.log_console_widget and hasattr(self.log_console_widget, 'log_handler'):
            log_handler_to_remove = self.log_console_widget.log_handler
            if log_handler_to_remove:
                logging.getLogger().removeHandler(log_handler_to_remove)
                if hasattr(log_handler_to_remove, 'flush'):
                    try:
                        log_handler_to_remove.flush()
                    except:
                        pass  # 플러시 오류 무시
                logging.info("루트 로거에서 QtLogHandler가 성공적으로 제거되었습니다.")
                self.log_console_widget.log_handler = None  # 참조 제거

        # sys.stdout, sys.stderr 원본으로 복원
        if StreamRedirector and isinstance(sys.stdout, StreamRedirector):
            if hasattr(sys.stdout, 'flush'): sys.stdout.flush()
            sys.stdout = original_stdout  # 원본 stdout으로 복원
            logging.info("sys.stdout이 원본 스트림으로 복원되었습니다.")
        if StreamRedirector and isinstance(sys.stderr, StreamRedirector):
            if hasattr(sys.stderr, 'flush'): sys.stderr.flush()
            sys.stderr = original_stderr  # 원본 stderr으로 복원
            logging.info("sys.stderr이 원본 스트림으로 복원되었습니다.")

        # 파이썬 로깅 시스템 명시적 종료 (파일 핸들러 등 닫기)
        logging.shutdown()
        # logging.shutdown() 이후에는 logging 사용 불가 (아래 로그는 파일에 안 써질 수 있음)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Python 로깅 시스템 명시적 종료 호출됨 (콘솔 출력).")

        logging.info("애플리케이션 종료 작업 거의 완료. Qt 애플리케이션 종료 이벤트 수락.")
        event.accept()  # PyQt 종료 이벤트 수락
        
        # 대기 중인 종료 후 업데이트가 있으면 프로세스 종료 직전에 실행 (파일 락 현상 원천 방지)
        if getattr(self, "pending_update_path", None):
            logging.info(f"종료 후 업데이트 적용 시작: {self.pending_update_path}")
            updater_src = resource_path("updater.exe")
            if os.path.exists(updater_src):
                updater_path = updater_src
                current_executable = sys.executable
                pid = os.getpid()
                args = [str(self.pending_update_path), str(current_executable), str(pid)]
                try:
                    creation_flags = 0
                    if sys.platform == 'win32':
                        creation_flags = subprocess.CREATE_NEW_CONSOLE
                    
                    # 폰트 리소스 해제
                    cleanup_fonts()
                    
                    subprocess.Popen([updater_path] + args, creationflags=creation_flags)
                    print(f"종료 후 업데이터 실행 성공: {updater_path} {' '.join(args)}")
                except Exception as e_run_up:
                    print(f"종료 후 업데이터 실행 실패: {e_run_up}")

        os._exit(0)
    else:  # '아니오'를 선택한 경우
        event.ignore()  # 종료 이벤트 무시


# ==========================================
# 1.2.8 Emoji Hotfix Helper Functions
# ==========================================

def resource_path(relative_path):
    """실행 환경(개발/배포)에 맞는 리소스 절대 경로를 반환합니다."""
    import sys
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def patched_draw_text_with_emojis(draw, position, text, font, emoji_font, fill, image=None):
    """이모지가 포함된 텍스트를 그립니다."""
    x, y = position
    
    # Get regular font's .notdef size using a high-range emoji
    try:
        regular_notdef_size = font.getmask("🔥").size
    except Exception:
        regular_notdef_size = None

    # Get typical line height for alignment
    try:
        ref_bbox = draw.textbbox((0, 0), "가", font=font)
        line_h = ref_bbox[3] - ref_bbox[1]
    except Exception:
        line_h = font.size if hasattr(font, 'size') else 32

    # Load fallback system emoji font (Segoe UI Emoji) in case NotoColorEmoji fails to render
    fallback_emoji_font = None
    try:
        segoe_path = "C:\\Windows\\Fonts\\seguiemj.ttf"
        if os.path.exists(segoe_path):
            fallback_emoji_font = ImageFont.truetype(segoe_path, int(line_h))
    except Exception:
        pass

    for char in text:
        c_ord = ord(char)
        
        # 1. Fast path for standard alphanumeric, Hangul, and spaces (always non-emoji)
        if (0x0020 <= c_ord <= 0x007E) or (0x3130 <= c_ord <= 0x318F) or (0xAC00 <= c_ord <= 0xD7AF):
            is_emoji = False
        else:
            # 2. Check font support dynamically using regular font's .notdef size
            if regular_notdef_size is not None:
                try:
                    char_mask_size = font.getmask(char).size
                    # If its mask size is the same as the .notdef size, it means it is NOT supported by the regular font,
                    # so it should be rendered with the emoji font.
                    is_emoji = (char_mask_size == regular_notdef_size)
                except Exception:
                    is_emoji = True
            else:
                # Fallback to standard check if regular_notdef_size is not available
                is_emoji = c_ord > 0xFFFF or 0x2600 <= c_ord <= 0x27BF

        if not is_emoji:
            # Draw standard character
            draw.text((x, y), char, font=font, fill=fill)
            bbox = draw.textbbox((0, 0), char, font=font)
            char_w = bbox[2] - bbox[0]
            x += char_w
        else:
            # Render color emoji
            drawn_via_fallback = False
            if image is not None:
                try:
                    # 1. Draw on temporary transparent canvas
                    temp_sz = 200
                    temp_img = Image.new("RGBA", (temp_sz, temp_sz), (0, 0, 0, 0))
                    temp_draw = ImageDraw.Draw(temp_img)
                    
                    # Draw with NotoColorEmoji size 109
                    temp_draw.text((10, 10), char, font=emoji_font, fill=None, embedded_color=True)
                    
                    # 2. Crop tightly
                    crop_bbox = temp_img.getbbox()
                    if crop_bbox is not None:
                        cropped = temp_img.crop(crop_bbox)
                        crop_w = crop_bbox[2] - crop_bbox[0]
                        crop_h = crop_bbox[3] - crop_bbox[1]
                        
                        # 3. Scale to fit regular font height
                        target_h = int(line_h * 1.1)  # Slightly larger for better visibility
                        target_w = int(crop_w * (target_h / crop_h))
                        
                        scaled_emoji = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
                        
                        # 4. Paste inline
                        y_offset = int((line_h - target_h) / 2)
                        image.paste(scaled_emoji, (int(x), int(y + y_offset)), scaled_emoji)
                        
                        x += target_w
                        drawn_via_fallback = True
                except Exception:
                    pass
            
            if not drawn_via_fallback:
                # Fallback to Segoe UI Emoji or regular font
                fallback_font = fallback_emoji_font if fallback_emoji_font is not None else font
                draw.text((x, y), char, font=fallback_font, fill=fill)
                bbox = draw.textbbox((0, 0), char, font=fallback_font)
                char_w = bbox[2] - bbox[0]
                x += char_w


def get_inducted_teams_for_room(room_size):
    try:
        import sys
        quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
        db_app = getattr(quickstep_mod, 'AllData_app', None)
        config = getattr(quickstep_mod, 'config', None)
        if not config:
            try:
                from data_handler import read_config
                config = read_config('config.cfg')
            except Exception:
                config = {}
                
        from hall_of_fame import HallOfFameManager, NicknameAliasManager
        hof_manager = HallOfFameManager(db_app, config)
        alias_manager = NicknameAliasManager(db_app, config)
        inducted = hof_manager.get_inducted_teams(room_size, alias_manager)
        return {t["primary_nickname"].strip().lower() for t in inducted}, alias_manager
    except Exception as e:
        logging.error(f"Error getting inducted teams for room {room_size}: {e}")
        return set(), None


def generate_trophy_image(app):
    # Generates a PIL image of size (45, 32) containing both the 🏆 emoji and the ★ star side-by-side
    try:
        emoji_font = getattr(app, 'pil_font_emoji', None)
        if emoji_font is None:
            font_path_emoji = resource_path(os.path.join("fonts", "NotoColorEmoji-Regular.ttf"))
            if not os.path.exists(font_path_emoji):
                font_path_emoji = "arial.ttf"
            emoji_font = ImageFont.truetype(font_path_emoji, 109)
            
        font_path_bold = resource_path(os.path.join("fonts", "경기천년제목_Bold.ttf"))
        if not os.path.exists(font_path_bold):
            font_path_bold = "arial.ttf"
        star_font = ImageFont.truetype(font_path_bold, 16)
        
        temp_img = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((10, 10), "🏆", font=emoji_font, fill=None, embedded_color=True)
        
        crop_bbox = temp_img.getbbox()
        if crop_bbox is not None:
            cropped = temp_img.crop(crop_bbox)
            crop_w = crop_bbox[2] - crop_bbox[0]
            crop_h = crop_bbox[3] - crop_bbox[1]
            
            target_h = 26
            target_w = int(crop_w * (target_h / crop_h))
            
            scaled_emoji = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            final_img = Image.new("RGBA", (45, 32), (0, 0, 0, 0))
            # Paste trophy at x=0
            final_img.paste(scaled_emoji, (0, 3), scaled_emoji)
            
            # Draw ★ right next to it in gold (size 16)
            final_draw = ImageDraw.Draw(final_img)
            final_draw.text((27, 7), "★", font=star_font, fill=(255, 215, 0, 255))
            
            return ImageTk.PhotoImage(final_img)
    except Exception as e:
        logging.error(f"Error generating dynamic trophy-star image: {e}")
    return ""


def patched_generate_scoreboard_image(year, month, room_size_name, max_rank, ratio, data, output_path, start_rank=1):
    """
    PIL을 사용하여 점수판 이미지를 생성합니다.
    ratio: "9:16", "16:9", "4:3" 중 하나
    """
    # 1. 해상도 설정
    resolutions = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "4:3": (1440, 1080)
    }
    width, height = resolutions.get(ratio, (1080, 1920))
    
    # 2. 이미지 생성 및 그리기 객체
    bg_color = "#0A0A23"
    image = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(image)
    
    # 3. 폰트 로드
    font_path_bold = resource_path(os.path.join("fonts", "경기천년제목_Bold.ttf"))
    font_path_regular = resource_path(os.path.join("fonts", "NotoSansKR-VF.ttf"))
    font_path_emoji = resource_path(os.path.join("fonts", "NotoColorEmoji-Regular.ttf"))
    
    if not os.path.exists(font_path_bold):
        font_path_bold = "arial.ttf"
    if not os.path.exists(font_path_regular):
        font_path_regular = "arial.ttf"
    if not os.path.exists(font_path_emoji):
        font_path_emoji = font_path_regular

    # 비율에 따른 스케일링 팩터
    scale = width / 1080.0
    
    title_size = int(60 * scale)
    header_size = int(35 * scale)
    row_size = int(32 * scale)
    
    try:
        title_font = ImageFont.truetype(font_path_bold, title_size)
        header_font = ImageFont.truetype(font_path_regular, header_size)
        rank_font = ImageFont.truetype(font_path_bold, row_size)
        nick_font = ImageFont.truetype(font_path_bold, row_size)
        emoji_font = ImageFont.truetype(font_path_emoji, 109)  # CBDT 폰트는 항상 109 사이즈로 로드해야 함
        score_font = ImageFont.truetype(font_path_bold, int(row_size * 1.1))
        info_font = ImageFont.truetype(font_path_bold, int(row_size * 0.9))
    except Exception as e:
        logging.error(f"[핫패치] 폰트 로드 실패, 기본 폰트로 폴백합니다: {e}")
        title_font = header_font = rank_font = nick_font = emoji_font = score_font = info_font = ImageFont.load_default()

    # 4. 타이틀 그리기
    title_text = f"{year}년 {month}월 TOP {start_rank}~{start_rank + max_rank - 1} ({room_size_name})"
    title_color = "#FFD700"
    
    # 타이틀 위치 계산
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_w) / 2, 50 * scale), title_text, font=title_font, fill=title_color)

    # 5. 헤더 그리기
    header_bg = "#1C1C3A"
    header_y = 150 * scale
    header_h = 70 * scale
    draw.rectangle([10, header_y, width - 10, header_y + header_h], fill=header_bg)
    
    headers = ["등수", "닉네임", "점수", "LV", "♥", "지점"]
    # 컬럼 비율 (9:16 기준)
    col_weights = [0.1, 0.35, 0.2, 0.1, 0.1, 0.15]
    col_x = [10]
    for w in col_weights[:-1]:
        col_x.append(col_x[-1] + (width - 20) * w)
    
    header_fg = "#00E5FF"
    for i, h_text in enumerate(headers):
        text_bbox = draw.textbbox((0, 0), h_text, font=header_font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        
        # 중앙 정렬
        center_x = col_x[i] + ((width - 20) * col_weights[i]) / 2
        draw.text((center_x - text_w / 2, header_y + (header_h - text_h) / 2 - 5), h_text, font=header_font, fill=header_fg)

    # 6. 데이터 로드 및 그리기
    start_y = header_y + header_h + 10
    row_h = (height - start_y - 20) / max_rank
    if row_h > 100 * scale: row_h = 100 * scale # 너무 크지 않게 제한
    
    # 왕관 이미지 로드
    crowns = {}
    try:
        img_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "image")
        for r, name in [(1, "1st.png"), (2, "2nd.png"), (3, "3rd.png")]:
            p = os.path.join(img_dir, name)
            if os.path.exists(p):
                crown_img = Image.open(p).convert("RGBA")
                crown_img = crown_img.resize((int(40 * scale), int(40 * scale)), Image.Resampling.LANCZOS)
                crowns[r] = crown_img
    except Exception as e:
        logging.error(f"Error loading crowns: {e}")

    top3_bgs = {1: "#1F1A00", 2: "#101C1F", 3: "#1F1010"}
    top3_rank_fgs = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
    
    # Resolve room size code from name
    room_size_code = None
    for k, v in {"S": "작은방", "M": "중간방", "L": "큰방", "XL": "더큰방"}.items():
        if v in room_size_name or k == room_size_name:
            room_size_code = k
            break
            
    inducted_primary_nicks, alias_manager = get_inducted_teams_for_room(room_size_code)
    
    # Pre-calculate ranks and HOF trophy status
    calculated_ranks = []
    non_hof_rank = start_rank
    
    for idx, entry in enumerate(data):
        nick = str(entry.get("닉네임", "익명"))
        primary = alias_manager.get_primary_nickname(nick) if alias_manager else nick
        primary_clean = primary.strip().lower()
        
        if room_size_code in ["S", "M", "L", "XL"] and primary_clean in inducted_primary_nicks:
            is_hof_trophy = (non_hof_rank == 1)
            calculated_ranks.append((None, is_hof_trophy))
        else:
            calculated_ranks.append((non_hof_rank, False))
            non_hof_rank += 1
            
    for i in range(max_rank):
        curr_y = start_y + i * row_h
        
        if i < len(data):
            entry = data[i]
            rank_num, is_hof_trophy = calculated_ranks[i]
            
            # 행 배경
            row_bg_color = None
            if is_hof_trophy:
                row_bg_color = top3_bgs.get(1)
            elif rank_num in top3_bgs:
                row_bg_color = top3_bgs[rank_num]
                
            if row_bg_color:
                draw.rectangle([10, curr_y, width - 10, curr_y + row_h - 2], fill=row_bg_color)
            
            # 1. 등수
            rank_fg = "#CFD8DC"
            if is_hof_trophy:
                rank_fg = top3_rank_fgs.get(1, rank_fg)
            elif rank_num in top3_rank_fgs:
                rank_fg = top3_rank_fgs[rank_num]
                
            if is_hof_trophy:
                try:
                    temp_sz = 150
                    temp_img = Image.new("RGBA", (temp_sz, temp_sz), (0, 0, 0, 0))
                    temp_draw = ImageDraw.Draw(temp_img)
                    temp_draw.text((10, 10), "🏆", font=emoji_font, fill=None, embedded_color=True)
                    
                    crop_bbox = temp_img.getbbox()
                    if crop_bbox is not None:
                        cropped = temp_img.crop(crop_bbox)
                        crop_w = crop_bbox[2] - crop_bbox[0]
                        crop_h = crop_bbox[3] - crop_bbox[1]
                        
                        target_h = int(40 * scale)
                        target_w = int(crop_w * (target_h / crop_h))
                        
                        scaled_emoji = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
                        y_offset = int((row_h - target_h) / 2)
                        
                        image.paste(scaled_emoji, (int(col_x[0] + 5), int(curr_y + y_offset)), scaled_emoji)
                        
                        # Draw ★ right next to it in gold (size row_size * 0.95)
                        star_font = ImageFont.truetype(font_path_bold, int(row_size * 0.95))
                        draw.text((col_x[0] + 5 + target_w + int(10 * scale), curr_y + (row_h - row_size * 0.95) / 2), "★", font=star_font, fill="#FFD700")
                except Exception as e_trophy:
                    logging.error(f"Error drawing trophy emoji: {e_trophy}")
            elif rank_num in crowns:
                image.paste(crowns[rank_num], (int(col_x[0] + 5), int(curr_y + (row_h - 40 * scale) / 2)), crowns[rank_num])
                draw.text((col_x[0] + 50 * scale, curr_y + (row_h - row_size) / 2), str(rank_num), font=rank_font, fill=rank_fg)
            elif rank_num is not None:
                draw.text((col_x[0] + 20 * scale, curr_y + (row_h - row_size) / 2), str(rank_num), font=rank_font, fill=rank_fg)
            
            # 2. 닉네임
            nick = str(entry.get("닉네임", "익명"))
            nick_color = "#FFFFFF"
            if is_hof_trophy:
                nick_color = "#FFFFE0"
            elif rank_num == 1:
                nick_color = "#FFFFE0"
            elif rank_num == 2:
                nick_color = "#E8E8E8"
            elif rank_num == 3:
                nick_color = "#FFDAB9"
                
            patched_draw_text_with_emojis(draw, (col_x[1] + 10, curr_y + (row_h - row_size) / 2), nick, nick_font, emoji_font, nick_color, image=image)
            
            # 3. 점수
            score = f"{int(entry.get('점수', 0)):,}"
            draw.text((col_x[2] + 10, curr_y + (row_h - row_size) / 2), score, font=score_font, fill="#FFAB00")
            
            # 4. LV
            lv = str(entry.get("레벨", "0"))
            draw.text((col_x[3] + 10, curr_y + (row_h - row_size) / 2), lv, font=info_font, fill="#40C4FF")
            
            # 5. Heart
            heart = str(entry.get("하트", "0"))
            draw.text((col_x[4] + 10, curr_y + (row_h - row_size) / 2), heart, font=info_font, fill="#FF4081")
            
            # 6. Branch
            branch = str(entry.get("지점명", ""))
            if len(branch) > 5: branch = branch[:4] + "…"
            draw.text((col_x[5] + 5, curr_y + (row_h - row_size) / 2), branch, font=info_font, fill="#B0BEC5")

    # 7. 하단 워터마크 또는 날짜
    footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    footer_font = ImageFont.truetype(font_path_regular, int(20 * scale))
    footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    draw.text((width - (footer_bbox[2]-footer_bbox[0]) - 20, height - 40), footer_text, font=footer_font, fill="#444466")

    # 8. 저장
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path)
    return output_path


# ==========================================
# Patch Bootstrapper Entry Point
# ==========================================

def patched_sb_has_emoji(self, text):
    if not hasattr(self, 'pil_font_regular') or self.pil_font_regular is None:
        try:
            font_path_regular = resource_path(os.path.join("fonts", "경기천년제목_Bold.ttf"))
            font_path_emoji = resource_path(os.path.join("fonts", "NotoColorEmoji-Regular.ttf"))
            if not os.path.exists(font_path_regular):
                font_path_regular = "arial.ttf"
            if not os.path.exists(font_path_emoji):
                font_path_emoji = font_path_regular
                
            self.pil_font_regular = ImageFont.truetype(font_path_regular, 26)
            self.pil_font_emoji = ImageFont.truetype(font_path_emoji, 109)
        except Exception as e:
            logging.error(f"[핫패치] ScoreboardApp PIL 폰트 로드 실패: {e}")
            return False

    font = self.pil_font_regular
    try:
        regular_notdef_size = font.getmask("🔥").size
    except Exception:
        regular_notdef_size = None
        
    for char in text:
        c_ord = ord(char)
        if (0x0020 <= c_ord <= 0x007E) or (0x3130 <= c_ord <= 0x318F) or (0xAC00 <= c_ord <= 0xD7AF):
            continue
        if regular_notdef_size is not None:
            try:
                if font.getmask(char).size == regular_notdef_size:
                    return True
            except Exception:
                return True
        else:
            if c_ord > 0xFFFF or 0x2600 <= c_ord <= 0x27BF:
                return True
    return False

def patched_sb_draw_nickname_image(self, nickname, row_bg_hex, fg_hex, target_width=None, is_hof_trophy=False):
    if not hasattr(self, 'pil_font_regular') or self.pil_font_regular is None:
        patched_sb_has_emoji(self, "")
        
    def hex_to_rgb(hex_str, default=(255, 255, 255)):
        try:
            h = hex_str.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return default

    bg_rgb = hex_to_rgb(row_bg_hex, (10, 10, 35))
    fg_rgb = hex_to_rgb(fg_hex, (255, 255, 255))
    
    font = self.pil_font_regular
    emoji_font = self.pil_font_emoji
    
    try:
        regular_notdef_size = font.getmask("🔥").size
    except Exception:
        regular_notdef_size = None
        
    line_h = 26 # Target line height
    
    def is_emoji_char(char):
        c_ord = ord(char)
        if (0x0020 <= c_ord <= 0x007E) or (0x3130 <= c_ord <= 0x318F) or (0xAC00 <= c_ord <= 0xD7AF):
            return False
        if regular_notdef_size is not None:
            try:
                return font.getmask(char).size == regular_notdef_size
            except Exception:
                return True
        return c_ord > 0xFFFF or 0x2600 <= c_ord <= 0x27BF

    total_w = 0
    char_info = []
    for char in nickname:
        is_emoji = is_emoji_char(char)
        if not is_emoji:
            try:
                temp_img = Image.new("RGBA", (1, 1))
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), char, font=font)
                char_w = bbox[2] - bbox[0]
                if char_w <= 0:
                    char_w = 12
            except Exception:
                char_w = 12
        else:
            char_w = int(line_h * 1.1)
            
        char_info.append((char, is_emoji, char_w))
        total_w += char_w
        
    if is_hof_trophy:
        total_w += int(line_h * 0.8) + 5
        
    total_h = 32
    if target_width is not None:
        total_w = target_width
    else:
        total_w += 10
    
    image = Image.new("RGBA", (total_w, total_h), bg_rgb + (255,))
    draw = ImageDraw.Draw(image)
    
    x = 5
    y = int((total_h - line_h) / 2)
    
    for char, is_emoji, char_w in char_info:
        if not is_emoji:
            draw.text((x, y), char, font=font, fill=fg_rgb + (255,))
            x += char_w
        else:
            drawn_via_fallback = False
            try:
                temp_sz = 150
                temp_img = Image.new("RGBA", (temp_sz, temp_sz), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((10, 10), char, font=emoji_font, fill=None, embedded_color=True)
                
                crop_bbox = temp_img.getbbox()
                if crop_bbox is not None:
                    cropped = temp_img.crop(crop_bbox)
                    crop_w = crop_bbox[2] - crop_bbox[0]
                    crop_h = crop_bbox[3] - crop_bbox[1]
                    
                    target_h = int(line_h * 1.1)
                    target_w = int(crop_w * (target_h / crop_h))
                    
                    scaled_emoji = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    y_offset = int((line_h - target_h) / 2)
                    
                    image.paste(scaled_emoji, (int(x), int(y + y_offset)), scaled_emoji)
                    x += target_w
                    drawn_via_fallback = True
            except Exception:
                pass
            
            if not drawn_via_fallback:
                draw.text((x, y), char, font=font, fill=fg_rgb + (255,))
                x += char_w
                
    if is_hof_trophy:
        trophy_x = x + 2
        trophy_y = y - int(line_h * 0.3)
        font_path_bold = resource_path(os.path.join("fonts", "경기천년제목_Bold.ttf"))
        if not os.path.exists(font_path_bold):
            font_path_bold = "arial.ttf"
        badge_font = ImageFont.truetype(font_path_bold, int(line_h * 0.7))
        patched_draw_text_with_emojis(draw, (trophy_x, trophy_y), "🏆", badge_font, emoji_font, (255, 215, 0), image=image)
        
    return image

def patched_sb_show_page_and_schedule_next(self, scores_data):
    if self.shutdown_event.is_set() or not self.winfo_exists():
        return
    if self._after_id_update_scores:
        self.after_cancel(self._after_id_update_scores)
        self._after_id_update_scores = None

    try:
        room_size = self.room_sizes_config[self.current_room_index]
        
        # 1. Load HOF teams
        from patches.active_patch import get_inducted_teams_for_room
        inducted_primary_nicks, alias_manager = get_inducted_teams_for_room(room_size)
        
        # Calculate ranks and HOF trophy status for the entire list
        calculated_ranks = []
        non_hof_rank = 1
        for idx, entry in enumerate(scores_data):
            nick = str(entry.get("닉네임", "익명"))
            primary = alias_manager.get_primary_nickname(nick) if alias_manager else nick
            primary_clean = primary.strip().lower()
            
            if room_size in ["S", "M", "L", "XL"] and primary_clean in inducted_primary_nicks:
                is_hof_trophy = (non_hof_rank == 1)
                calculated_ranks.append((None, is_hof_trophy))
            else:
                calculated_ranks.append((non_hof_rank, False))
                non_hof_rank += 1

        display_start_rank_idx = 20 if self.current_page == 1 else 0
        display_end_rank_idx = 40 if self.current_page == 1 else 20

        for i in range(40):
            self._stop_nickname_marquee(i)
            self.row_frames[i].grid_remove()

        rows_to_update = []
        for i in range(display_start_rank_idx, display_end_rank_idx):
            if i < len(scores_data):
                self.row_frames[i].grid()
                rows_to_update.append(i)
            else:
                self.score_labels[i]['rank_icon'].config(image='')
                for key_to_clear in ['rank_text', 'nickname', 'score', 'level', 'heart', 'branch']:
                    self.score_labels[i][key_to_clear].config(text="")

        for i in rows_to_update:
            entry = scores_data[i]
            rank_num, is_hof_trophy = calculated_ranks[i]
            
            # Draw rank
            if is_hof_trophy:
                if not hasattr(self, '_trophy_image_tk') or self._trophy_image_tk is None:
                    from patches.active_patch import generate_trophy_image
                    self._trophy_image_tk = generate_trophy_image(self)
                self.score_labels[i]['rank_icon'].config(image=self._trophy_image_tk if self._trophy_image_tk else '')
                self.score_labels[i]['rank_text'].config(text="", fg="#FFD700")
            elif rank_num is not None:
                self.score_labels[i]['rank_icon'].config(image=self.crown_images_tk.get(rank_num, ''))
                self.score_labels[i]['rank_text'].config(text=f"{rank_num}", fg="#CFD8DC")
            else:
                self.score_labels[i]['rank_icon'].config(image='')
                self.score_labels[i]['rank_text'].config(text="", fg="#CFD8DC")

            raw_nickname = str(entry.get("닉네임", "익명"))
            nickname_label_widget = self.score_labels[i]['nickname']
            
            # Determine background and nickname text colors
            top_3_bgs = {1: "#1F1A00", 2: "#101C1F", 3: "#1F1010"}
            top_3_nick_fgs = {1: "#FFFFE0", 2: "#E8E8E8", 3: "#FFDAB9"}
            
            row_bg = "#0A0A23"
            nick_fg_color = "#FFFFFF"
            
            if is_hof_trophy:
                row_bg = top_3_bgs.get(1)
                nick_fg_color = top_3_nick_fgs.get(1)
            elif rank_num in top_3_bgs:
                row_bg = top_3_bgs[rank_num]
                nick_fg_color = top_3_nick_fgs[rank_num]
                
            if self.has_emoji(raw_nickname):
                pil_img = self.draw_nickname_image(raw_nickname, row_bg, nick_fg_color, is_hof_trophy=False)
                photo_img = ImageTk.PhotoImage(pil_img)
                
                if not hasattr(self, '_nickname_photo_images'):
                    self._nickname_photo_images = {}
                self._nickname_photo_images[i] = photo_img
                
                nickname_label_widget.config(image=photo_img, text="")
            else:
                nickname_label_widget.config(image='', text=raw_nickname, fg=nick_fg_color)
            
            self.score_labels[i]['score'].config(text=f"{int(entry.get('점수', 0)):,}")
            self.score_labels[i]['level'].config(text=f"{int(entry.get('레벨', 0)):d}")
            self.score_labels[i]['heart'].config(text=f"{int(entry.get('하트', 0)):d}")
            
            raw_branch = str(entry.get("지점명", ""))
            max_branch_chars = 5
            display_branch = (raw_branch[:max_branch_chars-1] + "…") if len(raw_branch) > max_branch_chars else raw_branch
            self.score_labels[i]['branch'].config(text=display_branch)

        self.after(300, lambda: self._check_and_start_marquees(rows_to_update, scores_data))

        display_duration_ms = 6000
        if self.current_page == 0 and len(scores_data) > 20:
            self.current_page = 1
            self._after_id_update_scores = self.after(display_duration_ms, lambda: self._show_page_and_schedule_next(scores_data))
        else:
            self.current_room_index = (self.current_room_index + 1) % len(self.room_sizes_config)
            self._after_id_update_scores = self.after(display_duration_ms, self.main_loop)

    except Exception as e:
        logging.error(f"[핫패치] 점수판 표시 중 오류 발생: {e}", exc_info=True)
        self._after_id_update_scores = self.after(5000, self.main_loop)

def patched_sb_get_nickname_pixel_width(self, nickname, label_font):
    if not self.has_emoji(nickname):
        return label_font.measure(nickname)
        
    font = self.pil_font_regular
    if not font:
        return label_font.measure(nickname)
    line_h = 26
    try:
        regular_notdef_size = font.getmask("🔥").size
    except Exception:
        regular_notdef_size = None

    def is_emoji_char(char):
        c_ord = ord(char)
        if (0x0020 <= c_ord <= 0x007E) or (0x3130 <= c_ord <= 0x318F) or (0xAC00 <= c_ord <= 0xD7AF):
            return False
        if regular_notdef_size is not None:
            try:
                return font.getmask(char).size == regular_notdef_size
            except Exception:
                return True
        return c_ord > 0xFFFF or 0x2600 <= c_ord <= 0x27BF

    total_w = 0
    for char in nickname:
        is_emoji = is_emoji_char(char)
        if not is_emoji:
            try:
                temp_img = Image.new("RGBA", (1, 1))
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), char, font=font)
                char_w = bbox[2] - bbox[0]
                if char_w <= 0:
                    char_w = 12
            except Exception:
                char_w = 12
        else:
            char_w = int(line_h * 1.1)
        total_w += char_w
    return total_w

def patched_sb_check_and_start_marquees(self, rows_indices, scores_data):
    if not self.winfo_exists(): return
    import tkinter.font as tkFont
    for i in rows_indices:
        if i >= len(scores_data): continue
        entry = scores_data[i]
        raw_nickname = str(entry.get("닉네임", "익명"))
        nickname_label_widget = self.score_labels[i]['nickname']
        
        try:
            font_desc_nick = nickname_label_widget.cget("font")
            label_font_nick = tkFont.Font(font=font_desc_nick)
            text_pixel_width_nick = self.get_nickname_pixel_width(raw_nickname, label_font_nick)
            actual_label_pixel_width_nick = nickname_label_widget.winfo_width()

            if actual_label_pixel_width_nick > 1 and text_pixel_width_nick > (actual_label_pixel_width_nick - 5):
                self._start_nickname_marquee(i, nickname_label_widget, raw_nickname, text_pixel_width_nick, actual_label_pixel_width_nick)
        except Exception as e:
            logging.warning(f"[핫패치] 마키 애니메이션: 닉네임 너비 측정 오류({raw_nickname}): {e}")

def patched_sb_start_nickname_marquee(self, label_index, label_widget, full_text, text_pixel_width, label_pixel_width):
    if not self.winfo_exists(): return
    self._stop_nickname_marquee(label_index)

    padding_chars = "     "
    full_text_padded = full_text + padding_chars
    
    rank = label_index + 1
    top_3_bgs = {1: "#1F1A00", 2: "#101C1F", 3: "#1F1010"}
    row_bg = top_3_bgs.get(rank, "#0A0A23")
    top_3_nick_fgs = {1: "#FFFFE0", 2: "#E8E8E8", 3: "#FFDAB9"}
    nick_fg_color = top_3_nick_fgs.get(rank, "#FFFFFF")
    
    import tkinter.font as tkFont
    font_desc_nick = label_widget.cget("font")
    label_font_nick = tkFont.Font(font=font_desc_nick)
    single_period_width = self.get_nickname_pixel_width(full_text_padded, label_font_nick)
    
    double_text = full_text_padded + full_text_padded
    scroll_image = self.draw_nickname_image(double_text, row_bg, nick_fg_color, target_width=None)

    self.nickname_marquee_data[label_index] = {
        'scroll_image': scroll_image,
        'single_period_width': single_period_width,
        'pixel_offset': 0.0,
        'after_id': None,
        'label_widget': label_widget,
        'animation_speed_ms': 16, # ~60 FPS
        'pixel_increment_per_frame': 0.8
    }
    self._animate_nickname_marquee(label_index)

def patched_sb_animate_nickname_marquee(self, label_index):
    if not self.winfo_exists() or label_index not in self.nickname_marquee_data:
        return
    data = self.nickname_marquee_data[label_index]
    label_widget = data['label_widget']
    if not label_widget.winfo_exists():
        self._stop_nickname_marquee(label_index)
        return

    scroll_image = data['scroll_image']
    single_period_width = data['single_period_width']
    current_offset = data['pixel_offset']
    label_width = label_widget.winfo_width()
    
    if label_width <= 1:
        data['after_id'] = self.after(50, lambda idx=label_index: self._animate_nickname_marquee(idx))
        return

    total_h = 32
    x_start = int(current_offset)
    x_end = x_start + label_width
    
    if x_end > scroll_image.width:
        x_end = scroll_image.width
        x_start = max(0, x_end - label_width)
        
    pil_img_cropped = scroll_image.crop((x_start, 0, x_end, total_h))
    photo_img = ImageTk.PhotoImage(pil_img_cropped)

    if not hasattr(self, '_nickname_photo_images'):
        self._nickname_photo_images = {}
    self._nickname_photo_images[label_index] = photo_img

    label_widget.config(image=photo_img, text="")

    next_offset = current_offset + data['pixel_increment_per_frame']
    if next_offset >= single_period_width:
        next_offset -= single_period_width
        
    data['pixel_offset'] = next_offset

    if self.winfo_exists():
        data['after_id'] = self.after(data['animation_speed_ms'], lambda idx=label_index: self._animate_nickname_marquee(idx))


def patched_rm_preload_current_month_cache(self):
    """프로그램 시작 시 현재 월의 랭킹 데이터를 Firebase로부터 백그라운드 로드하여 캐시를 예열(Warm-up)합니다."""
    if not self.db_app:
        return
    
    def _async_preload():
        logging.info("[핫패치] RankingManager: 현재 월 랭킹 데이터 백그라운드 예열(Warm-up) 시작...")
        from datetime import datetime
        import threading
        now = datetime.now()
        year, month = now.year, now.month
        
        quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
        config = getattr(quickstep_mod, 'config', {})
        room_sizes_config_str = config.get('표시할점수판', 'S,M,L,XL')
        room_sizes = [size.strip() for size in room_sizes_config_str.split(',') if size.strip()]
        
        for room_size in room_sizes:
            key = (year, month, room_size)
            with self.lock:
                in_cache = key in self.cache
            
            if not in_cache:
                logging.info(f"[핫패치] RankingManager: 방크기 {room_size}의 랭킹 데이터 비동기 예열 시도...")
                self.get_ranking_list(year, month, room_size)
        
        logging.info("[핫패치] RankingManager: 현재 월 랭킹 데이터 백그라운드 예열 완료.")
        
    import threading
    threading.Thread(target=_async_preload, name="RankingWarmupThread", daemon=True).start()

def patched_rm_execute_save_to_disk(self, year, month, room_size, sorted_list):
    filepath = self._get_cache_filepath(year, month, room_size)
    try:
        if not hasattr(self, 'file_lock'):
            import threading
            self.file_lock = threading.Lock()
            
        with self.file_lock:
            temp_filepath = filepath + ".tmp"
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                import json
                json.dump(sorted_list, f, ensure_ascii=False)
            import os
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(temp_filepath, filepath)
    except Exception as e:
        logging.error(f"[핫패치] 랭킹 캐시 파일 저장 실패 ({filepath}): {e}")

def patched_cctv_stop_recording(self, step_index, recorded_temp_file_path):
    """지정된 채널(step_index)의 CCTV 녹화를 중지합니다. (비동기 스레드 위임)"""
    import threading
    import time
    import logging
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
    
    current_thread_name = threading.current_thread().name
    logging.info(f"[핫패치] CCTVApp.stop_recording 호출됨 (Step: {step_index + 1}, 스레드: {current_thread_name}, 임시파일: {recorded_temp_file_path})")

    if not (0 <= step_index < self.num_rooms):
        logging.error(f"[핫패치] 잘못된 step_index ({step_index})로 녹화 중지 시도.")
        if self.main_window_ref and hasattr(self.main_window_ref, 'recording_stopped_signal'):
            try:
                QMetaObject.invokeMethod(self.main_window_ref.recording_stopped_signal, "emit", Qt.QueuedConnection,
                                         Q_ARG(int, step_index), Q_ARG(str, ""))
            except Exception as e_emit:
                logging.error(f"[핫패치] CCTVApp.stop_recording (잘못된 인덱스): recording_stopped_signal emit 중 오류: {e_emit}", exc_info=True)
        return

    if self.is_recording_status[step_index]:
        self.is_recording_status[step_index] = False
        
        def _async_stop():
            try:
                recorder = self.vlc_recorders[step_index]
                if recorder.is_playing():
                    recorder.stop()
                logging.info(f"[핫패치] Step{step_index + 1} 녹화 중지됨 (VLC stop 호출 완료). 파일 시스템에 쓰기 완료 대기...")
            except Exception as e:
                logging.error(f"[핫패치] Step{step_index + 1} VLC stop 호출 중 오류: {e}", exc_info=True)
            
            time.sleep(1.5)
            if self.winfo_exists():
                self.after(0, lambda: self._after_stop_recording_complete(step_index, recorded_temp_file_path))

        threading.Thread(target=_async_stop, name=f"VlcStopThread_Step{step_index+1}", daemon=True).start()
    else:
        logging.warning(f"[핫패치] Step {step_index + 1} 녹화 중지 시도되었으나, 이미 녹화 중이 아니었습니다.")
        if self.main_window_ref and hasattr(self.main_window_ref, 'recording_stopped_signal'):
            final_path_to_emit_not_recording = ""
            if recorded_temp_file_path:
                 logging.info(f"[핫패치] CCTVApp.stop_recording (else branch): 'is_recording_status'가 false였지만, 'recorded_temp_file_path'가 전달되었습니다. 빈 경로로 시그널을 발생시킵니다.")
            try:
                self.main_window_ref.recording_stopped_signal.emit(step_index, final_path_to_emit_not_recording)
            except Exception as e_emit_not_rec:
                logging.error(f"[핫패치] CCTVApp: 미녹화 상황에서 recording_stopped_signal.emit 중 예외: {e_emit_not_rec}", exc_info=True)

def patched_cctv_after_stop_recording_complete(self, step_index, recorded_temp_file_path):
    """stop_recording 호출 후 1.5초 비동기 대기 후에 최종 검증 및 시그널 전달을 완료합니다."""
    import os
    import logging
    
    try:
        final_path_to_emit = ""
        if recorded_temp_file_path and os.path.exists(recorded_temp_file_path) and os.path.getsize(recorded_temp_file_path) > 1024:
            logging.info(f"[핫패치] 녹화된 유효한 임시 파일: {recorded_temp_file_path}, 크기: {os.path.getsize(recorded_temp_file_path)} bytes")
            final_path_to_emit = recorded_temp_file_path
        else:
            logging.error(f"[핫패치] 녹화된 임시 파일 '{recorded_temp_file_path}'을(를) 찾을 수 없거나, 생성되지 않았거나, 크기가 너무 작습니다. 하이퍼랩스 처리 불가.")

        if self.main_window_ref and hasattr(self.main_window_ref, 'recording_stopped_signal'):
            try:
                self.main_window_ref.recording_stopped_signal.emit(step_index, final_path_to_emit)
                logging.info(f"[핫패치] Step{step_index+1} recording_stopped_signal emit 완료: '{final_path_to_emit}'")
            except Exception as e_emit:
                logging.error(f"[핫패치] Step{step_index+1} recording_stopped_signal emit 실패: {e_emit}", exc_info=True)
    except Exception as e:
        logging.error(f"[핫패치] _after_stop_recording_complete 처리 중 예외 발생: {e}", exc_info=True)

def patched_cctv_execute_set_stream_visibility(self, step_index, show_live_stream, is_initial_start=False):
    """실제로 CCTV 스트림 또는 GIF 플레이스홀더를 표시/숨김 처리하는 내부 메소드입니다. (VLC 비동기 위임)"""
    import os
    import random
    import threading
    import logging
    
    if not self.winfo_exists():
        self.visibility_change_pending[step_index] = False
        return

    player = self.vlc_players[step_index]
    player_frame_widget = self.vlc_player_frames[step_index]
    placeholder_label = self.placeholder_labels[step_index]
    step_name = f"Step{step_index+1}"

    try:
        if step_index in self.gif_after_ids and self.gif_after_ids[step_index]:
            self.after_cancel(self.gif_after_ids[step_index])
            self.gif_after_ids[step_index] = None

        if show_live_stream:
            logging.info(f"[핫패치] {step_name}: 라이브 CCTV 스트림 표시 요청.")
            placeholder_label.pack_forget()
            if not player_frame_widget.winfo_ismapped():
                player_frame_widget.pack(fill="both", expand=True)
            player_frame_widget.update_idletasks()

            def _async_play():
                try:
                    if player and player.is_playing():
                        player.stop()
                    media = self.play_instance.media_new(self.rtsp_urls[step_index])
                    player.set_media(media)
                    media.release()
                    if player_frame_widget.winfo_exists() and player_frame_widget.winfo_id() != 0:
                        player.set_hwnd(player_frame_widget.winfo_id())
                        player.play()
                        logging.info(f"[핫패치] {step_name}: 라이브 CCTV 스트림 비동기 재생 시작 완료.")
                except Exception as e_play:
                    logging.error(f"[핫패치] {step_name} 라이브 스트림 비동기 재생 중 오류: {e_play}")

            threading.Thread(target=_async_play, name=f"VlcPlayThread_{step_name}", daemon=True).start()

        else:
            logging.info(f"[핫패치] {step_name}: GIF Placeholder 애니메이션 표시 요청.")
            player_frame_widget.pack_forget()
            if not placeholder_label.winfo_ismapped():
                placeholder_label.pack(fill="both", expand=True)
            placeholder_label.update_idletasks()

            def _async_stop():
                try:
                    if player and player.is_playing():
                        player.stop()
                    logging.info(f"[핫패치] {step_name}: 라이브 CCTV 스트림 비동기 중지 완료.")
                except Exception as e_stop:
                    logging.error(f"[핫패치] {step_name} 라이브 스트림 비동기 중지 중 오류: {e_stop}")

            threading.Thread(target=_async_stop, name=f"VlcStopThread_{step_name}", daemon=True).start()

            if not self.gif_placeholder_paths or not any(os.path.exists(p) for p in self.gif_placeholder_paths):
                logging.error(f"[핫패치] 사용 가능한 GIF 플레이스홀더 파일이 없습니다. {step_name} 화면이 검게 나올 수 있습니다.")
                placeholder_label.configure(image=None, text="GIF 없음", fg="white", bg="black")
                self._finalize_visibility_change(step_index)
                return

            available_gifs = [p for p in self.gif_placeholder_paths if os.path.exists(p)]
            if not available_gifs:
                logging.error(f"[핫패치] 실제로 사용 가능한 GIF 플레이스홀더 파일이 없습니다. {step_name} 화면이 검게 표시됩니다.")
                placeholder_label.configure(image=None, text="GIF 로드 불가", fg="white", bg="black")
                self._finalize_visibility_change(step_index)
                return

            chosen_gif_path = random.choice(available_gifs)
            self._play_gif_animation(step_index, chosen_gif_path)

    except Exception as e:
        logging.error(f"[핫패치] {step_name} 가시성 제어 처리 중 예외 발생: {e}", exc_info=True)
        self._finalize_visibility_change(step_index)

def patched_quickstep_proceed_with_recording(self, step_name_proc_rec, step_index_proc_rec, record_button_proc_rec):
    """실제 녹화 시작 또는 중지 처리를 담당하는 내부 메소드입니다. (비동기 스레드 위임)"""
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
    from PyQt5.QtWidgets import QMessageBox
    import threading
    import logging
    import os
    
    if not self.cctv_app.is_recording(step_index_proc_rec):
        def _async_start_recording_task():
            try:
                temp_file_path_started = self.cctv_app.start_recording(step_index_proc_rec)
                if temp_file_path_started:
                    QMetaObject.invokeMethod(self, "_handle_start_recording_success_ui", Qt.QueuedConnection,
                                             Q_ARG(str, step_name_proc_rec), Q_ARG(str, temp_file_path_started))
                else:
                    logging.error(f"[핫패치] {step_name_proc_rec} 녹화 시작에 실패했습니다 (VlcStartThread에서 확인됨).")
                    QMetaObject.invokeMethod(record_button_proc_rec, "setText", Qt.QueuedConnection,
                                             Q_ARG(str, "녹화 시작"))
                    QMetaObject.invokeMethod(record_button_proc_rec, "setStyleSheet", Qt.QueuedConnection,
                                             Q_ARG(str, "background-color: lightgreen; color: black; font-weight: bold;"))
                    QMetaObject.invokeMethod(record_button_proc_rec, "setEnabled", Qt.QueuedConnection,
                                             Q_ARG(bool, True))
            except Exception as e:
                logging.error(f"[핫패치] VlcStartThread 실행 중 예외 발생: {e}", exc_info=True)
                QMetaObject.invokeMethod(record_button_proc_rec, "setText", Qt.QueuedConnection,
                                         Q_ARG(str, "녹화 시작"))
                QMetaObject.invokeMethod(record_button_proc_rec, "setStyleSheet", Qt.QueuedConnection,
                                         Q_ARG(str, "background-color: lightgreen; color: black; font-weight: bold;"))
                QMetaObject.invokeMethod(record_button_proc_rec, "setEnabled", Qt.QueuedConnection,
                                         Q_ARG(bool, True))

        record_button_proc_rec.setEnabled(False)
        record_button_proc_rec.setText("시작 중...")
        threading.Thread(target=_async_start_recording_task, name=f"VlcStartThread_{step_name_proc_rec}", daemon=True).start()
    else:
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("녹화 중지 확인")
        msg_box.setText(f"{step_name_proc_rec} 녹화를 중지하고 하이퍼랩스를 생성하시겠습니까?")
        msg_box.setIcon(QMessageBox.Question)

        start_button = msg_box.addButton("시작", QMessageBox.AcceptRole)
        close_button = msg_box.addButton("닫기", QMessageBox.RejectRole)
        cancel_recording_button = msg_box.addButton("녹화 취소", QMessageBox.DestructiveRole)

        msg_box.setDefaultButton(start_button)
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()

        if clicked_button == start_button:
            record_button_proc_rec.setEnabled(False)
            record_button_proc_rec.setText("중지 중...")

            temp_file_to_stop_rec = self.temp_recorded_files.get(step_name_proc_rec)
            if not temp_file_to_stop_rec:
                logging.error(f"[핫패치] {step_name_proc_rec} 녹화 중지 시 임시 파일 경로를 찾을 수 없습니다.")
                QMessageBox.critical(self, "오류",
                                     f"{step_name_proc_rec} 임시 녹화 파일 정보를 찾을 수 없습니다.")
                if hasattr(self.tk_root_window, 'after') and self.cctv_app.is_recording(step_index_proc_rec):
                    self.tk_root_window.after(0, lambda si_stop=step_index_proc_rec: self.cctv_app.stop_recording(
                        si_stop, None))
                else:
                    record_button_proc_rec.setText("녹화 시작")
                    record_button_proc_rec.setStyleSheet("background-color: lightgreen; color: black; font-weight: bold;")
                    record_button_proc_rec.setEnabled(True)
                return

            if hasattr(self.tk_root_window, 'after'):
                self.tk_root_window.after(0, lambda si_stop=step_index_proc_rec,
                                                    tf_stop=temp_file_to_stop_rec: self.cctv_app.stop_recording(
                    si_stop, tf_stop))
            else:
                logging.error("[핫패치] tk_root_window.after를 사용할 수 없습니다.")
                record_button_proc_rec.setText("녹화 시작")
                record_button_proc_rec.setStyleSheet("background-color: lightgreen; color: black; font-weight: bold;")
                record_button_proc_rec.setEnabled(True)

        elif clicked_button == cancel_recording_button:
            logging.info(f"[핫패치] {step_name_proc_rec} 녹화 취소 선택됨.")
            record_button_proc_rec.setEnabled(False)
            record_button_proc_rec.setText("취소 중...")

            temp_file_to_cancel = self.temp_recorded_files.get(step_name_proc_rec)

            if hasattr(self.tk_root_window, 'after'):
                self.tk_root_window.after(0,
                                          lambda si_stop=step_index_proc_rec: self.cctv_app.stop_recording(si_stop,
                                                                                                           ""))

            if temp_file_to_cancel and os.path.exists(temp_file_to_cancel):
                try:
                    os.remove(temp_file_to_cancel)
                    logging.info(f"[핫패치] 임시 파일 삭제 완료: {temp_file_to_cancel}")
                except Exception as e_delete:
                    logging.error(f"[핫패치] 임시 파일 삭제 실패: {e_delete}", exc_info=True)

            if step_name_proc_rec in self.temp_recorded_files:
                del self.temp_recorded_files[step_name_proc_rec]

            record_button_proc_rec.setText("녹화 시작")
            record_button_proc_rec.setStyleSheet("background-color: lightgreen; color: black; font-weight: bold;")
            record_button_proc_rec.setEnabled(True)
            self.stop_recording_timer_display(step_name_proc_rec)

def apply_patch(main_win):
    """런타임 핫패치 진입점:
    - MainWindow.closeEvent 내 중복 'import os'로 인한 UnboundLocalError 문제를 해결합니다.
    - [1.2.9 패치] 테스트 모드 여부에 따른 RankingManager 로컬 캐시 폴더 동적 분리 및 재로드 핫픽스를 주입합니다.
    """
    # 0. UPDATE_URL 핫픽스 (github.com 504 Gateway Timeout 방지용 raw.githubusercontent.com 강제 우회)
    for mod_name in ['__main__', 'quickstep']:
        mod = sys.modules.get(mod_name)
        if mod:
            setattr(mod, "UPDATE_URL", "https://raw.githubusercontent.com/QuickStep2024/QStep/main/version.json")
    logging.info("[핫패치] UPDATE_URL을 raw.githubusercontent.com으로 우회 설정 완료.")

    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    current_ver_str = getattr(quickstep_mod, "CURRENT_VERSION", "1.0.0")
    try:
        ver_parts = [int(x) for x in current_ver_str.split(".")]
    except Exception as e:
        logging.warning(f"[핫패치] 버전 확인 중 예외 발생: {e}")
        ver_parts = [1, 0, 0]

    logging.info("[핫패치] active_patch.py 로딩 및 실행 시작...")

    # 1. MainWindow.closeEvent 핫픽스 (v1.2.9 미만 구버전에만 필요)
    if ver_parts < [1, 2, 9]:
        try:
            main_win.__class__.closeEvent = patched_close_event
            main_win.closeEvent = types.MethodType(patched_close_event, main_win)
            logging.info("[핫패치] MainWindow.closeEvent UnboundLocalError 핫픽스 패치 및 바인딩 완료.")
        except Exception as ex:
            logging.error(f"[핫패치] MainWindow.closeEvent 패치 바인딩 중 예외 발생: {ex}", exc_info=True)
    else:
        logging.info("[핫패치] MainWindow.closeEvent가 이미 소스코드에 내장되어 패치를 건너뜁니다.")

    # 2. RankingManager 로컬 캐시 데이터 폴더 동적 분리 핫픽스 (v1.2.9 미만 구버전에만 필요)
    if ver_parts < [1, 2, 9]:
        try:
            quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
            data_handler_mod = sys.modules.get('data_handler')
            if data_handler_mod and quickstep_mod:
                RankingManager = getattr(data_handler_mod, 'RankingManager', None)
                if RankingManager and RankingManager._instance:
                    config = getattr(quickstep_mod, 'config', None)
                    if not config:
                        try:
                            from data_handler import read_config
                            config = read_config('config.cfg')
                        except Exception:
                            config = {}
                    
                    mode = config.get('mode', 'production') if config else 'production'
                    data_dir = 'data_test' if mode == 'test' else 'data'
                    
                    if RankingManager._instance.data_dir != data_dir:
                        logging.info(f"[핫패치] RankingManager data_dir 변경 감지: {RankingManager._instance.data_dir} -> {data_dir}")
                        with RankingManager._lock:
                            RankingManager._instance.data_dir = data_dir
                            os.makedirs(data_dir, exist_ok=True)
                            RankingManager._instance.cache.clear()
                            RankingManager._instance._load_cache_from_disk()
                        logging.info(f"[핫패치] RankingManager 로컬 캐시 디렉토리 분리 및 재로드 완료 (경로: {data_dir})")
        except Exception as ex_rm:
            logging.error(f"[핫패치] RankingManager 로컬 캐시 디렉토리 핫픽스 주입 중 오류 발생: {ex_rm}", exc_info=True)
    else:
        logging.info("[핫패치] RankingManager 로컬 캐시 디렉토리 핫픽스가 이미 소스코드에 내장되어 패치를 건너뜁니다.")
        
    # 3. 1.2.8용 이모지 렌더링 핫픽스 (v1.3.0 미만 구버전에 필요)
    if ver_parts <= [1, 3, 0]:
        try:
            import gui.scoreboard_generator
            gui.scoreboard_generator.draw_text_with_emojis = patched_draw_text_with_emojis
            gui.scoreboard_generator.generate_scoreboard_image = patched_generate_scoreboard_image
            
            # Patch in gui.dialogs since it imports generate_scoreboard_image directly
            try:
                import gui.dialogs
                gui.dialogs.generate_scoreboard_image = patched_generate_scoreboard_image
            except Exception as e_dlg:
                logging.error(f"[핫패치] gui.dialogs.generate_scoreboard_image 바인딩 실패: {e_dlg}")
                
            logging.info("[핫패치] 1.2.8용 이모지 렌더링(NotoColorEmoji) 핫픽스 패치 및 바인딩 완료.")
        except Exception as ex_emoji:
            logging.error(f"[핫패치] 1.2.8용 이모지 렌더링 핫픽스 주입 중 오류 발생: {ex_emoji}", exc_info=True)
    else:
        logging.info("[핫패치] 1.2.8용 이모지 렌더링 핫픽스가 이미 소스코드에 내장되어(v1.3.0 이상) 패치를 건너뜁니다.")

    # 4. 실시간 전광판(ScoreboardApp) 이모지 렌더링 및 마키 애니메이션 핫픽스 (v1.3.0 미만 구버전에 필요)
    if ver_parts <= [1, 3, 0]:
        try:
            import scoreboard_app
            for app_class in [scoreboard_app.ScoreboardApp] + ([quickstep_mod.ScoreboardApp] if (quickstep_mod and hasattr(quickstep_mod, 'ScoreboardApp')) else []):
                app_class.has_emoji = patched_sb_has_emoji
                app_class.draw_nickname_image = patched_sb_draw_nickname_image
                app_class.get_nickname_pixel_width = patched_sb_get_nickname_pixel_width
                app_class._show_page_and_schedule_next = patched_sb_show_page_and_schedule_next
                app_class._check_and_start_marquees = patched_sb_check_and_start_marquees
                app_class._start_nickname_marquee = patched_sb_start_nickname_marquee
                app_class._animate_nickname_marquee = patched_sb_animate_nickname_marquee
            logging.info("[핫패치] 실시간 전광판(ScoreboardApp) 이모지 렌더링 및 마키 애니메이션 핫픽스 패치 및 바인딩 완료.")
        except Exception as ex_sb:
            logging.error(f"[핫패치] 실시간 전광판(ScoreboardApp) 핫픽스 주입 중 오류 발생: {ex_sb}", exc_info=True)
    else:
        logging.info("[핫패치] 실시간 전광판(ScoreboardApp) 핫픽스가 이미 소스코드에 내장되어(v1.3.0 이상) 패치를 건너뜁니다.")

    # 5. CCTVApp 비동기화 및 RankingManager 캐싱 개편 핫픽스 (v1.3.0 미만 구버전에 필요)
    if ver_parts <= [1, 3, 0]:
        try:
            import data_handler
            data_handler.RankingManager.preload_current_month_cache = patched_rm_preload_current_month_cache
            data_handler.RankingManager._execute_save_to_disk = patched_rm_execute_save_to_disk
            rm_instance = data_handler.RankingManager._instance
            if rm_instance:
                if not hasattr(rm_instance, 'file_lock'):
                    import threading
                    rm_instance.file_lock = threading.Lock()
                rm_instance.preload_current_month_cache()
            logging.info("[핫패치] RankingManager 비동기 캐시 예열 및 file_lock 핫픽스 패치 완료.")
        except Exception as ex_rm_hot:
            logging.error(f"[핫패치] RankingManager 핫픽스 주입 중 오류 발생: {ex_rm_hot}", exc_info=True)

        try:
            import cctv_app
            cctv_app.CCTVApp.stop_recording = patched_cctv_stop_recording
            cctv_app.CCTVApp._after_stop_recording_complete = patched_cctv_after_stop_recording_complete
            cctv_app.CCTVApp._execute_set_stream_visibility = patched_cctv_execute_set_stream_visibility
            logging.info("[핫패치] CCTVApp 비동기 VLC stop/play 및 레코더 stop 핫픽스 패치 완료.")
        except Exception as ex_cctv_hot:
            logging.error(f"[핫패치] CCTVApp 핫픽스 주입 중 오류 발생: {ex_cctv_hot}", exc_info=True)

        try:
            main_win.__class__._proceed_with_recording = patched_quickstep_proceed_with_recording
            main_win._proceed_with_recording = types.MethodType(patched_quickstep_proceed_with_recording, main_win)
            logging.info("[핫패치] MainWindow._proceed_with_recording 비동기 start_recording 핫픽스 패치 완료.")
        except Exception as ex_quick_hot:
            logging.error(f"[핫패치] MainWindow._proceed_with_recording 핫픽스 주입 중 오류 발생: {ex_quick_hot}", exc_info=True)
    else:
        logging.info("[핫패치] CCTVApp 및 MainWindow 비동기 개편 핫픽스가 이미 소스코드에 내장되어(v1.3.0 이상) 패치를 건너뜁니다.")

    logging.info("[핫패치] 원격 핫패치가 실시간으로 메모리에 주입되었습니다. 🔥")
