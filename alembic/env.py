from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context
import sys
import os

# Tambahkan path project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alembic config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ===== IMPORT BASE & SEMUA MODEL =====
from app.db.base import Base
from app.core.config import settings

# IMPORT SEMUA MODEL AGAR TERDETEKSI ALEMBIC
from app.models.user import User, KaryawanDetail
from app.models.attendance import Attendance
from app.models.schedule import WorkSchedule
# from app.models.office_location import OfficeLocation

target_metadata = Base.metadata


def get_url():
    return settings.DATABASE_URL


def run_migrations_offline():
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # 🔥 INI KUNCI UTAMA (NEON FIX)
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        connection.execute(text("SET search_path TO public"))
        connection.commit()  # 🔥 COMMIT SETELAH SET search_path

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,  # 🔥 PASTIKAN INI TRUE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()