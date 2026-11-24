"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-11

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    subscription_status = sa.Enum("active", "paused", "deleted", name="subscription_status")
    notification_type = sa.Enum("new_flight", "price_drop", "flight_back", name="notification_type")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ru"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column(
            "notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "reported_as_new", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "flights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("airline", sa.String(length=128), nullable=True),
        sa.Column("flight_number", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=8), nullable=False),
        sa.Column("departure_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrival_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_departure_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_arrival_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("direct", sa.Boolean(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("baggage", sa.String(length=64), nullable=True),
        sa.Column("booking_url", sa.String(length=1024), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_flights_external_id", "flights", ["external_id"])
    op.create_unique_constraint(
        "uq_flights_provider_external_id", "flights", ["provider", "external_id"]
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=8), nullable=False),
        sa.Column("flexible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("departure_date_from", sa.Date(), nullable=True),
        sa.Column("departure_date_to", sa.Date(), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("return_date_from", sa.Date(), nullable=True),
        sa.Column("return_date_to", sa.Date(), nullable=True),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("direct_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("status", subscription_status, nullable=False, server_default="active"),
        sa.Column("search_key", sa.String(length=256), nullable=False),
        sa.Column("last_known_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_known_flight_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_search_key", "subscriptions", ["search_key"])

    op.create_table(
        "flight_price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "flight_id", sa.Integer(), sa.ForeignKey("flights.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_flight_price_history_subscription_id", "flight_price_history", ["subscription_id"]
    )
    op.create_index("ix_flight_price_history_flight_id", "flight_price_history", ["flight_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "flight_id", sa.Integer(), sa.ForeignKey("flights.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_subscription_id", "notifications", ["subscription_id"])

    op.create_table(
        "searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=8), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("flexible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_searches_user_id", "searches", ["user_id"])


def downgrade() -> None:
    op.drop_table("searches")
    op.drop_table("notifications")
    op.drop_table("flight_price_history")
    op.drop_table("subscriptions")
    op.drop_table("flights")
    op.drop_table("users")

    sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscription_status").drop(op.get_bind(), checkfirst=True)
