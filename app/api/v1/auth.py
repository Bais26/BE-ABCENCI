from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import *
from app.utils.security import *
from app.core.email import get_mail_client

from fastapi_mail import MessageSchema

router = APIRouter()

# REGISTER
@router.post("/register")
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    if data.password != data.confirm_password:
        raise HTTPException(400, "Password dan konfirmasi password tidak sama")

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email sudah terdaftar")

    user = User(
        full_name=data.full_name,
        email=data.email,
        password=hash_password(data.password),
        is_active=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token({"email": user.email}, 30)

    fm = get_mail_client()

    message = MessageSchema(
        subject="Verifikasi Email",
        recipients=[user.email],
        body=(
            f"Halo {user.full_name},\n\n"
            f"Klik link berikut untuk verifikasi akun kamu:\n"
            f"http://localhost:8000/api/v1/auth/verify?token={token}\n\n"
            f"Abaikan jika ini bukan kamu."
        ),
        subtype="plain"
    )

    await fm.send_message(message)

    return {
        "message": "Registrasi berhasil. Silakan cek email untuk verifikasi."
    }


# VERIFY EMAIL
@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        raise HTTPException(400, "Token tidak valid")

    user = db.query(User).filter(User.email == payload["email"]).first()
    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    user.is_active = True
    db.commit()

    return {"message": "Email berhasil diverifikasi"}


# LOGIN
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(401, "Email / password salah")

    if not user.is_active:
        raise HTTPException(403, "Email belum diverifikasi")

    token = create_token(
        {"user_id": user.id},
        ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# FORGOT PASSWORD
@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(404, "Email tidak ditemukan")

    token = create_token({"email": user.email}, 15)

    fm = get_mail_client()

    message = MessageSchema(
        subject="Reset Password",
        recipients=[user.email],
        body=(
            f"Klik link berikut untuk reset password:\n"
            f"http://localhost:3000/reset-password?token={token}"
        ),
        subtype="plain"
    )

    await fm.send_message(message)

    return {"message": "Link reset password dikirim ke email"}


# RESET PASSWORD
@router.post("/reset-password")
def reset_password(
    token: str,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    if data.password != data.confirm_password:
        raise HTTPException(400, "Password tidak sama")

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user = db.query(User).filter(User.email == payload["email"]).first()

    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    user.password = hash_password(data.password)
    db.commit()

    return {"message": "Password berhasil direset"}
