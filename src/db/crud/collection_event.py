import uuid

from sqlmodel import Session, select, func
from sqlalchemy import update

from ..models.transaction import Transaction, TransactionType, ActorType
from ..models.collection_event import CollectionEvent
from ...core.utils import round_money


class CollectionEventService:

    def get_outstanding_by_admin(self, session: Session) -> list[tuple[uuid.UUID, float]]:
        """Every admin currently holding an uncollected cash/transfer
        recharge, and how much — a plain GROUP BY over the ledger rather
        than a separately-maintained running total, so it can never drift
        from the transactions it's summarizing."""
        stmt = (
            select(Transaction.actor_id, func.sum(Transaction.amount))
            .where(
                Transaction.type == TransactionType.RECHARGE,
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id.is_not(None),
            )
            .group_by(Transaction.actor_id)
        )
        return [(actor_id, round_money(total)) for actor_id, total in session.exec(stmt).all()]

    def get_outstanding_for_admin(self, admin_id: str, session: Session) -> float:
        stmt = (
            select(func.sum(Transaction.amount))
            .where(
                Transaction.type == TransactionType.RECHARGE,
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id == uuid.UUID(admin_id),
            )
        )
        total = session.exec(stmt).first()
        return round_money(total or 0)

    def collect_from_admin(
        self,
        super_admin_id: str,
        standard_admin_id: str,
        session: Session,
    ) -> CollectionEvent | None:
        """Sweeps every uncollected qualifying Transaction row for this
        admin into one new CollectionEvent, atomically. Returns None if
        there was nothing outstanding to collect."""
        admin_uuid = uuid.UUID(standard_admin_id)

        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.RECHARGE,
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id == admin_uuid,
            )
            .with_for_update()
        )
        rows = session.exec(stmt).all()
        if not rows:
            return None

        total = round_money(sum(row.amount for row in rows))

        event = CollectionEvent(
            super_admin_id=uuid.UUID(super_admin_id),
            standard_admin_id=admin_uuid,
            amount_collected=total,
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        row_ids = [row.id for row in rows]
        session.execute(
            update(Transaction)
            .where(Transaction.id.in_(row_ids))  # type: ignore
            .values(collected_in_event_id=event.id)
        )
        session.commit()

        return event

    def get_all_events(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CollectionEvent]:
        stmt = (
            select(CollectionEvent)
            .order_by(CollectionEvent.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())
