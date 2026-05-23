"""어드민 계정 조회/비번 리셋 도구.

사용법 (server 디렉토리에서):
    python admin_tool.py list
    python admin_tool.py reset <email> <new_password>
    python admin_tool.py promote <email>          # 기존 유저를 admin 으로 승격 (+ active)
"""
import sys
from sqlalchemy import select

from db import SessionLocal
from models import User
from models.user import USER_STATUS_ACTIVE
from security import hash_password


def cmd_list():
    db = SessionLocal()
    try:
        admins = db.scalars(select(User).where(User.is_admin == True)).all()  # noqa: E712
        if not admins:
            print("(어드민 계정 없음)")
            return
        print(f"{'EMAIL':<40} {'STATUS':<10} CREATED")
        for u in admins:
            print(f"{u.email:<40} {u.status:<10} {u.created_at}")
    finally:
        db.close()


def cmd_reset(email: str, new_password: str):
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            print(f"사용자 없음: {email}")
            sys.exit(1)
        user.password_hash = hash_password(new_password)
        db.commit()
        print(f"OK - {email} 비번 변경됨 (is_admin={user.is_admin}, status={user.status})")
    finally:
        db.close()


def cmd_promote(email: str):
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            print(f"사용자 없음: {email}")
            sys.exit(1)
        user.is_admin = True
        user.status = USER_STATUS_ACTIVE
        db.commit()
        print(f"OK - {email} -> is_admin=True, status=active")
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "reset" and len(sys.argv) == 4:
        cmd_reset(sys.argv[2], sys.argv[3])
    elif cmd == "promote" and len(sys.argv) == 3:
        cmd_promote(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
