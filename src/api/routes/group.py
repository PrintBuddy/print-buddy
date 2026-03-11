import uuid
from fastapi import APIRouter, status, HTTPException

from ..dependencies.database import SessionDep
from ..dependencies.token import AdminTokenDep
from ...db.crud.group import GroupService
from ...db.crud.user import UserService
from ...db.crud.printer import PrinterService
from ...schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupRead,
    GroupDetailRead,
    GroupMemberAdd,
    GroupPrinterPermitCreate,
    GroupPrinterPermitUpdate,
    GroupPrinterPermitRead,
)


router = APIRouter()
group_service = GroupService()
user_service = UserService()
printer_service = PrinterService()


# ──────────────────────── GROUPS ────────────────────────

@router.get(
    "",
    response_model=list[GroupRead],
    status_code=status.HTTP_200_OK
)
def get_groups(token: AdminTokenDep, session: SessionDep):
    return group_service.get_all_groups(session)


@router.post(
    "",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED
)
def create_group(data: GroupCreate, token: AdminTokenDep, session: SessionDep):
    if group_service.get_group_by_name(data.name, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A group with that name already exists"
        )
    return group_service.create_group(data, session)


@router.get(
    "/{group_id}",
    response_model=GroupDetailRead,
    status_code=status.HTTP_200_OK
)
def get_group(group_id: uuid.UUID, token: AdminTokenDep, session: SessionDep):
    group = group_service.get_group_by_id(group_id, session)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    members = group_service.get_group_members(group_id, session)
    permits = group_service.get_group_printer_permits(group_id, session)
    return GroupDetailRead(
        id=group.id,
        name=group.name,
        description=group.description,
        members=members,
        printer_permits=[
            GroupPrinterPermitRead(
                printer_id=p.printer_id,
                custom_price_bw=p.custom_price_bw,
                custom_price_color=p.custom_price_color,
            )
            for p in permits
        ],
    )


@router.patch(
    "/{group_id}",
    response_model=GroupRead,
    status_code=status.HTTP_200_OK
)
def update_group(
    group_id: uuid.UUID, data: GroupUpdate, token: AdminTokenDep, session: SessionDep
):
    if data.name is not None:
        existing = group_service.get_group_by_name(data.name, session)
        if existing and existing.id != group_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A group with that name already exists"
            )
    group = group_service.update_group(group_id, data, session)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.delete(
    "/{group_id}",
    response_model=GroupRead,
    status_code=status.HTTP_200_OK
)
def delete_group(group_id: uuid.UUID, token: AdminTokenDep, session: SessionDep):
    group = group_service.delete_group(group_id, session)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


# ──────────────────────── MEMBERS ────────────────────────

@router.post(
    "/{group_id}/members",
    status_code=status.HTTP_201_CREATED
)
def add_member(
    group_id: uuid.UUID, body: GroupMemberAdd, token: AdminTokenDep, session: SessionDep
):
    if group_service.get_group_by_id(group_id, session) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if user_service.get_user_by_id(str(body.user_id), session) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    group_service.add_user_to_group(group_id, body.user_id, session)
    return {"success": True}


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_200_OK
)
def remove_member(
    group_id: uuid.UUID, user_id: uuid.UUID, token: AdminTokenDep, session: SessionDep
):
    if group_service.get_group_by_id(group_id, session) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    removed = group_service.remove_user_from_group(group_id, user_id, session)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this group"
        )
    return {"success": True}


# ──────────────────── PRINTER PERMITS ────────────────────

@router.post(
    "/{group_id}/printers",
    response_model=GroupPrinterPermitRead,
    status_code=status.HTTP_201_CREATED
)
def add_printer_permit(
    group_id: uuid.UUID,
    body: GroupPrinterPermitCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    if group_service.get_group_by_id(group_id, session) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    printer = printer_service.get_printer_by_id(body.printer_id, session)
    if printer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Printer not found")
    permit = group_service.add_printer_to_group(
        group_id, body.printer_id, body.custom_price_bw, body.custom_price_color, session
    )
    return GroupPrinterPermitRead(
        printer_id=permit.printer_id,
        custom_price_bw=permit.custom_price_bw,
        custom_price_color=permit.custom_price_color,
    )


@router.patch(
    "/{group_id}/printers/{printer_id}",
    response_model=GroupPrinterPermitRead,
    status_code=status.HTTP_200_OK
)
def update_printer_permit(
    group_id: uuid.UUID,
    printer_id: uuid.UUID,
    body: GroupPrinterPermitUpdate,
    token: AdminTokenDep,
    session: SessionDep,
):
    permit = group_service.update_printer_permit(
        group_id, printer_id, body.custom_price_bw, body.custom_price_color, session
    )
    if permit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permit not found"
        )
    return GroupPrinterPermitRead(
        printer_id=permit.printer_id,
        custom_price_bw=permit.custom_price_bw,
        custom_price_color=permit.custom_price_color,
    )


@router.delete(
    "/{group_id}/printers/{printer_id}",
    status_code=status.HTTP_200_OK
)
def remove_printer_permit(
    group_id: uuid.UUID,
    printer_id: uuid.UUID,
    token: AdminTokenDep,
    session: SessionDep,
):
    if group_service.get_group_by_id(group_id, session) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    removed = group_service.remove_printer_from_group(group_id, printer_id, session)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permit not found"
        )
    return {"success": True}
