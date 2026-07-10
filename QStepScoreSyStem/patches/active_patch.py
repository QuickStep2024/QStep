# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import logging

def patched_load_fonts():
    """[1.3.3 패치] NotoColorEmoji-Regular.ttf GDI 임시 등록 생략 버전"""
    import platform
    import ctypes
    import scoreboard_app
    
    font_dir = scoreboard_app.resource_path("fonts")
    if not os.path.isdir(font_dir):
        logging.warning(f"폰트 디렉토리 '{font_dir}'를 찾을 수 없습니다.")
        return

    if platform.system() == "Windows":
        gdi32 = ctypes.WinDLL('gdi32')
        loaded_count = 0
        for filename in os.listdir(font_dir):
            if filename.lower().endswith((".ttf", ".otf")):
                # NotoColorEmoji-Regular.ttf는 GDI에서 지원하지 않으므로 임시 등록 생략 (Pillow에서 직접 로드됨)
                if filename == "NotoColorEmoji-Regular.ttf":
                    continue
                font_path = os.path.join(font_dir, filename)
                try:
                    if gdi32.AddFontResourceW(font_path) != 0:
                        loaded_count += 1
                        logging.info(f"Windows GDI를 통해 폰트 임시 등록 성공: {filename}")
                    else:
                        logging.warning(f"Windows GDI를 통해 폰트 임시 등록 실패: {filename}")
                except Exception as e:
                    logging.error(f"폰트 등록 중 예외 발생 ({filename}): {e}")
        
        if loaded_count > 0:
            user32 = ctypes.WinDLL('user32')
            user32.SendNotifyMessageW(0xFFFF, 0x001D, 0, 0)
            logging.info(f"총 {loaded_count}개의 폰트가 로드되었으며, 시스템에 폰트 변경 알림을 보냈습니다.")
    else:
        logging.info(f"현재 운영체제({platform.system()})에서는 자동 폰트 로드를 지원하지 않습니다.")

def patched_unload_fonts():
    """[1.3.3 패치] NotoColorEmoji-Regular.ttf GDI 해제 생략 버전"""
    import platform
    import ctypes
    import scoreboard_app
    
    font_dir = scoreboard_app.resource_path("fonts")
    if not os.path.isdir(font_dir):
        return

    if platform.system() == "Windows":
        gdi32 = ctypes.WinDLL('gdi32')
        removed_count = 0
        for filename in os.listdir(font_dir):
            if filename.lower().endswith((".ttf", ".otf")):
                if filename == "NotoColorEmoji-Regular.ttf":
                    continue
                font_path = os.path.join(font_dir, filename)
                try:
                    if gdi32.RemoveFontResourceW(font_path) != 0:
                        removed_count += 1
                        logging.info(f"Windows GDI를 통해 폰트 해제 성공: {filename}")
                except Exception as e:
                    logging.error(f"폰트 해제 중 예외 발생 ({filename}): {e}")
        
        if removed_count > 0:
            user32 = ctypes.WinDLL('user32')
            user32.SendNotifyMessageW(0xFFFF, 0x001D, 0, 0)
            logging.info(f"총 {removed_count}개의 폰트가 해제되었습니다.")

def apply_patch(main_win):
    """런타임 핫패치 진입점:
    - [1.3.3 패치] NotoColorEmoji-Regular.ttf GDI 임시 등록 생략 핫픽스 주입
    """
    logging.info("[핫패치] active_patch.py 로딩 및 실행 시작...")

    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    current_ver_str = getattr(quickstep_mod, "CURRENT_VERSION", "1.0.0")
    try:
        ver_parts = [int(x) for x in current_ver_str.split(".")]
    except Exception as e:
        logging.warning(f"[핫패치] 버전 확인 중 예외 발생: {e}")
        ver_parts = [1, 0, 0]

    # NotoColorEmoji-Regular.ttf GDI 임시 등록 생략 패치 (v1.3.3 이하 버전에 모두 적용)
    if ver_parts <= [1, 3, 3]:
        try:
            import scoreboard_app
            scoreboard_app.load_fonts = patched_load_fonts
            scoreboard_app.unload_fonts = patched_unload_fonts
            logging.info("[핫패치] scoreboard_app 폰트 임시 등록 예외처리 핫픽스 패치 완료.")
        except Exception as ex_font_hot:
            logging.error(f"[핫패치] scoreboard_app 폰트 핫픽스 주입 중 오류 발생: {ex_font_hot}", exc_info=True)

    logging.info("[핫패치] 원격 핫패치가 실시간으로 메모리에 주입되었습니다. 🔥")
