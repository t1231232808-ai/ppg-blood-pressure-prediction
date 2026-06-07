import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.models.database import SessionLocal
from app.models.entities import User
from app.utils.jwt_util import hash_password


def ensure_admin(username: str = "admin", email: str = "admin@example.com", password: str = "admin123") -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role="admin",
                status=1,
            )
            db.add(user)
        else:
            user.email = email
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.status = 1
        db.commit()
    print(f"Admin ready: {username} / {password}")


if __name__ == "__main__":
    ensure_admin()
