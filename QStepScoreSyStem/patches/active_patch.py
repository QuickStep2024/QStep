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

def patched_fetch_json_via_subprocess(self, url, timeout=5):
    import subprocess
    import json
    import sys
    
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        logging.debug(f"[핫패치] curl 조회 실패: {e}")

    try:
        cmd = f"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-RestMethod -Uri '{url}' -TimeoutSec {timeout} | ConvertTo-Json -Compress"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        logging.debug(f"[핫패치] powershell 조회 실패: {e}")

    import requests
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()

def patched_fetch_text_via_subprocess(self, url, timeout=5):
    import subprocess
    import sys
    
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        logging.debug(f"[핫패치] curl 패치 다운로드 실패: {e}")

    try:
        cmd = f"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '{url}' -TimeoutSec {timeout} | Select-Object -ExpandProperty Content"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        logging.debug(f"[핫패치] powershell 패치 다운로드 실패: {e}")

    import requests
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text

def patched_check_patch_update(self, version_info):
    import sys
    import os
    from PyQt5.QtCore import QMetaObject, Qt
    from packaging import version
    
    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    current_version_str = getattr(quickstep_mod, "CURRENT_VERSION", "1.0.0")
    
    try:
        latest_ver = version.parse(version_info.get("version", "1.0.0"))
        current_ver = version.parse(current_version_str)
        if current_ver > latest_ver:
            logging.info(f"[핫패치] 현재 버전(v{current_version_str})이 패치 대상 버전(v{latest_ver})보다 크므로 패치 검사를 생략합니다.")
            return
    except Exception as e:
        logging.warning(f"[핫패치] 버전 비교 중 오류 발생: {e}")

    try:
        server_patch_ver = int(version_info.get("patch_version", 0))
        local_patch_ver = int(self.settings.value("appPatchVersion", 0))
        
        if server_patch_ver > local_patch_ver:
            patch_url = version_info.get("patch_url")
            if not patch_url:
                return
                
            logging.info(f"[핫패치] 새로운 핫패치 발견: v{server_patch_ver} (현재 로컬 패치: v{local_patch_ver})")
            
            patch_urls = [patch_url]
            if "raw.githubusercontent.com/QuickStep2024/QStep/main/" in patch_url:
                patch_urls.append(patch_url.replace("raw.githubusercontent.com/QuickStep2024/QStep/main/", "cdn.jsdelivr.net/gh/QuickStep2024/QStep@main/"))
                patch_urls.append(patch_url.replace("raw.githubusercontent.com/QuickStep2024/QStep/main/", "raw.githack.com/QuickStep2024/QStep/main/"))
            elif "github.com/QuickStep2024/QStep/raw/refs/heads/main/" in patch_url:
                patch_urls.append(patch_url.replace("github.com/QuickStep2024/QStep/raw/refs/heads/main/", "cdn.jsdelivr.net/gh/QuickStep2024/QStep@main/"))
                patch_urls.append(patch_url.replace("github.com/QuickStep2024/QStep/raw/refs/heads/main/", "raw.githack.com/QuickStep2024/QStep/main/"))

            patch_content = None
            for p_url in patch_urls:
                try:
                    logging.info(f"[핫패치] 핫패치 다운로드 시도 중: {p_url}")
                    patch_content = self._fetch_text_via_subprocess(p_url, timeout=5)
                    if patch_content and "def apply_patch" in patch_content:
                        logging.info(f"[핫패치] 핫패치 다운로드 성공 ({p_url})")
                        break
                except Exception as e_p:
                    logging.warning(f"[핫패치] 핫패치 다운로드 실패 ({p_url}): {e_p}")

            if not patch_content:
                raise Exception("모든 패치 다운로드 주소에서 패치 파일 획득 실패")
            
            if getattr(sys, 'frozen', False):
                patch_dir = os.path.join(os.path.dirname(sys.executable), "patches")
            else:
                patch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patches")
            os.makedirs(patch_dir, exist_ok=True)
            patch_file = os.path.join(patch_dir, "active_patch.py")
            
            temp_patch_file = patch_file + ".tmp"
            with open(temp_patch_file, "w", encoding="utf-8") as f:
                f.write(patch_content)
            
            if os.path.exists(patch_file):
                os.remove(patch_file)
            os.rename(temp_patch_file, patch_file)
            
            self.settings.setValue("appPatchVersion", server_patch_ver)
            self.settings.sync()
            
            logging.info(f"[핫패치] 핫패치 v{server_patch_ver} 다운로드 완료. 실시간 즉시 덮어쓰기 적용을 수행합니다.")
            QMetaObject.invokeMethod(self, "apply_local_hotpatch", Qt.QueuedConnection)
    except Exception as e:
        logging.error(f"[핫패치] 핫패치 업데이트 확인/다운로드 중 실패: {e}")

def patched_check_version_thread(self, manual):
    import sys
    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
    from packaging import version
    
    quickstep_mod = sys.modules.get('__main__') or sys.modules.get('quickstep')
    current_version_str = getattr(quickstep_mod, "CURRENT_VERSION", "1.0.0")
    update_url = getattr(quickstep_mod, "UPDATE_URL", "https://raw.githubusercontent.com/QuickStep2024/QStep/main/version.json")
    
    urls = [
        update_url,
        "https://cdn.jsdelivr.net/gh/QuickStep2024/QStep@main/version.json",
        "https://raw.githack.com/QuickStep2024/QStep/main/version.json"
    ]
    
    update_info = None
    last_error = None
    
    for url in urls:
        try:
            logging.info(f"[핫패치] 버전 확인 시도 중: {url}")
            update_info = self._fetch_json_via_subprocess(url, timeout=5)
            if update_info and "version" in update_info:
                logging.info(f"[핫패치] 버전 확인 성공 ({url})")
                break
        except Exception as e:
            logging.warning(f"[핫패치] 버전 확인 실패 ({url}): {e}")
            last_error = e
            
    if not update_info:
        logging.error(f"[핫패치] 모든 경로에서 버전 정보 확인 실패: {last_error}")
        QMetaObject.invokeMethod(self.update_status_label, "setText", Qt.QueuedConnection, Q_ARG(str, "버전 확인 실패"))
        if manual:
            QMetaObject.invokeMethod(self, "_show_qmessagebox_critical_safe", Qt.QueuedConnection,
                                     Q_ARG(str, "업데이트 오류"),
                                     Q_ARG(str, f"버전 정보를 가져오는 데 실패했습니다:\n{last_error}"))
        return

    self.update_info = update_info

    try:
        self.check_patch_update(self.update_info)

        latest_ver = version.parse(self.update_info['version'])
        current_ver = version.parse(current_version_str)

        if latest_ver > current_ver:
            logging.info(f"[핫패치] 새 버전 발견: {latest_ver} (현재 버전: {current_ver})")
            QMetaObject.invokeMethod(self, "prompt_for_update", Qt.QueuedConnection, Q_ARG(dict, self.update_info))
        else:
            logging.info("[핫패치] 현재 최신 버전을 사용 중입니다.")
            QMetaObject.invokeMethod(self.update_status_label, "setText", Qt.QueuedConnection,
                                     Q_ARG(str, f"최신 버전입니다 (v{current_version_str})"))
            if manual:
                QMetaObject.invokeMethod(self, "_show_qmessagebox_info_safe", Qt.QueuedConnection,
                                         Q_ARG(str, "업데이트 확인"),
                                         Q_ARG(str, f"현재 최신 버전(v{current_version_str})을 사용하고 있습니다."))
    except Exception as e:
        logging.error(f"[핫패치] 버전 분석/패치 중 오류: {e}")
        QMetaObject.invokeMethod(self.update_status_label, "setText", Qt.QueuedConnection, Q_ARG(str, "버전 확인 실패"))
        if manual:
            QMetaObject.invokeMethod(self, "_show_qmessagebox_critical_safe", Qt.QueuedConnection,
                                     Q_ARG(str, "업데이트 오류"),
                                     Q_ARG(str, f"버전 분석 중 오류가 발생했습니다:\n{e}"))

def patched_prompt_for_update(self, version_info):
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtCore import Qt
    
    latest_version = version_info['version']
    release_notes = version_info.get('notes', '릴리스 노트가 없습니다.')

    msg_box = QMessageBox(self)
    msg_box.setWindowTitle("새 업데이트 발견")
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setText(f"새로운 버전 <b>{latest_version}</b>이(가) 있습니다.\n지금 업데이트하시겠습니까?")
    msg_box.setInformativeText(f"<b>릴리스 노트:</b><br>{release_notes}")

    # 항상 위에 표시 플래그 추가 (가려져서 먹통이 되는 현상 방지)
    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)

    update_button = msg_box.addButton("업데이트", QMessageBox.AcceptRole)
    cancel_button = msg_box.addButton("나중에", QMessageBox.RejectRole)

    msg_box.exec_()

    if msg_box.clickedButton() == update_button:
        self.start_update_download(version_info)

def apply_patch(main_win):
    """런타임 핫패치 진입점:
    - [1.3.3 패치] NotoColorEmoji-Regular.ttf GDI 임시 등록 생략 핫픽스 주입
    - [업데이트 개선] GIL 블로킹(DNS 지연 등) 및 리다이렉션 504 우회를 위해 curl/powershell 및 multi-CDN 폴백 방식의 비동기 업데이트 확인 주입
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

    # GIL-safe 비동기 업데이트 확인 및 핫패치 주입 우회 등록
    if ver_parts <= [1, 3, 3]:
        try:
            import types
            main_win._fetch_json_via_subprocess = types.MethodType(patched_fetch_json_via_subprocess, main_win)
            main_win._fetch_text_via_subprocess = types.MethodType(patched_fetch_text_via_subprocess, main_win)
            main_win.check_patch_update = types.MethodType(patched_check_patch_update, main_win)
            main_win._check_version_thread = types.MethodType(patched_check_version_thread, main_win)
            main_win.prompt_for_update = types.MethodType(patched_prompt_for_update, main_win)
            logging.info("[핫패치] GIL-safe 업데이트/패치 다운로더 및 항상위 다이얼로그 바인딩 완료.")
        except Exception as ex_up_hot:
            logging.error(f"[핫패치] 업데이트/패치 핫픽스 주입 중 오류 발생: {ex_up_hot}", exc_info=True)

    logging.info("[핫패치] 원격 핫패치가 실시간으로 메모리에 주입되었습니다. 🔥")
