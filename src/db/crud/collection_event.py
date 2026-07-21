import uuid

from sqlmodel import Session, select, func
from sqlalchemy import update

from ..models.transaction import Transaction, TransactionType, ActorType
from ..models.collection_event import CollectionEvent, CollectionDirection
from ...core.utils import round_money


# RECHARGE amounts are positive (admin owes the house), EXPENSE amounts are
# negative (the house owes the admin, if they fronted the money) — summing
# both per admin gives a single signed net figure with no extra math.
NETTED_TYPES = (TransactionType.RECHARGE, TransactionType.EXPENSE)


class CollectionEventService:

    def get_outstanding_by_admin(self, session: Session) -> list[tuple[uuid.UUID, float]]:
        """Every admin with a nonzero net (recharges collected minus
        expenses fronted, uncollected/unpaid-back) — a plain GROUP BY over
        the ledger rather than a separately-maintained running total, so it
        can never drift from the transactions it's summarizing. Positive =
        admin owes the house; negative = the house owes the admin."""
        stmt = (
            select(Transaction.actor_id, func.sum(Transaction.amount))
            .where(
                Transaction.type.in_(NETTED_TYPES),
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id.is_not(None),
            )
            .group_by(Transaction.actor_id)
        )
        return [
            (actor_id, round_money(total)) for actor_id, total in session.exec(stmt).all()
            if round_money(total) != 0
        ]

    def get_outstanding_for_admin(self, admin_id: str, session: Session) -> float:
        stmt = (
            select(func.sum(Transaction.amount))
            .where(
                Transaction.type.in_(NETTED_TYPES),
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id == uuid.UUID(admin_id),
            )
        )
        total = session.exec(stmt).first()
        return round_money(total or 0)

    def _locked_unsettled_rows(self, admin_uuid: uuid.UUID, session: Session) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                Transaction.type.in_(NETTED_TYPES),
                Transaction.actor_type.in_([ActorType.ADMIN, ActorType.SUPER_ADMIN]),
                Transaction.collected_in_event_id.is_(None),
                Transaction.actor_id == admin_uuid,
            )
            .with_for_update()
        )
        return list(session.exec(stmt).all())

    def _settle(
        self,
        super_admin_id: str,
        admin_uuid: uuid.UUID,
        rows: list[Transaction],
        amount: float,
        direction: CollectionDirection,
        session: Session,
    ) -> CollectionEvent:
        event = CollectionEvent(
            super_admin_id=uuid.UUID(super_admin_id),
            standard_admin_id=admin_uuid,
            amount_collected=amount,
            direction=direction,
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

    def collect_from_admin(
        self,
        super_admin_id: str,
        standard_admin_id: str,
        session: Session,
    ) -> CollectionEvent | None:
        """Sweeps every unsettled RECHARGE+EXPENSE row for this admin into
        one new CollectionEvent — only when the net is positive (admin
        still owes the house after any fronted expenses are netted out).
        Returns None if there's nothing to collect (including when the net
        is zero or negative — that's pay_admin_from_house's job)."""
        admin_uuid = uuid.UUID(standard_admin_id)
        rows = self._locked_unsettled_rows(admin_uuid, session)
        if not rows:
            return None

        total = round_money(sum(row.amount for row in rows))
        if total <= 0:
            return None

        return self._settle(super_admin_id, admin_uuid, rows, total, CollectionDirection.FROM_ADMIN, session)

    def pay_admin_from_house(
        self,
        super_admin_id: str,
        standard_admin_id: str,
        session: Session,
    ) -> CollectionEvent | None:
        """Mirror of collect_from_admin for the opposite direction: this
        admin has fronted more in expenses than they currently owe from
        recharges, so the house pays them back the difference. Sweeps the
        same unsettled row set. Returns None if the net isn't negative."""
        admin_uuid = uuid.UUID(standard_admin_id)
        rows = self._locked_unsettled_rows(admin_uuid, session)
        if not rows:
            return None

        total = round_money(sum(row.amount for row in rows))
        if total >= 0:
            return None

        return self._settle(super_admin_id, admin_uuid, rows, abs(total), CollectionDirection.TO_ADMIN, session)

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
