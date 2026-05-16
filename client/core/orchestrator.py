"""
Orchestrator (팀장) - 전체 워크플로우 오케스트레이션
각 모듈을 조율하여 자동 발송 프로세스를 실행
"""

import json
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from core.window_controller import WindowController
from core.screen_capture import ScreenCapture
from core.ocr_engine import OCREngine
from core.contact_manager import ContactManager, Contact
from core.message_engine import MessageEngine
from core.kakao_sender import KakaoSender, SendResult
from core.report_generator import ReportGenerator
from core.scheduler import Scheduler

try:
    from core.sejong_sender import SejongSender, SejongConfig, SejongSendResult
except ImportError:
    SejongSender = None


class OrchestratorState:
    """오케스트레이터 상태"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    SENDING = "sending"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class Orchestrator:
    """
    팀장 모듈 - 전체 자동화 워크플로우 관리

    워크플로우:
    1. 초기화 (카카오톡 창 설정)
    2. 발송 대상 로드 & 메시지 생성
    3. 순차 발송 (검색 → OCR 확인 → 전송)
    4. 리포트 생성
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".")

        # 설정 로드
        self.config = self._load_config()

        # 모듈 초기화
        self.window_ctrl = WindowController(self.config)
        self.screen_capture = ScreenCapture(str(self.base_dir / "logs" / "screenshots"))
        self.contact_mgr = ContactManager(str(self.base_dir / "data" / "contacts.json"))
        self.message_engine = MessageEngine(str(self.base_dir / "data" / "templates"))
        self.report = ReportGenerator(str(self.base_dir / "logs"))

        self.sender: Optional[KakaoSender] = None
        self.sejong_sender: Optional[SejongSender] = None
        self.coordinates: dict = {}
        self.scheduler = Scheduler(str(self.base_dir / "data" / "schedules.json"), self)

        # 발송 방법: "kakao_bot" | "alimtalk" | "sms"
        self.send_method = "kakao_bot"

        # 상태
        self.state = OrchestratorState.IDLE
        self.current_index = 0
        self.total_count = 0
        self.send_queue: list[dict] = []  # [{"contact": Contact, "message": str}]

        # 콜백 (UI 업데이트용)
        self._on_state_change: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
        self._on_result: Optional[Callable] = None
        self._on_log: Optional[Callable] = None

        # 스레드
        self._send_thread: Optional[threading.Thread] = None

    def _load_config(self) -> dict:
        """설정 파일 로드 + .env 환경변수 병합"""
        # .env 로드
        env_path = self.base_dir / ".env"
        if env_path.exists() and load_dotenv:
            load_dotenv(env_path)

        config_path = self.base_dir / "config" / "default_config.json"
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        # .env → sejong 설정 병합 (환경변수가 있으면 우선)
        env_sejong = {}
        if os.getenv("SEJONG_DB_HOST"):
            env_sejong["db"] = {
                "host": os.getenv("SEJONG_DB_HOST", "localhost"),
                "port": int(os.getenv("SEJONG_DB_PORT", "3306")),
                "name": os.getenv("SEJONG_DB_NAME", "sms"),
                "user": os.getenv("SEJONG_DB_USER", ""),
                "password": os.getenv("SEJONG_DB_PASSWORD", ""),
            }
            env_sejong["kakao"] = {
                "sender_key": os.getenv("SEJONG_SENDER_KEY", ""),
                "callback": os.getenv("SEJONG_CALLBACK", ""),
                "template_code": os.getenv("SEJONG_TEMPLATE_CODE", ""),
            }
            # .env 값으로 덮어쓰기 (config에 sejong이 없거나 비어있으면)
            existing = config.get("sejong", {})
            if not existing.get("db", {}).get("user"):
                config["sejong"] = env_sejong

        return config

    # -- 콜백 등록 --

    def on_state_change(self, callback: Callable):
        self._on_state_change = callback

    def on_progress(self, callback: Callable):
        self._on_progress = callback

    def on_result(self, callback: Callable):
        self._on_result = callback

    def on_log(self, callback: Callable):
        self._on_log = callback

    def _emit_state(self, state: str):
        self.state = state
        if self._on_state_change:
            self._on_state_change(state)

    def _emit_progress(self, current: int, total: int, name: str = ""):
        if self._on_progress:
            self._on_progress(current, total, name)

    def _emit_result(self, result: dict):
        if self._on_result:
            self._on_result(result)

    def _emit_log(self, message: str, level: str = "info"):
        if self._on_log:
            self._on_log(message, level)

    # -- 초기화 --

    def initialize(self) -> dict:
        """
        시스템 초기화
        1. 카카오톡 창 찾기
        2. 위치/크기 고정
        3. 스크린샷 캡처 & 캘리브레이션
        4. 사용자 확인 대기 (UI에서 처리)
        """
        self._emit_state(OrchestratorState.INITIALIZING)
        self._emit_log("시스템 초기화 중...")

        # 화면 정보
        screen_info = self.window_ctrl.get_screen_info()
        self._emit_log(f"화면: {screen_info['screen_width']}x{screen_info['screen_height']} "
                       f"(DPI: {screen_info['dpi_scale']}x)")

        # 카카오톡 찾기
        if not self.window_ctrl.find_kakao_window():
            self._emit_state(OrchestratorState.ERROR)
            self._emit_log("카카오톡이 실행되어 있지 않습니다!", "error")
            return {"success": False, "kakao_found": False,
                    "error": "카카오톡이 실행되어 있지 않습니다."}

        self._emit_log("카카오톡 발견!")

        # 위치 계산 (포그라운드 전환 안 함)
        import time
        time.sleep(0.3)
        self.window_ctrl.calculate_kakao_position()
        positioned = self.window_ctrl.position_kakao_window()

        if not positioned:
            self._emit_log("카카오톡 창 위치 조정 실패. 수동으로 배치해주세요.", "warning")

        time.sleep(0.5)  # 창 이동 후 안정화 대기

        # 스크린샷 기반 캘리브레이션
        self._emit_log("카카오톡 창 캡처 중...")
        calibration = self.window_ctrl.calibrate(self.screen_capture)

        if not calibration.get("success"):
            self._emit_state(OrchestratorState.ERROR)
            self._emit_log(f"캘리브레이션 실패: {calibration.get('error', '')}", "error")
            return {"success": False, "error": calibration.get("error", "캘리브레이션 실패")}

        self.coordinates = calibration["coordinates"]
        self._emit_log(f"캘리브레이션 완료! 스크린샷: {calibration['screenshot_path']}")

        # 좌표 로그
        search_icon = self.coordinates.get("search_icon", {})
        self._emit_log(f"  돋보기 아이콘: ({search_icon.get('x')}, {search_icon.get('y')})")
        msg_input = self.coordinates.get("message_input", {})
        self._emit_log(f"  메시지 입력창: ({msg_input.get('x')}, {msg_input.get('y')})")

        return {
            "success": True,
            "calibration_pending": True,
            "screenshot_path": calibration["screenshot_path"],
            "screen": screen_info,
            "kakao_rect": self.window_ctrl.kakao_rect,
            "coordinates": self.coordinates
        }

    def auto_detect_coordinates(self) -> dict:
        """
        카카오톡 창 위치를 자동 감지하고 디폴트 좌표 계산
        학습된 좌표 없이도 바로 사용 가능
        """
        if not self.window_ctrl.find_kakao_window():
            return {"success": False, "error": "카카오톡이 실행되어 있지 않습니다."}

        # 실제 카카오톡 창 위치 기반 좌표 자동 계산
        coords = self.window_ctrl.calculate_ui_coordinates()
        self.coordinates = coords
        self._emit_log(f"카카오톡 창 감지: ({self.window_ctrl.kakao_rect['x']}, "
                       f"{self.window_ctrl.kakao_rect['y']}) "
                       f"{self.window_ctrl.kakao_rect['width']}x"
                       f"{self.window_ctrl.kakao_rect['height']}")
        self._emit_log("디폴트 좌표 자동 계산 완료!")
        return {"success": True, "coordinates": coords}

    def confirm_calibration(self) -> dict:
        """
        캘리브레이션 확인 - 사용자가 스크린샷을 확인한 후 호출
        KakaoSender를 초기화하고 발송 준비 상태로 전환
        """
        if not self.coordinates:
            # 학습된 좌표 없으면 자동 계산 시도
            result = self.auto_detect_coordinates()
            if not result.get("success"):
                return {"success": False, "error": "좌표를 설정해주세요."}

        # KakaoSender 초기화
        self.sender = KakaoSender(self.coordinates, self.config)

        self._emit_state(OrchestratorState.READY)
        self._emit_log("셋팅 확인 완료! 발송 준비 완료.")

        return {"success": True}

    # -- 발송 준비 --

    def prepare_send_queue(self, category: str, template_content: str) -> list[dict]:
        """
        발송 큐 준비

        Args:
            category: 카테고리 ("friend", "family", "business", "all" 등)
            template_content: 메시지 템플릿 텍스트
        """
        contacts = self.contact_mgr.get_by_category(category)
        self.send_queue = []

        for contact in contacts:
            message = self.message_engine.substitute(
                template_content,
                contact.to_dict()
            )
            self.send_queue.append({
                "contact": contact,
                "message": message
            })

        self.total_count = len(self.send_queue)
        self.current_index = 0

        self._emit_log(f"발송 큐 준비 완료: {self.total_count}명")
        return [
            {
                "name": item["contact"].name,
                "category": item["contact"].category,
                "message": item["message"]
            }
            for item in self.send_queue
        ]

    def prepare_custom_queue(self, contacts: list[Contact], template_content: str,
                            image_path: str = None,
                            template_contents: list = None) -> list[dict]:
        """선택된 연락처로 발송 큐 준비
        template_contents: 여러 변형 메시지 리스트 (있으면 랜덤 선택)
        """
        self.send_queue = []

        for contact in contacts:
            if template_contents and len(template_contents) > 1:
                message = self.message_engine.substitute_random(
                    template_contents, contact.to_dict()
                )
            else:
                message = self.message_engine.substitute(
                    template_content,
                    contact.to_dict()
                )
            self.send_queue.append({
                "contact": contact,
                "message": message,
                "image_path": image_path
            })

        self.total_count = len(self.send_queue)
        self.current_index = 0

        self._emit_log(f"발송 큐 준비 완료: {self.total_count}명")
        return [
            {
                "name": item["contact"].name,
                "category": item["contact"].category,
                "message": item["message"]
            }
            for item in self.send_queue
        ]

    # -- 발송 실행 --

    def start_sending(self):
        """발송 시작 (별도 스레드)"""
        if self.state == OrchestratorState.SENDING:
            self._emit_log("이미 발송 중입니다.", "warning")
            return

        if not self.send_queue:
            self._emit_log("발송할 대상이 없습니다.", "warning")
            return

        if not self.sender:
            self._emit_log("먼저 초기화를 실행해주세요.", "error")
            return

        # 완료/에러 상태에서 다시 시작 → 처음부터
        if self.state in (OrchestratorState.COMPLETED, OrchestratorState.ERROR,
                          OrchestratorState.IDLE, OrchestratorState.READY):
            self.current_index = 0
            self._emit_log("발송 큐를 처음부터 다시 시작합니다.")

        self.sender.resume()
        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()

    def _send_loop(self):
        """발송 루프 (스레드에서 실행) - 안전 장치 포함"""
        self._emit_state(OrchestratorState.SENDING)
        self.report.start_session()
        self._emit_log("=" * 40)
        self._emit_log("발송 시작!")
        self._emit_log("=" * 40)

        # 안전 정지 콜백 등록
        def on_safety(msg):
            self._emit_log(f"🛑 {msg}", "error")

        self.sender.on_safety_stop(on_safety)

        while self.current_index < self.total_count:
            # 정지 체크 (일시정지 or 안전 정지)
            if self.sender._stop_flag:
                if self.sender._safety_error:
                    self._emit_state(OrchestratorState.ERROR)
                    self._emit_log("=" * 40)
                    self._emit_log(f"안전 정지로 발송 중단!", "error")
                    self._emit_log(f"원인: {self.sender._safety_error}", "error")
                    self._emit_log("=" * 40)
                    break
                else:
                    self._emit_state(OrchestratorState.PAUSED)
                    self._emit_log("발송 일시정지됨")
                    return

            # 일일 한도 체크
            if not self.sender.check_daily_limit():
                self._emit_log(f"일일 발송 한도({self.sender.daily_limit}명) 도달! 내일 다시 시도하세요.", "warning")
                break

            item = self.send_queue[self.current_index]
            contact = item["contact"]
            message = item["message"]
            image_path = item.get("image_path")

            self._emit_progress(self.current_index + 1, self.total_count, contact.name)
            self._emit_log(f"[{self.current_index + 1}/{self.total_count}] "
                           f"{contact.name}에게 발송 중..."
                           + (" (이미지 첨부)" if image_path else ""))

            # 발송
            from core.kakao_win32 import _log as _debug_log
            _debug_log(f"orchestrator: {contact.name}에게 send_to_contact 호출")
            result = self.sender.send_to_contact(contact.name, message, image_path=image_path)
            _debug_log(f"orchestrator: 결과={result.status} detail={result.detail}")
            result_dict = result.to_dict()
            self.report.add_result(result_dict)
            self._emit_result(result_dict)

            is_success = False
            if result.status == SendResult.SUCCESS:
                self.contact_mgr.mark_sent(contact.id)
                item["status"] = "success"
                self._emit_log(f"  {contact.name} 발송 성공!", "success")
                is_success = True
            elif result.status == SendResult.FAILED_SAFETY:
                item["status"] = "failed"
                self._emit_log(f"  {contact.name}: {result.detail}", "error")
                self.save_queue_state()  # 중단 전 상태 저장
                break
            elif result.status == SendResult.FAILED_NOT_FOUND:
                item["status"] = "failed"
                self._emit_log(f"  {contact.name}: 검색 결과 없음 - 건너뜀", "warning")
            else:
                item["status"] = "failed"
                self._emit_log(f"  {contact.name}: {result.detail}", "error")

            self.current_index += 1

            # 10건마다 큐 상태 저장 (중간 저장)
            if self.current_index % 10 == 0:
                self.save_queue_state()

            # 안전 정지 확인
            if self.sender._stop_flag:
                break

            # 딜레이 (성공/실패 모두 적용 - 실패 시에도 쉬어야 탐지 회피)
            if self.current_index < self.total_count:
                # N명마다 긴 휴식 (배치 관리)
                if self.sender.should_rest():
                    rest = self.sender.take_rest()
                    self._emit_log(f"  배치 휴식: {rest:.0f}초 쉬는 중...", "info")

                delay = self.sender.random_delay()
                self._emit_log(f"  다음 발송까지 {delay:.0f}초 대기...")

        # 큐 상태 저장
        self.save_queue_state()

        # 완료/중단 처리
        failed_count = sum(1 for q in self.send_queue if q.get("status") == "failed")

        if self.sender._safety_error:
            self._emit_state(OrchestratorState.ERROR)
        elif self.current_index >= self.total_count:
            self._emit_state(OrchestratorState.COMPLETED)
            if failed_count == 0:
                self.clear_queue_state()  # 전원 성공 시 큐 삭제
        else:
            self._emit_state(OrchestratorState.PAUSED)

        self._emit_log("=" * 40)
        stats = self.report.get_statistics()
        self._emit_log(f"총 {stats['total']}명 | "
                       f"성공 {stats['success']}명 | "
                       f"실패 {stats['failed']}명 | "
                       f"성공률 {stats['success_rate']}%")
        if failed_count > 0:
            self._emit_log(
                f"실패 {failed_count}건 → 하단의 '↻ 실패 재발송' 버튼으로 재시도 가능"
            )
        self._emit_log("=" * 40)

        log_path = self.report.save_session_log()
        self._emit_log(f"로그 저장: {log_path}")

    def pause_sending(self):
        """발송 일시정지"""
        if self.sender:
            self.sender.stop()
            self._emit_log("발송 일시정지 요청됨")

    def resume_sending(self):
        """발송 재개"""
        if self.state == OrchestratorState.PAUSED:
            self.sender.resume()
            self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
            self._send_thread.start()
            self._emit_log("발송 재개!")

    def stop_sending(self):
        """발송 완전 중지 - 상태 완전 초기화"""
        if self.sender:
            self.sender.stop()
            # 플래그 초기화 → 다음 발송 시 재시작 가능
            self.sender._stop_flag = False
            self.sender._safety_error = None
        self.current_index = 0
        self.send_queue = []
        self.state = OrchestratorState.IDLE
        self._emit_state(OrchestratorState.IDLE)
        self._emit_log("발송 중지됨. 큐가 초기화되었습니다.")

    # -- 리포트 --

    # -- 세종텔레콤 연동 --

    def init_sejong(self, config_dict: dict = None) -> dict:
        """세종텔레콤 DB 연결 초기화"""
        try:
            sejong_cfg = config_dict or self.config.get("sejong", {})
            sc = SejongConfig(sejong_cfg)
            self.sejong_sender = SejongSender(sc)
            result = self.sejong_sender.test_connection()
            if result["success"]:
                self._emit_log(f"세종텔레콤 DB 연결 성공: {result['message']}")
            else:
                self._emit_log(f"세종텔레콤 DB 연결 실패: {result['message']}", "error")
            return result
        except Exception as e:
            self._emit_log(f"세종텔레콤 초기화 실패: {e}", "error")
            return {"success": False, "message": str(e)}

    def start_sejong_sending(self):
        """세종텔레콤(알림톡/SMS) 발송 시작 (별도 스레드)"""
        if self.state == OrchestratorState.SENDING:
            self._emit_log("이미 발송 중입니다.", "warning")
            return
        if not self.send_queue:
            self._emit_log("발송할 대상이 없습니다.", "warning")
            return
        if not self.sejong_sender:
            self._emit_log("세종텔레콤 DB 연결이 필요합니다.", "error")
            return

        self.current_index = 0
        self._send_thread = threading.Thread(target=self._sejong_send_loop, daemon=True)
        self._send_thread.start()

    def _sejong_send_loop(self):
        """세종텔레콤 발송 루프"""
        self._emit_state(OrchestratorState.SENDING)
        self.report.start_session()
        self._emit_log("=" * 40)
        method_label = "알림톡" if self.send_method == "alimtalk" else "SMS/LMS"
        self._emit_log(f"{method_label} 발송 시작! (세종텔레콤)")
        self._emit_log("=" * 40)

        sejong_cfg = self.config.get("sejong", {})
        template_code = sejong_cfg.get("kakao", {}).get("template_code", "")

        while self.current_index < self.total_count:
            item = self.send_queue[self.current_index]
            contact = item["contact"]
            message = item["message"]

            self._emit_progress(self.current_index + 1, self.total_count, contact.name)
            self._emit_log(f"[{self.current_index + 1}/{self.total_count}] "
                           f"{contact.name}에게 {method_label} 발송 중...")

            phone = contact.phone
            if not phone:
                result_dict = {
                    "contact_name": contact.name, "phone": "",
                    "status": "failed", "detail": "전화번호 없음"
                }
                self.report.add_result(result_dict)
                self._emit_result(result_dict)
                self._emit_log(f"  {contact.name}: 전화번호 없음 - 건너뜀", "warning")
                self.current_index += 1
                continue

            # 발송 방법에 따라 분기
            if self.send_method == "alimtalk":
                result = self.sejong_sender.send_alimtalk(
                    phone=phone, message=message,
                    template_code=template_code,
                    contact_name=contact.name
                )
            else:  # sms
                result = self.sejong_sender.send_auto(
                    phone=phone, message=message,
                    contact_name=contact.name
                )

            result_dict = result.to_dict()
            # 통일된 status 키
            result_dict["status"] = "success" if result.status == SejongSendResult.SUCCESS else "failed"
            self.report.add_result(result_dict)
            self._emit_result(result_dict)

            if result.status == SejongSendResult.SUCCESS:
                self.contact_mgr.mark_sent(contact.id)
                self._emit_log(f"  {contact.name} 접수 성공! ({result.detail})", "success")
            else:
                self._emit_log(f"  {contact.name}: {result.detail}", "error")

            self.current_index += 1

        # 완료
        self._emit_state(OrchestratorState.COMPLETED)
        self._emit_log("=" * 40)
        stats = self.report.get_statistics()
        self._emit_log(f"총 {stats['total']}명 | "
                       f"성공 {stats['success']}명 | "
                       f"실패 {stats['failed']}명 | "
                       f"성공률 {stats['success_rate']}%")
        self._emit_log("=" * 40)
        log_path = self.report.save_session_log()
        self._emit_log(f"로그 저장: {log_path}")

    def get_current_stats(self) -> dict:
        """현재 발송 통계"""
        return self.report.get_statistics()

    def export_report(self, filepath: str = None) -> str:
        """리포트 엑셀 내보내기"""
        return self.report.export_report_excel(filepath)

    def get_send_history(self, limit: int = 10) -> list:
        """최근 발송 이력"""
        return self.report.get_history(limit)

    # -- 발송 큐 저장/복원 (이어서 보내기) --

    def _queue_state_path(self) -> Path:
        return self.base_dir / "data" / "send_queue_state.json"

    def save_queue_state(self):
        """현재 발송 큐 상태를 파일에 저장 (이어서 보내기용)"""
        if not self.send_queue:
            return
        state = {
            "current_index": self.current_index,
            "total_count": self.total_count,
            "send_method": self.send_method,
            "queue": [
                {
                    "contact_id": item["contact"].id,
                    "contact_name": item["contact"].name,
                    "message": item["message"],
                    "image_path": item.get("image_path"),
                    "status": item.get("status", "pending"),  # pending/success/failed
                }
                for item in self.send_queue
            ]
        }
        path = self._queue_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        self._emit_log(f"발송 큐 저장: {self.current_index}/{self.total_count}")

    def load_queue_state(self) -> bool:
        """저장된 발송 큐 복원 (이어서 보내기)"""
        path = self._queue_state_path()
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)

            self.send_queue = []
            for item in state.get("queue", []):
                contact = self.contact_mgr.get_by_name(item["contact_name"])
                if not contact:
                    continue
                self.send_queue.append({
                    "contact": contact,
                    "message": item["message"],
                    "image_path": item.get("image_path"),
                    "status": item.get("status", "pending"),
                })

            self.current_index = state.get("current_index", 0)
            self.total_count = len(self.send_queue)
            self.send_method = state.get("send_method", "kakao_bot")

            # 이미 완료된 건 건너뛰기 (current_index 이전은 완료)
            pending = sum(1 for i, q in enumerate(self.send_queue)
                          if i >= self.current_index and q.get("status") != "success")

            self._emit_log(f"발송 큐 복원: {self.current_index}/{self.total_count} "
                           f"(미발송 {pending}건)")
            return True
        except Exception as e:
            self._emit_log(f"발송 큐 복원 실패: {e}", "error")
            return False

    def clear_queue_state(self):
        """저장된 큐 상태 삭제"""
        path = self._queue_state_path()
        if path.exists():
            path.unlink()

    def prepare_unsent_queue(self, category: str, template_content: str,
                             image_path: str = None, days: int = 0,
                             template_contents: list = None) -> list[dict]:
        """
        미발송자만 발송 큐 준비

        Args:
            category: 카테고리
            template_content: 메시지 템플릿
            days: N일 이내 보낸 사람 제외 (0=오늘만 체크)
        """
        if days > 0:
            contacts = self.contact_mgr.get_not_sent_within_days(days, category)
        else:
            contacts = self.contact_mgr.get_not_sent_today(category)

        self.send_queue = []
        for contact in contacts:
            if template_contents and len(template_contents) > 1:
                message = self.message_engine.substitute_random(
                    template_contents, contact.to_dict()
                )
            else:
                message = self.message_engine.substitute(
                    template_content, contact.to_dict()
                )
            self.send_queue.append({
                "contact": contact,
                "message": message,
                "image_path": image_path,
                "status": "pending",
            })

        self.total_count = len(self.send_queue)
        self.current_index = 0

        # 큐 상태 저장
        self.save_queue_state()

        total_in_cat = len(self.contact_mgr.get_by_category(category))
        skipped = total_in_cat - self.total_count
        self._emit_log(f"발송 큐: {self.total_count}명 (전체 {total_in_cat}명 중 "
                       f"{skipped}명 이미 발송 → 제외)")

        return [
            {
                "name": item["contact"].name,
                "category": item["contact"].category,
                "message": item["message"],
                "send_count": item["contact"].send_count,
                "last_sent": item["contact"].last_sent,
            }
            for item in self.send_queue
        ]

    def retry_failed(self) -> int:
        """실패한 건만 재발송 큐로 재구성.

        앱 재시작 후에도 동작: 메모리 큐가 비어있으면 마지막으로 디스크에 저장된
        큐 상태(`data/send_queue_state.json`)를 자동 복원한 뒤 실패 건을 추출.
        """
        # 메모리 큐 비어있으면 디스크에 저장된 마지막 큐 복원 시도
        if not self.send_queue:
            if not self.load_queue_state():
                self._emit_log("재발송할 발송 이력이 없습니다.")
                return 0
            self._emit_log("이전 발송 큐를 복원했습니다.")

        failed_items = []
        for item in self.send_queue:
            if item.get("status") in ("failed", "pending"):
                item["status"] = "pending"
                failed_items.append(item)

        if not failed_items:
            self._emit_log("재발송할 실패 건이 없습니다.")
            return 0

        self.send_queue = failed_items
        self.total_count = len(self.send_queue)
        self.current_index = 0
        self.save_queue_state()
        self._emit_log(f"실패 {self.total_count}건 재발송 큐 준비 완료")
        return self.total_count

    # ── 카톡 친구탭 OCR 자동화 ──

    @property
    def kakao_friends(self):
        """KakaoFriends lazy 초기화. KakaoWin32, OCR, ScreenCapture 공유."""
        if getattr(self, "_kakao_friends", None) is None:
            from core.kakao_friends import KakaoFriends
            from core.kakao_win32 import KakaoWin32
            from core.ocr_engine import OCREngine

            # sender가 이미 초기화돼 있으면 그 win32 공유, 아니면 새로 생성
            if self.sender and self.sender.win32:
                win32 = self.sender.win32
            else:
                win32 = KakaoWin32()
                win32.find_main_window()

            ocr = OCREngine()
            self._kakao_friends = KakaoFriends(win32, ocr, self.screen_capture)
        return self._kakao_friends

    def seed_contacts_from_kakao(self, max_count: int = 1000,
                                    on_progress=None,
                                    should_stop=None) -> dict:
        """카톡 친구탭 OCR 으로 전체 친구 자동 수집 → 연락처 DB 시드.

        주로 첫 실행 시 (주소록 비어있을 때) 호출.
        기존 친구는 중복 추가 안 함 (이름 일치 = duplicate).

        Returns: {ok, added, duplicates, ocr_failed, names, reason}
        """
        self._emit_log("=" * 40)
        self._emit_log("📥 카톡 친구 자동 수집 시작 (주소록 시드)")
        try:
            result = self.kakao_friends.collect_friends_to_addressbook(
                contact_manager=self.contact_mgr,
                category="kakao_friend",
                dry_run=False,  # 실제 저장
                max_count=max_count,
                on_progress=on_progress,
                should_stop=should_stop,
            )
            if result.get("ok"):
                self._emit_log(
                    f"✅ 친구 수집 완료: {result['added']}명 추가, "
                    f"{result['duplicates']}명 중복, "
                    f"{result['ocr_failed']}명 OCR 실패",
                    "info",
                )
            else:
                self._emit_log(
                    f"❌ 친구 수집 실패: {result.get('reason')}", "error"
                )
            return result
        except Exception as e:
            self._emit_log(f"친구 수집 예외: {e}", "error")
            return {"ok": False, "reason": str(e), "added": 0,
                    "duplicates": 0, "ocr_failed": 0, "names": []}

    def _sync_birthday_to_contacts(self, targets: list[dict],
                                     create_new: bool = False) -> dict:
        """카톡 OCR 으로 발견된 '어제/오늘/내일 생일자' 를 연락처 DB 에 반영.

        발송은 오늘만(send_birthday_messages 내부 로직)이지만 DB 채움은 ±1일
        모두 처리 → 매일 실행 시 3일치 동시 수집 (약 120일이면 1년치 채워짐).

        매칭 정책:
        - 이름 정확 일치 (공백 무시)
        - 빈 birthday → 해당 일자 MM-DD 채움
        - 이미 birthday 있으면 변경 없음
        - 미매칭: create_new=True 면 새 연락처 생성, False 면 스킵

        Returns: {updated, created, skipped_already_set, skipped_no_match}
        """
        from datetime import datetime, timedelta
        now = datetime.now()
        DAY_MMDD = {
            "today": now.strftime("%m-%d"),
            "yesterday": (now - timedelta(days=1)).strftime("%m-%d"),
            "tomorrow": (now + timedelta(days=1)).strftime("%m-%d"),
        }

        contacts = self.contact_mgr.get_all()
        by_name = {c.name.replace(" ", ""): c for c in contacts}

        updated = created = skipped_set = skipped_no_match = 0
        for t in targets:
            day = t.get("day")
            mmdd = DAY_MMDD.get(day)
            if not mmdd:
                continue  # 알 수 없는 day 라벨은 스킵
            name_raw = (t.get("name") or "").strip()
            if not name_raw:
                continue
            key = name_raw.replace(" ", "")
            existing = by_name.get(key)
            if existing:
                if not existing.birthday:
                    existing.birthday = mmdd
                    if not existing.memo:
                        existing.memo = "카톡에서 생일 자동 수집"
                    updated += 1
                else:
                    skipped_set += 1
            elif create_new:
                from core.contact_manager import Contact
                c = Contact(
                    name=name_raw, category="kakao_friend",
                    birthday=mmdd,
                    memo="카톡 생일자 자동 추가",
                )
                self.contact_mgr.contacts.append(c)
                by_name[key] = c
                created += 1
            else:
                skipped_no_match += 1
        if updated or created:
            self.contact_mgr.save()
        return {
            "updated": updated, "created": created,
            "skipped_already_set": skipped_set,
            "skipped_no_match": skipped_no_match,
        }

    def run_kakao_birthday_send(self, template_content: str = None,
                                  template_id: str = None,
                                  image_path: str = None,
                                  dry_run: bool = True,
                                  daily_limit: int = 50) -> dict:
        """
        카톡 친구탭 OCR 기반 오늘 생일자 자동 발송.

        Args:
            template_content: 메시지 본문 (우선)
            template_id: 템플릿 ID (template_content 가 없을 때 사용)
            image_path: 이미지 첨부 경로 (선택)
            dry_run: True (기본) 면 발송 시뮬레이션만
            daily_limit: 일일 발송 한도

        Returns:
            send_birthday_messages() 결과 dict
        """
        # 템플릿 결정
        if not template_content and template_id:
            tpl = self.message_engine.get_template_by_id(template_id)
            if tpl:
                template_content = tpl.content
                if not image_path:
                    image_path = tpl.image_path or None

        if not template_content:
            self._emit_log("카톡 생일 발송: 템플릿이 지정되지 않았습니다.", "error")
            return {"ok": False, "reason": "템플릿 없음", "sent": 0,
                    "skipped": 0, "errors": [], "targets": [], "dry_run": dry_run}

        self._emit_state(OrchestratorState.SENDING)
        self._emit_log("=" * 40)
        self._emit_log(f"🎂 카톡 친구탭 생일 발송 시작 (dry_run={dry_run})")

        def progress_cb(target, action, idx):
            name = target.get("name", "?")
            if action == "dry_run_sent":
                self._emit_log(f"  [{idx+1}] {name} → 시뮬레이션 발송")
            elif action == "sent":
                self._emit_log(f"  [{idx+1}] {name} → 발송 완료")
            elif action == "skip_not_today":
                self._emit_log(f"  [{idx+1}] {name} → 스킵 (오늘 생일 아님)")
            elif action.startswith("error"):
                self._emit_log(f"  [{idx+1}] {name} → 실패 ({action})", "error")
            self._emit_progress(idx + 1, 0, name)

        result = self.kakao_friends.send_birthday_messages(
            template_content=template_content,
            image_path=image_path,
            dry_run=dry_run,
            daily_limit=daily_limit,
            on_progress=progress_cb,
        )

        if result["ok"]:
            mode = "DRY RUN" if dry_run else "실발송"
            self._emit_log(f"✅ {mode} 완료: 발송 {result['sent']}, "
                           f"스킵 {result['skipped']}, 오류 {len(result['errors'])}")
            self._emit_state(OrchestratorState.COMPLETED)
        else:
            self._emit_log(f"❌ 실패: {result['reason']}", "error")
            self._emit_state(OrchestratorState.ERROR)

        # 카톡 OCR 으로 발견한 ±1일 생일자 → 연락처 DB 자동 반영
        # (발송은 오늘만 — send_birthday_messages 내부 로직)
        try:
            sync_cfg = self.config.get("auto_sync_birthday", {})
            if sync_cfg.get("enabled", True):
                sync = self._sync_birthday_to_contacts(
                    result.get("targets", []),
                    create_new=sync_cfg.get("create_new", False),
                )
                parts = []
                if sync["updated"]:
                    parts.append(f"빈 생일 {sync['updated']}명 채움")
                if sync["created"]:
                    parts.append(f"새 연락처 {sync['created']}명 추가")
                if sync["skipped_already_set"]:
                    parts.append(f"이미 입력됨 {sync['skipped_already_set']}명")
                if sync["skipped_no_match"]:
                    parts.append(f"미매칭 {sync['skipped_no_match']}명")
                if parts:
                    self._emit_log("📝 연락처 DB 동기화: " + ", ".join(parts))
        except Exception as e:
            self._emit_log(f"연락처 동기화 실패 (계속 진행): {e}", "warning")

        # 결과를 리포트로
        try:
            self._save_kakao_run_report("birthday", result)
        except Exception as e:
            self._emit_log(f"리포트 저장 실패: {e}", "warning")

        return result

    def run_kakao_friends_sync(self, category: str = "kakao_friend",
                                 dry_run: bool = True,
                                 max_count: int = 1000,
                                 on_progress=None,
                                 should_stop=None) -> dict:
        """
        카톡 친구목록 자동 수집 → ContactManager 저장.

        Args:
            category: 저장 시 부여할 카테고리 (기본: "kakao_friend")
            dry_run: True (기본) 면 OCR 만, 저장 X
            max_count: 최대 수집 친구 수 (안전장치)

        Returns:
            collect_friends_to_addressbook() 결과 dict
        """
        self._emit_state(OrchestratorState.SENDING)
        self._emit_log("=" * 40)
        self._emit_log(f"👥 카톡 친구목록 동기화 시작 (dry_run={dry_run})")

        def progress_cb(target, action, idx):
            name = target.get("name", "?")
            if action == "added":
                self._emit_log(f"  [{idx+1}] + {name}")
            elif action == "duplicate":
                self._emit_log(f"  [{idx+1}] = {name} (중복)")
            elif action == "dry_run_collected":
                self._emit_log(f"  [{idx+1}] · {name}")
            elif action == "ocr_failed":
                pass  # 너무 많은 로그 방지
            if (idx + 1) % 10 == 0:
                self._emit_progress(idx + 1, max_count, name)
            # UI 콜백 외부 전달 (다이얼로그 라이브 갱신용)
            if on_progress:
                on_progress(target, action, idx)

        result = self.kakao_friends.collect_friends_to_addressbook(
            contact_manager=self.contact_mgr,
            category=category,
            dry_run=dry_run,
            max_count=max_count,
            on_progress=progress_cb,
            should_stop=should_stop,
        )

        if result["ok"]:
            if dry_run:
                self._emit_log(f"✅ DRY RUN 완료: {len(result['names'])}명 수집 "
                               f"(OCR 실패 {result['ocr_failed']}명)")
            else:
                self._emit_log(f"✅ 동기화 완료: 추가 {result['added']}, "
                               f"중복 {result['duplicates']}, "
                               f"OCR실패 {result['ocr_failed']}")
            self._emit_state(OrchestratorState.COMPLETED)
        else:
            self._emit_log(f"❌ 실패: {result['reason']}", "error")
            self._emit_state(OrchestratorState.ERROR)

        try:
            self._save_kakao_run_report("friends_sync", result)
        except Exception as e:
            self._emit_log(f"리포트 저장 실패: {e}", "warning")

        return result

    def _save_kakao_run_report(self, kind: str, result: dict):
        """카톡 자동화 결과를 logs/kakao_runs/ 에 JSON 저장 (간단한 audit log)"""
        log_dir = self.base_dir / "logs" / "kakao_runs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = log_dir / f"{kind}_{ts}.json"

        # row_image, prev_image 등 직렬화 불가 객체 제거
        def _clean(obj):
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()
                         if k not in ("row_image", "prev_image", "cur_image")}
            if isinstance(obj, list):
                return [_clean(x) for x in obj]
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

        cleaned = _clean(result)
        cleaned["kind"] = kind
        cleaned["timestamp"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
