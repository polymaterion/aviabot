from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, SubscriptionStatus, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.user import User


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)

    flexible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    departure_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    departure_date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    departure_date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    return_date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    return_date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    max_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    direct_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Нормализованный ключ параметров поиска - используется для группировки
    # одинаковых подписок разных пользователей в один API-запрос (см. п.33 ТЗ).
    search_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)

    # Последнее известное состояние результата - для защиты от повторных
    # уведомлений (п.36 ТЗ): цена и наличие подходящего варианта.
    last_known_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    last_known_flight_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    last_seen_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
