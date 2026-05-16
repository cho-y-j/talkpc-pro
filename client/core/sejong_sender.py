"""
SejongSender - 세종텔레콤 MessagingAgent DB 연동 발송 모듈
msg_queue 테이블에 INSERT → MessagingAgent가 자동 발송

지원:
  - SMS (단문, msg_type='1')
  - LMS (장문, msg_type='3', filecnt=0)
  - MMS (사진, msg_type='3', filecnt>0)
  - 알림톡 (msg_type='6')
  - 친구톡 (msg_type='7')
"""

import json
import time
from datetime import datetime
from typing import Optional

try:
    import pymysql
except ImportError:
    pymysql = None


class SejongConfig:
    """세종텔레콤 연동 설정"""

    def __init__(self, config: dict = None):
        config = config or {}
        db = config.get("db", {})
        self.db_host = db.get("host", "localhost")
        self.db_port = db.get("port", 3306)
        self.db_name = db.get("name", "sms")
        self.db_user = db.get("user", "")
        self.db_password = db.get("password", "")
        self.db_charset = db.get("charset", "utf8mb4")

        kakao = config.get("kakao", {})
        self.sender_key = kakao.get("sender_key", "")
        self.callback = kakao.get("callback", "")  # 발신번호

    def to_dict(self) -> dict:
        return {
            "db": {
                "host": self.db_host,
                "port": self.db_port,
                "name": self.db_name,
                "user": self.db_user,
                "password": self.db_password,
                "charset": self.db_charset,
            },
            "kakao": {
                "sender_key": self.sender_key,
                "callback": self.callback,
            }
        }


class SejongSendResult:
    """발송 결과"""
    SUCCESS = "success"
    FAILED_DB = "db_error"
    FAILED_CONFIG = "config_error"

    def __init__(self, contact_name: str, phone: str, status: str,
                 mseq: int = None, detail: str = ""):
        self.contact_name = contact_name
        self.phone = phone
        self.status = status
        self.mseq = mseq
        self.detail = detail
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "contact_name": self.contact_name,
            "phone": self.phone,
            "status": self.status,
            "mseq": self.mseq,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class SejongSender:
    """세종텔레콤 MessagingAgent DB 연동 발송기"""

    # msg_type 상수
    MSG_TYPE_SMS = "1"
    MSG_TYPE_LMS_MMS = "3"
    MSG_TYPE_ALIMTALK = "6"
    MSG_TYPE_FRIENDTALK = "7"

    def __init__(self, config: SejongConfig):
        if pymysql is None:
            raise ImportError("pymysql이 설치되지 않았습니다. pip install pymysql")
        self.config = config
        self._conn = None

    def _get_connection(self):
        """DB 연결 (재사용)"""
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
                charset=self.config.db_charset,
                autocommit=True,
                connect_timeout=10,
            )
        return self._conn

    def test_connection(self) -> dict:
        """DB 연결 테스트"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                # msg_queue 테이블 존재 확인
                cur.execute("SHOW TABLES LIKE 'msg_queue'")
                has_table = cur.fetchone() is not None
            return {
                "success": True,
                "has_table": has_table,
                "message": "DB 연결 성공" + (" (msg_queue 테이블 확인됨)" if has_table else " (msg_queue 테이블 없음 - 생성 필요)")
            }
        except Exception as e:
            return {"success": False, "message": f"DB 연결 실패: {e}"}

    def close(self):
        """DB 연결 종료"""
        if self._conn and self._conn.open:
            self._conn.close()
            self._conn = None

    # ── SMS/LMS 발송 ──

    def send_sms(self, phone: str, message: str, callback: str = None,
                 contact_name: str = "") -> SejongSendResult:
        """SMS 단문 발송 (90바이트 이하)"""
        cb = callback or self.config.callback
        if not cb:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_CONFIG,
                                    detail="발신번호(callback) 미설정")
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO msg_queue (
                        msg_type, dstaddr, callback, text, request_time
                    ) VALUES (
                        %s, %s, %s, %s, NOW()
                    )
                """
                cur.execute(sql, (self.MSG_TYPE_SMS, phone, cb, message))
                mseq = cur.lastrowid
            return SejongSendResult(contact_name, phone, SejongSendResult.SUCCESS,
                                    mseq=mseq, detail=f"SMS 접수 (mseq={mseq})")
        except Exception as e:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_DB,
                                    detail=str(e))

    def send_lms(self, phone: str, subject: str, message: str,
                 callback: str = None, contact_name: str = "") -> SejongSendResult:
        """LMS 장문 발송 (2000바이트 이하)"""
        cb = callback or self.config.callback
        if not cb:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_CONFIG,
                                    detail="발신번호(callback) 미설정")
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO msg_queue (
                        msg_type, dstaddr, callback, subject, text, request_time
                    ) VALUES (
                        %s, %s, %s, %s, %s, NOW()
                    )
                """
                cur.execute(sql, (self.MSG_TYPE_LMS_MMS, phone, cb, subject, message))
                mseq = cur.lastrowid
            return SejongSendResult(contact_name, phone, SejongSendResult.SUCCESS,
                                    mseq=mseq, detail=f"LMS 접수 (mseq={mseq})")
        except Exception as e:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_DB,
                                    detail=str(e))

    def send_auto(self, phone: str, message: str, subject: str = "알림",
                  callback: str = None, contact_name: str = "") -> SejongSendResult:
        """SMS/LMS 자동 판별 발송 (90바이트 초과시 LMS)"""
        byte_len = len(message.encode("euc-kr", errors="replace"))
        if byte_len <= 90:
            return self.send_sms(phone, message, callback, contact_name)
        else:
            return self.send_lms(phone, subject, message, callback, contact_name)

    # ── 알림톡 발송 ──

    def send_alimtalk(self, phone: str, message: str,
                      template_code: str,
                      buttons: list = None,
                      fallback_message: str = None,
                      fallback_type: str = "sms",
                      callback: str = None,
                      contact_name: str = "") -> SejongSendResult:
        """
        카카오 알림톡 발송

        Args:
            phone: 수신자 전화번호
            message: 알림톡 메시지 (템플릿 변수 치환 완료된)
            template_code: 카카오 승인 템플릿 코드
            buttons: 버튼 리스트 [{"name": "...", "type": "WL", "url_mobile": "...", "url_pc": "..."}]
            fallback_message: 카카오 실패시 대체 문자 내용 (None이면 message 사용)
            fallback_type: 대체발송 타입 ("none", "sms", "lms", "mms")
            callback: 발신번호
            contact_name: 연락처 이름 (로깅용)
        """
        sender_key = self.config.sender_key
        if not sender_key:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_CONFIG,
                                    detail="sender_key 미설정")

        cb = callback or self.config.callback
        if not cb:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_CONFIG,
                                    detail="발신번호(callback) 미설정")

        # k_next_type: 0=카카오only, 7=SMS대체, 8=LMS대체, 9=MMS대체
        next_type_map = {"none": 0, "sms": 7, "lms": 8, "mms": 9}
        k_next_type = next_type_map.get(fallback_type, 7)

        # k_attach JSON 구성
        attach = {"message_type": "AT"}
        if buttons:
            attach["attachment"] = {"button": buttons}

        text2 = fallback_message or message  # 대체 발송 문자

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO msg_queue (
                        msg_type, dstaddr, callback, subject, text, text2,
                        request_time, k_template_code, k_next_type,
                        sender_key, k_at_send_type, k_attach
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        NOW(), %s, %s,
                        %s, %s, %s
                    )
                """
                cur.execute(sql, (
                    self.MSG_TYPE_ALIMTALK,
                    phone, cb, "알림톡", message, text2,
                    template_code, k_next_type,
                    sender_key, "0",
                    json.dumps(attach, ensure_ascii=False)
                ))
                mseq = cur.lastrowid
            return SejongSendResult(contact_name, phone, SejongSendResult.SUCCESS,
                                    mseq=mseq, detail=f"알림톡 접수 (mseq={mseq})")
        except Exception as e:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_DB,
                                    detail=str(e))

    # ── 친구톡 발송 ──

    def send_friendtalk(self, phone: str, message: str,
                        buttons: list = None,
                        ad_flag: bool = False,
                        image_path: str = None,
                        fallback_message: str = None,
                        fallback_type: str = "sms",
                        callback: str = None,
                        contact_name: str = "") -> SejongSendResult:
        """카카오 친구톡 발송"""
        sender_key = self.config.sender_key
        if not sender_key:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_CONFIG,
                                    detail="sender_key 미설정")

        cb = callback or self.config.callback
        next_type_map = {"none": 0, "sms": 7, "lms": 8, "mms": 9}
        k_next_type = next_type_map.get(fallback_type, 7)

        # k_attach JSON
        attach = {"message_type": "FT"}
        if buttons:
            attach["attachment"] = {"button": buttons}
        if image_path:
            attach["message_type"] = "FI"
            if "attachment" not in attach:
                attach["attachment"] = {}
            attach["attachment"]["image"] = {
                "img_url": "%s",
                "img_link": ""
            }

        text2 = fallback_message or message
        filecnt = 1 if image_path else 0

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO msg_queue (
                        msg_type, dstaddr, callback, subject, text, text2,
                        request_time, k_next_type, sender_key,
                        k_ad_flag, k_attach,
                        filecnt, fileloc1
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        NOW(), %s, %s,
                        %s, %s,
                        %s, %s
                    )
                """
                cur.execute(sql, (
                    self.MSG_TYPE_FRIENDTALK,
                    phone, cb, "친구톡", message, text2,
                    k_next_type, sender_key,
                    "Y" if ad_flag else "N",
                    json.dumps(attach, ensure_ascii=False),
                    filecnt, image_path or ""
                ))
                mseq = cur.lastrowid
            return SejongSendResult(contact_name, phone, SejongSendResult.SUCCESS,
                                    mseq=mseq, detail=f"친구톡 접수 (mseq={mseq})")
        except Exception as e:
            return SejongSendResult(contact_name, phone, SejongSendResult.FAILED_DB,
                                    detail=str(e))

    # ── 발송 결과 조회 ──

    def check_result(self, mseq: int) -> dict:
        """발송 결과 조회 (msg_queue에서 stat 확인)"""
        try:
            conn = self._get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT mseq, stat, result, dstaddr, report_time "
                    "FROM msg_queue WHERE mseq = %s", (mseq,)
                )
                row = cur.fetchone()
                if not row:
                    # 결과 테이블에서 조회 (이동 후)
                    table = f"msg_result_{datetime.now().strftime('%Y%m')}"
                    try:
                        cur.execute(
                            f"SELECT mseq, stat, result, dstaddr, report_time "
                            f"FROM {table} WHERE mseq = %s", (mseq,)
                        )
                        row = cur.fetchone()
                    except Exception:
                        pass
                if row:
                    stat_map = {"0": "대기", "1": "송신중", "2": "송신완료", "3": "결과수신"}
                    return {
                        "found": True,
                        "mseq": row["mseq"],
                        "stat": stat_map.get(row["stat"], row["stat"]),
                        "result": row.get("result", ""),
                        "phone": row["dstaddr"],
                    }
                return {"found": False}
        except Exception as e:
            return {"found": False, "error": str(e)}
