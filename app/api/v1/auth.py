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
from fastapi.responses import HTMLResponse

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
    verify_url = build_url(settings.BACKEND_URL, "/api/v1/auth/verify") + f"?token={token}"

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
@router.get("/verify", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError:
        return _verify_page(
            success=False,
            title="Link Kedaluwarsa",
            message="Link verifikasi ini sudah tidak berlaku. Silakan minta link verifikasi baru dari aplikasi."
        )
    except JWTError:
        return _verify_page(
            success=False,
            title="Link Tidak Valid",
            message="Link verifikasi ini tidak valid atau rusak."
        )

    user = db.query(User).filter(User.email == payload.get("email")).first()
    if not user:
        return _verify_page(
            success=False,
            title="Akun Tidak Ditemukan",
            message="Akun dengan email ini tidak ditemukan."
        )

    user.is_active = True
    db.commit()

    return _verify_page(
        success=True,
        title="Email Berhasil Diverifikasi!",
        message="Akun kamu sudah aktif. Silakan kembali ke aplikasi dan login."
    )


def _verify_page(success: bool, title: str, message: str) -> str:
    color = "#22c55e" if success else "#ef4444"
    icon = "✓" if success else "✕"

    return f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0f172a;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 24px;
            }}
            .card {{
                background: #ffffff;
                border-radius: 20px;
                padding: 40px 28px;
                max-width: 380px;
                width: 100%;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            .icon-circle {{
                width: 72px;
                height: 72px;
                border-radius: 50%;
                background: {color}1f;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 20px;
            }}
            .icon {{
                font-size: 32px;
                color: {color};
                font-weight: bold;
            }}
            h1 {{
                font-size: 20px;
                color: #0f172a;
                margin-bottom: 10px;
                font-weight: 800;
            }}
            p {{
                font-size: 14px;
                color: #64748b;
                line-height: 1.6;
            }}
            .footer {{
                margin-top: 24px;
                font-size: 12px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon-circle">
                <span class="icon">{icon}</span>
            </div>
            <h1>{title}</h1>
            <p>{message}</p>
            <div class="footer">© BlitzWork</div>
        </div>
    </body>
    </html>
    """

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
    verify_url = build_url(settings.BACKEND_URL, "/api/v1/auth/verify") + f"?token={token}"

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
