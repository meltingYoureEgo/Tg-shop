"""Wallet request model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class WalletRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentMethod(str, Enum):
    UPI = "upi"
    USDT_BEP20 = "usdt_bep20"


class WalletRequest(Base):
    """Wallet top-up request model."""

    __tablename__ = "wallet_requests"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Amount in INR always
    amount_inr: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # If USDT — original USDT amount
    amount_usdt: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    # USDT rate used at time of request (INR per 1 USDT)
    usdt_rate: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod),
        nullable=False,
    )

    utr_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    screenshot_file_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[WalletRequestStatus] = mapped_column(
        SQLEnum(WalletRequestStatus),
        default=WalletRequestStatus.PENDING,
        nullable=False,
        index=True,
    )

    processed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    admin_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<WalletRequest("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"amount_inr={self.amount_inr}, "
            f"method={self.payment_method}, "
            f"status={self.status})>"
        )