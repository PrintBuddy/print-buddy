import uuid
from sqlmodel import Session, select

from ..models.group import Group, UserGroup, GroupPrinterPermit
from ..models.printer import Printer
from ...schemas.group import GroupCreate, GroupUpdate


class GroupService:

    # ─────────────────────── GROUP CRUD ───────────────────────

    def create_group(self, data: GroupCreate, session: Session) -> Group:
        group = Group(**data.model_dump())
        session.add(group)
        session.commit()
        session.refresh(group)
        return group

    def get_all_groups(self, session: Session) -> list[Group]:
        return list(session.exec(select(Group)).all())

    def get_group_by_id(self, group_id: uuid.UUID, session: Session) -> Group | None:
        return session.get(Group, group_id)

    def get_group_by_name(self, name: str, session: Session) -> Group | None:
        return session.exec(select(Group).where(Group.name == name)).first()

    def update_group(
        self, group_id: uuid.UUID, data: GroupUpdate, session: Session
    ) -> Group | None:
        group = session.get(Group, group_id)
        if group is None:
            return None
        for key, val in data.model_dump(exclude_none=True).items():
            setattr(group, key, val)
        session.commit()
        session.refresh(group)
        return group

    def delete_group(self, group_id: uuid.UUID, session: Session) -> Group | None:
        group = session.get(Group, group_id)
        if group is None:
            return None
        session.delete(group)
        session.commit()
        return group

    # ─────────────────────── MEMBERSHIP ───────────────────────

    def add_user_to_group(
        self, group_id: uuid.UUID, user_id: uuid.UUID, session: Session
    ) -> UserGroup | None:
        existing = session.exec(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        ).first()
        if existing:
            return existing
        membership = UserGroup(group_id=group_id, user_id=user_id)
        session.add(membership)
        session.commit()
        return membership

    def remove_user_from_group(
        self, group_id: uuid.UUID, user_id: uuid.UUID, session: Session
    ) -> bool:
        membership = session.exec(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        ).first()
        if membership is None:
            return False
        session.delete(membership)
        session.commit()
        return True

    def get_group_members(self, group_id: uuid.UUID, session: Session) -> list[uuid.UUID]:
        rows = session.exec(
            select(UserGroup.user_id).where(UserGroup.group_id == group_id)
        ).all()
        return list(rows)

    def get_user_groups(self, user_id: uuid.UUID, session: Session) -> list[uuid.UUID]:
        rows = session.exec(
            select(UserGroup.group_id).where(UserGroup.user_id == user_id)
        ).all()
        return list(rows)

    # ──────────────────── PRINTER PERMITS ─────────────────────

    def add_printer_to_group(
        self,
        group_id: uuid.UUID,
        printer_id: uuid.UUID,
        custom_price_bw: float | None,
        custom_price_color: float | None,
        session: Session,
    ) -> GroupPrinterPermit:
        existing = session.exec(
            select(GroupPrinterPermit).where(
                GroupPrinterPermit.group_id == group_id,
                GroupPrinterPermit.printer_id == printer_id
            )
        ).first()
        if existing:
            existing.custom_price_bw = custom_price_bw
            existing.custom_price_color = custom_price_color
            session.commit()
            session.refresh(existing)
            return existing
        permit = GroupPrinterPermit(
            group_id=group_id,
            printer_id=printer_id,
            custom_price_bw=custom_price_bw,
            custom_price_color=custom_price_color,
        )
        session.add(permit)
        session.commit()
        session.refresh(permit)
        return permit

    def update_printer_permit(
        self,
        group_id: uuid.UUID,
        printer_id: uuid.UUID,
        custom_price_bw: float | None,
        custom_price_color: float | None,
        session: Session,
    ) -> GroupPrinterPermit | None:
        permit = session.exec(
            select(GroupPrinterPermit).where(
                GroupPrinterPermit.group_id == group_id,
                GroupPrinterPermit.printer_id == printer_id
            )
        ).first()
        if permit is None:
            return None
        permit.custom_price_bw = custom_price_bw
        permit.custom_price_color = custom_price_color
        session.commit()
        session.refresh(permit)
        return permit

    def remove_printer_from_group(
        self, group_id: uuid.UUID, printer_id: uuid.UUID, session: Session
    ) -> bool:
        permit = session.exec(
            select(GroupPrinterPermit).where(
                GroupPrinterPermit.group_id == group_id,
                GroupPrinterPermit.printer_id == printer_id
            )
        ).first()
        if permit is None:
            return False
        session.delete(permit)
        session.commit()
        return True

    def get_group_printer_permits(
        self, group_id: uuid.UUID, session: Session
    ) -> list[GroupPrinterPermit]:
        return list(
            session.exec(
                select(GroupPrinterPermit).where(GroupPrinterPermit.group_id == group_id)
            ).all()
        )

    # ─────────── BUSINESS LOGIC: visibility & pricing ─────────

    def get_accessible_printers(
        self, user_id: uuid.UUID, session: Session
    ) -> list[Printer]:
        """
        Returns all printers the user is allowed to see:
          - all non-restricted printers
          - restricted printers for which the user's groups hold a permit
        """
        user_group_ids = self.get_user_groups(user_id, session)

        # Restricted printer IDs the user has access to via groups
        if user_group_ids:
            permitted_ids = set(
                session.exec(
                    select(GroupPrinterPermit.printer_id).where(
                        GroupPrinterPermit.group_id.in_(user_group_ids)
                    )
                ).all()
            )
        else:
            permitted_ids = set()

        printers = session.exec(
            select(Printer).where(Printer.is_active.is_(True))
        ).all()

        return [
            p for p in printers
            if not p.is_restricted or p.id in permitted_ids
        ]

    def get_effective_prices(
        self,
        user_id: uuid.UUID,
        printer_id: uuid.UUID,
        session: Session,
    ) -> tuple[float | None, float | None]:
        """
        Returns (effective_price_bw, effective_price_color) for a user on a printer.
        Returns (None, None) if the user has no relevant permits
        (caller should then use the printer's default prices).
        Takes the minimum (most favourable) price across all applicable group permits.
        """
        user_group_ids = self.get_user_groups(user_id, session)
        if not user_group_ids:
            return None, None

        permits = session.exec(
            select(GroupPrinterPermit).where(
                GroupPrinterPermit.printer_id == printer_id,
                GroupPrinterPermit.group_id.in_(user_group_ids)
            )
        ).all()

        if not permits:
            return None, None

        bw_prices = [p.custom_price_bw for p in permits if p.custom_price_bw is not None]
        color_prices = [p.custom_price_color for p in permits if p.custom_price_color is not None]

        return (
            min(bw_prices) if bw_prices else None,
            min(color_prices) if color_prices else None,
        )

    def user_can_access_printer(
        self, user_id: uuid.UUID, printer_id: uuid.UUID, session: Session
    ) -> bool:
        """Returns True if the user has a group permit for the given printer."""
        user_group_ids = self.get_user_groups(user_id, session)
        if not user_group_ids:
            return False
        permit = session.exec(
            select(GroupPrinterPermit).where(
                GroupPrinterPermit.printer_id == printer_id,
                GroupPrinterPermit.group_id.in_(user_group_ids)
            )
        ).first()
        return permit is not None
