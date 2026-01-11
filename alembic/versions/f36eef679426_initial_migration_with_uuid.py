"""initial migration with uuid

Revision ID: f36eef679426
Revises: 
Create Date: 2026-01-11 12:12:13.841968

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f36eef679426'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ✅ 1. CREATE ENUM TYPE FIRST
    userrole_enum = postgresql.ENUM('ADMIN', 'KARYAWAN', name='userrole', create_type=False)
    userrole_enum.create(op.get_bind(), checkfirst=True)
    
    # ✅ 2. CREATE USERS TABLE
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('role', postgresql.ENUM('ADMIN', 'KARYAWAN', name='userrole', create_type=False), nullable=False, server_default='KARYAWAN'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # ✅ 3. CREATE KARYAWAN_DETAILS TABLE
    op.create_table(
        'karyawan_details',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nama_depan', sa.String(), nullable=True),
        sa.Column('nama_belakang', sa.String(), nullable=True),
        sa.Column('tanggal_lahir', sa.Date(), nullable=True),
        sa.Column('jenis_kelamin', sa.String(), nullable=True),
        sa.Column('tinggi_badan', sa.String(), nullable=True),
        sa.Column('berat_badan', sa.String(), nullable=True),
        sa.Column('nama_alamat', sa.String(), nullable=True),
        sa.Column('alamat_lengkap', sa.Text(), nullable=True),
        sa.Column('detail_alamat', sa.String(), nullable=True),
        sa.Column('nama_kontak_darurat', sa.String(), nullable=True),
        sa.Column('hubungan_kontak_darurat', sa.String(), nullable=True),
        sa.Column('nomor_telepon_darurat', sa.String(), nullable=True),
        sa.Column('nama_bank', sa.String(), nullable=True),
        sa.Column('nomor_rekening', sa.String(), nullable=True),
        sa.Column('nama_pemilik_rekening', sa.String(), nullable=True),
        sa.Column('posisi', sa.String(), nullable=True),
        sa.Column('tanggal_masuk', sa.Date(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_karyawan_details_id'), 'karyawan_details', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_karyawan_details_id'), table_name='karyawan_details')
    op.drop_table('karyawan_details')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    
    # Drop ENUM type
    postgresql.ENUM(name='userrole').drop(op.get_bind(), checkfirst=True)