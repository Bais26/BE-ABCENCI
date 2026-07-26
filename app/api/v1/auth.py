from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from jose import jwt, ExpiredSignatureError, JWTError
from app.core.database import get_db
from app.models import User, UserRole, SubDivision, KaryawanDetail
from app.schemas.auth import *
from app.utils.security import *
from app.core.email import get_mail_client
from app.core.config import settings
from fastapi_mail import MessageSchema

router = APIRouter()

# @router.get("/me", response_model=UserWithDetailResponse)
# def get_my_profile(
#     current_user: User = Depends(get_current_user)
# ):
#     return current_user


@router.post("/save-token")
def save_token(
    data: FCMTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.fcm_token = data.fcm_token
    db.commit()

    return {
        "message": "FCM token saved"
    }

@router.get("/me", response_model=UserWithDetailResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ambil data user + karyawan_detail jika ada.
    Tidak melempar 404 jika karyawan_detail kosong.
    """

    user = db.query(User).options(
        joinedload(User.karyawan_detail)
        .joinedload(KaryawanDetail.subdivision)
        .joinedload(SubDivision.division)
    ).filter(User.id == current_user.id).first()

    if not user:
        # This case should ideally not happen if token is valid, but as a safeguard:
        raise HTTPException(status_code=404, detail="User not found")

    # Cukup kembalikan objek yang dibuat dari ORM.
    # Pydantic akan secara otomatis membuat struktur JSON yang bersarang dengan benar.
    return UserWithDetailResponse.from_orm(user)

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
    db.flush() 
    karyawan = KaryawanDetail(
    user_id=user.id
    )

    db.add(karyawan)
    db.commit()
    db.refresh(user)


    token = create_token({"email": user.email}, 30)

    fm = get_mail_client()
    verify_url = build_url(settings.FRONTEND_URL, "/api/v1/auth/verify") + f"?token={token}"

    message = MessageSchema(
        subject="Verifikasi Email",
        recipients=[user.email],
        body=(
            f"Halo {user.full_name},\n\n"
            f"Klik link berikut untuk verifikasi akun kamu:\n"
            f"{verify_url}\n\n"
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
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError:
        raise HTTPException(400, "Token sudah kedaluwarsa")
    except JWTError:
        raise HTTPException(400, "Token tidak valid")

    user = db.query(User).filter(User.email == payload.get("email")).first()
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

    # Load division and subdivision info
    user_with_details = db.query(User).options(
        joinedload(User.karyawan_detail).joinedload(KaryawanDetail.subdivision).joinedload(SubDivision.division)
    ).filter(User.id == user.id).one()

    karyawan = user_with_details.karyawan_detail
    division_name = karyawan.subdivision.division.name if karyawan and karyawan.subdivision and karyawan.subdivision.division else None

    token = create_token(
        {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
        },
        settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return {
    "access_token": token,
    "token_type": "bearer",
    "user": {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "divisi": division_name,
    },
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

    token = create_token({"email": user.email}, 15)   # ✅ diindentasi sejajar

    fm = get_mail_client()
    reset_url = build_url(settings.FRONTEND_URL, "/reset-password") + f"?token={token}"

    message = MessageSchema(
        subject="Reset Password",
        recipients=[user.email],
        body=(
            f"Halo {user.full_name},\n\n"
            f"Klik link berikut untuk reset password:\n"
            f"{reset_url}\n\n"
            f"Link berlaku 15 menit."
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

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Token tidak valid atau tidak berisi email.")
    except ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Tautan reset password sudah kedaluwarsa. Silakan minta yang baru.")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token tidak valid atau rusak.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    user.password = hash_password(data.password)
    db.commit()

    return {"message": "Password berhasil direset"}

# RESEND EMAIL VERIFICATION
@router.post("/resend-verification")
async def resend_verification(
    data: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    if user.is_active:
        raise HTTPException(400, "Email sudah diverifikasi")

    token = create_token({"email": user.email}, 30)

    fm = get_mail_client()
    verify_url = build_url(settings.FRONTEND_URL, "/api/v1/auth/verify") + f"?token={token}"

    message = MessageSchema(
        subject="Verifikasi Email",
        recipients=[user.email],
        body=(
            f"Halo {user.full_name},\n\n"
            f"Klik link berikut untuk verifikasi akun kamu:\n"
            f"{verify_url}\n\n"
            f"Abaikan jika ini bukan kamu."
        ),
        subtype="plain"
    )

    await fm.send_message(message)

    return {
        "message": "Email verifikasi berhasil dikirim ulang"
    }
