"""
Scheduler - 예약 발송 및 생일/기념일 자동 발송 관리
백그라운드 스레드로 30초마다 체크
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


class ScheduledJob:
    """예약 발송 작업"""

    def __init__(self, scheduled_time: str, contact_ids: list[str],
                 template_content: str, image_path: str = None,
                 job_type: str = "manual", job_id: str = None,
                 status: str = "pending", recurring: str = "none"):
        self.id = job_id or f"job_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.scheduled_time = scheduled_time  # ISO format
        self.contact_ids = contact_ids
        self.template_content = template_content
        self.image_path = image_path
        self.job_type = job_type  # "manual" | "birthday" | "anniversary"
        self.status = status  # "pending" | "running" | "completed" | "cancelled" | "failed"
        # "none" = 1회성 / "daily" = 매일 같은 시간 반복
        self.recurring = recurring
        self.created_at = datetime.now().isoformat()
        self.result_summary = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scheduled_time": self.scheduled_time,
            "contact_ids": self.contact_ids,
            "template_content": self.template_content,
            "image_path": self.image_path,
            "job_type": self.job_type,
            "status": self.status,
            "recurring": self.recurring,
            "created_at": self.created_at,
            "result_summary": self.result_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledJob":
        job = cls(
            scheduled_time=data["scheduled_time"],
            contact_ids=data["contact_ids"],
            template_content=data["template_content"],
            image_path=data.get("image_path"),
            job_type=data.get("job_type", "manual"),
            job_id=data.get("id"),
            status=data.get("status", "pending"),
            recurring=data.get("recurring", "none"),
        )
        job.created_at = data.get("created_at", job.created_at)
        job.result_summary = data.get("result_summary", "")
        return job

    @property
    def is_due(self) -> bool:
        """실행 시간이 되었는지"""
        if self.status != "pending":
            return False
        try:
            target = datetime.fromisoformat(self.scheduled_time)
            return datetime.now() >= target
        except (ValueError, TypeError):
            return False

    @property
    def display_time(self) -> str:
        try:
            dt = datetime.fromisoformat(self.scheduled_time)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return self.scheduled_time


class Scheduler:
    """예약 발송 관리자"""

    CHECK_INTERVAL = 30  # 초

    def __init__(self, data_path: str, orchestrator=None):
        self.data_path = Path(data_path)
        self.orchestrator = orchestrator
        self.jobs: list[ScheduledJob] = []
        self.auto_send_settings: dict = {
            "enabled": False,
            # 발송 모드:
            #   "json"      — 기존 contacts.json 의 birthday 필드 기반 (수동 입력)
            #   "kakao_ocr" — 카톡 친구탭 OCR 기반 (자동 식별, 카톡 PC 띄워야 함)
            "mode": "json",
            "birthday_template_id": "",
            "anniversary_template_id": "",
            "send_hour": 9,
            "send_minute": 0,
        }

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_date_check = ""  # 날짜 체크 중복 방지
        self._on_job_executed: Optional[Callable] = None

        self.load()

    def on_job_executed(self, callback: Callable):
        """예약 실행 완료 콜백"""
        self._on_job_executed = callback

    # ── 저장/로드 ──

    def load(self):
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.jobs = [ScheduledJob.from_dict(j) for j in data.get("jobs", [])]
                # 디스크 값과 기본값 merge — 새 키 (mode 등) 가 추가돼도 기본값 유지
                saved_auto_send = data.get("auto_send", {})
                self.auto_send_settings = {**self.auto_send_settings, **saved_auto_send}
            except (json.JSONDecodeError, KeyError):
                pass

    def save(self):
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "jobs": [j.to_dict() for j in self.jobs],
            "auto_send": self.auto_send_settings,
        }
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 예약 관리 ──

    def add_job(self, scheduled_time: str, contact_ids: list[str],
                template_content: str, image_path: str = None,
                job_type: str = "manual",
                recurring: str = "none") -> ScheduledJob:
        job = ScheduledJob(
            scheduled_time=scheduled_time,
            contact_ids=contact_ids,
            template_content=template_content,
            image_path=image_path,
            job_type=job_type,
            recurring=recurring,
        )
        self.jobs.append(job)
        self.save()
        return job

    def cancel_job(self, job_id: str) -> bool:
        for job in self.jobs:
            if job.id == job_id and job.status == "pending":
                job.status = "cancelled"
                self.save()
                return True
        return False

    def get_pending_jobs(self) -> list[ScheduledJob]:
        return [j for j in self.jobs if j.status == "pending"]

    def get_all_jobs(self) -> list[ScheduledJob]:
        return self.jobs

    def cleanup_old_jobs(self, keep_days: int = 7):
        """오래된 완료/취소 작업 정리"""
        now = datetime.now()
        self.jobs = [
            j for j in self.jobs
            if j.status == "pending"
            or (now - datetime.fromisoformat(j.created_at)).days <= keep_days
        ]
        self.save()

    # ── 백그라운드 체커 ──

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _check_loop(self):
        while self._running:
            try:
                self._check_due_jobs()
                self._check_daily_auto_send()
            except Exception:
                pass
            time.sleep(self.CHECK_INTERVAL)

    def _check_due_jobs(self):
        """실행 시간이 된 작업 실행"""
        for job in self.jobs:
            if job.is_due:
                self._execute_job(job)

    def _execute_job(self, job: ScheduledJob):
        """예약 작업 실행"""
        if not self.orchestrator or not self.orchestrator.sender:
            job.status = "failed"
            job.result_summary = "카카오톡 초기화 안됨"
            self.save()
            return

        # 이미 발송 중이면 스킵 (다음 체크에서 재시도)
        from core.orchestrator import OrchestratorState
        if self.orchestrator.state == OrchestratorState.SENDING:
            return

        job.status = "running"
        self.save()

        try:
            # contact_ids → Contact 객체 리스트
            all_contacts = self.orchestrator.contact_mgr.get_all()
            contacts = [c for c in all_contacts if c.id in job.contact_ids]

            if not contacts:
                job.status = "failed"
                job.result_summary = "대상 연락처 없음"
                self.save()
                return

            # 큐 준비 및 발송
            self.orchestrator.prepare_custom_queue(
                contacts, job.template_content, image_path=job.image_path
            )
            self.orchestrator.start_sending()

            job.status = "completed"
            job.result_summary = f"{len(contacts)}명 발송 시작"

        except Exception as e:
            job.status = "failed"
            job.result_summary = str(e)

        self.save()

        # 매일 반복 예약 — 다음날 같은 시간으로 새 job 자동 등록
        if job.recurring == "daily" and job.status == "completed":
            try:
                from datetime import timedelta
                cur_time = datetime.fromisoformat(job.scheduled_time)
                next_time = cur_time + timedelta(days=1)
                self.add_job(
                    scheduled_time=next_time.isoformat(),
                    contact_ids=job.contact_ids,
                    template_content=job.template_content,
                    image_path=job.image_path,
                    job_type=job.job_type,
                    recurring="daily",
                )
            except Exception:
                pass

        if self._on_job_executed:
            self._on_job_executed(job)

    # ── 생일/기념일 자동 발송 ──

    def _check_daily_auto_send(self):
        """하루 1회 생일/기념일 체크"""
        if not self.auto_send_settings.get("enabled", False):
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        if self._last_date_check == today_str:
            return  # 오늘 이미 체크함

        # 설정된 발송 시간 확인
        now = datetime.now()
        send_hour = self.auto_send_settings.get("send_hour", 9)
        send_minute = self.auto_send_settings.get("send_minute", 0)

        if now.hour < send_hour or (now.hour == send_hour and now.minute < send_minute):
            return  # 아직 발송 시간 안됨

        self._last_date_check = today_str

        mode = self.auto_send_settings.get("mode", "json")
        if mode == "kakao_ocr":
            # 카톡 친구탭 OCR 으로 오늘 생일자 자동 식별 + 발송
            self._run_kakao_birthday()
            # kakao_ocr 모드는 기념일 OCR 안 함 (카톡엔 기념일 섹션 없음).
            # 기념일은 contacts.json 기반으로 그대로 동작.
            self._create_anniversary_jobs()
        else:
            # 기존: contacts.json birthday/anniversary 필드 기반 Job 큐
            self._create_birthday_jobs()
            self._create_anniversary_jobs()

    def _run_kakao_birthday(self):
        """카톡 OCR 모드 자동 발송 — 별도 스레드 (체크 루프 차단 방지)"""
        if not self.orchestrator:
            return

        template_id = self.auto_send_settings.get("birthday_template_id", "")
        if not template_id:
            self.orchestrator._emit_log(
                "⚠ 자동 발송 활성화됨이지만 [생일 메시지 템플릿] 미설정 — "
                "오늘 자동 발송 건너뜀. 설정 페이지에서 템플릿을 선택하세요.",
                "error",
            )
            return

        def runner():
            try:
                self.orchestrator.run_kakao_birthday_send(
                    template_id=template_id,
                    dry_run=False,  # 스케줄러 자동 실행은 실발송
                )
            except Exception as e:
                # 스케줄러 스레드 보호 — 예외 삼키고 로그만
                if hasattr(self.orchestrator, "_emit_log"):
                    self.orchestrator._emit_log(
                        f"카톡 자동발송 에러: {e}", "error"
                    )

        threading.Thread(target=runner, daemon=True).start()

    def _create_birthday_jobs(self):
        """오늘 생일인 연락처에 대해 자동 발송 Job 생성"""
        if not self.orchestrator:
            return

        template_id = self.auto_send_settings.get("birthday_template_id", "")
        if not template_id:
            self.orchestrator._emit_log(
                "⚠ 자동 발송 활성화됨이지만 [생일 메시지 템플릿] 미설정 — "
                "오늘 자동 발송 건너뜀. 설정 페이지에서 템플릿을 선택하세요.",
                "error",
            )
            return

        template = self.orchestrator.message_engine.get_template_by_id(template_id)
        if not template:
            return

        today_mmdd = datetime.now().strftime("%m-%d")
        contacts = self.orchestrator.contact_mgr.get_all()
        birthday_contacts = [c for c in contacts if getattr(c, 'birthday', '') == today_mmdd]

        if birthday_contacts:
            self.add_job(
                scheduled_time=datetime.now().isoformat(),
                contact_ids=[c.id for c in birthday_contacts],
                template_content=template.content,
                job_type="birthday",
            )

    def _create_anniversary_jobs(self):
        """오늘 기념일인 연락처에 대해 자동 발송 Job 생성"""
        if not self.orchestrator:
            return

        template_id = self.auto_send_settings.get("anniversary_template_id", "")
        if not template_id:
            # 기념일은 선택적이므로 활성+생일 템플릿만 있으면 OK.
            # 단, 기념일이 있는 연락처가 오늘 있는데 템플릿 미설정이면 경고.
            today_mmdd = datetime.now().strftime("%m-%d")
            has_today_anniv = any(
                getattr(c, "anniversary", "") == today_mmdd
                for c in self.orchestrator.contact_mgr.get_all()
            )
            if has_today_anniv:
                self.orchestrator._emit_log(
                    "⚠ 오늘 기념일 연락처가 있지만 [기념일 메시지 템플릿] "
                    "미설정 — 자동 발송 건너뜀.",
                    "warning",
                )
            return

        template = self.orchestrator.message_engine.get_template_by_id(template_id)
        if not template:
            return

        today_mmdd = datetime.now().strftime("%m-%d")
        contacts = self.orchestrator.contact_mgr.get_all()
        anniversary_contacts = [c for c in contacts if getattr(c, 'anniversary', '') == today_mmdd]

        if anniversary_contacts:
            self.add_job(
                scheduled_time=datetime.now().isoformat(),
                contact_ids=[c.id for c in anniversary_contacts],
                template_content=template.content,
                job_type="anniversary",
            )
