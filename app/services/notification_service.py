from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError
from typing import Dict, Optional


def send_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> str:
    """
    Mengirim notifikasi push ke device menggunakan FCM token.

    :param token: FCM registration token dari device.
    :param title: Judul notifikasi.
    :param body: Isi pesan notifikasi.
    :param data: Payload data tambahan (opsional).
    :return: Message ID dari Firebase.
    """
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        token=token,
    )

    try:
        response = messaging.send(message)
        return response
    except FirebaseError as e:
        # Ini akan menangkap error seperti token tidak valid, dll.
        # Kita re-raise exception agar bisa ditangkap di schedule.py
        raise Exception(f"Firebase Error: {e.code} - {e.message}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}")