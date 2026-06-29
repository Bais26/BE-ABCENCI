from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, ExpiredSignatureError, JWTError
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import *
from app.utils.security import *
from app.core.email import get_mail_client
from app.core.config import settings
from app.models.karyawan_detail import KaryawanDetail
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
        joinedload(User.karyawan_detail).joinedload(KaryawanDetail.division)
    ).filter(User.id == current_user.id).first()

    # Eager load karyawan_detail (untuk safety)
    detail = current_user.karyawan_detail

    karyawan_detail_response = None
    if detail:
        from app.schemas.auth import KaryawanDetailResponse
        karyawan_detail_response = KaryawanDetailResponse(
            id=detail.id,
            user_id=detail.user_id,
            nama_depan=detail.nama_depan,
            nama_belakang=detail.nama_belakang,
            division={
                "id": detail.division.id,
                "name": detail.division.name
            } if detail.division else None,
            tanggal_lahir=detail.tanggal_lahir,
            jenis_kelamin=detail.jenis_kelamin,
            tinggi_badan=detail.tinggi_badan,
            berat_badan=detail.berat_badan,
            nama_alamat=detail.nama_alamat,
            alamat_lengkap=detail.alamat_lengkap,
            detail_alamat=detail.detail_alamat,
            nama_kontak_darurat=detail.nama_kontak_darurat,
            hubungan_kontak_darurat=detail.hubungan_kontak_darurat,
            nomor_telepon_darurat=detail.nomor_telepon_darurat,
            nama_bank=detail.nama_bank,
            nomor_rekening=detail.nomor_rekening,
            nama_pemilik_rekening=detail.nama_pemilik_rekening,
            posisi=detail.posisi,
            tanggal_masuk=detail.tanggal_masuk,
            status=detail.status,
            created_at=detail.created_at,
            updated_at=detail.updated_at
        )

    division_name = None
    if detail and detail.division:
        division_name = detail.division.name

    return UserWithDetailResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        phone_number=current_user.phone_number,
        address=current_user.address,
        date_of_birth=current_user.date_of_birth,
        created_at=current_user.created_at,
        karyawan_detail=karyawan_detail_response,
        division_name=division_name
    )

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
    verify_url = f"{settings.BACKEND_URL}/api/v1/auth/verify?token={token}"

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

    karyawan = user.karyawan_detail
    division_name = None

    if karyawan and karyawan.division:
        division_name = karyawan.division.name

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
        "divisi": division_name
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

    token = create_token({"email": user.email}, 15)

    fm = get_mail_client()
    reset_url = f"{settings.BACKEND_URL}/api/v1/auth/reset-password?token={token}"
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

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    user = db.query(User).filter(User.email == payload["email"]).first()

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
        "message": "Email verifikasi berhasil dikirim ulang"
    }
