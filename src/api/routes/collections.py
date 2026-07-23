from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import AdminTokenDep, SuperAdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.collection_event import OutstandingAdminFloat, CollectionEventRead
from ...db.crud.collection_event import CollectionEventService
from ...db.crud.user import UserService


router = APIRouter()

collection_service = CollectionEventService()
user_service = UserService()


def _to_event_read(event, session) -> CollectionEventRead:
    super_admin = user_service.get_user_by_id(str(event.super_admin_id), session) if event.super_admin_id else None
    standard_admin = user_service.get_user_by_id(str(event.standard_admin_id), session) if event.standard_admin_id else None
    return CollectionEventRead(
        id=event.id,
        super_admin_id=event.super_admin_id,
        super_admin_username=super_admin.username if super_admin else None,
        standard_admin_id=event.standard_admin_id,
        standard_admin_username=standard_admin.username if standard_admin else None,
        amount_collected=event.amount_collected,
        direction=event.direction,
        created_at=event.created_at,
    )


@router.get(
    "/outstanding",
    response_model=list[OutstandingAdminFloat],
    status_code=status.HTTP_200_OK,
)
def get_outstanding_floats(
    token: AdminTokenDep,
    session: SessionDep,
):
    """Every admin with a nonzero net cash position (recharges collected,
    netted against any expenses they've fronted) — readable by any admin,
    but only a Super Admin can act on it (see collect/pay below)."""
    results = []
    for admin_id, net_amount in collection_service.get_outstanding_by_admin(session):
        admin = user_service.get_user_by_id(str(admin_id), session)
        if admin is None:
            continue
        results.append(
            OutstandingAdminFloat(
                admin_id=admin.id,
                username=admin.username,
                name=admin.name,
                surname=admin.surname,
                net_amount=net_amount,
            )
        )
    return results


@router.post(
    "/{admin_id}/collect",
    response_model=CollectionEventRead,
    status_code=status.HTTP_201_CREATED,
)
def collect_from_admin(
    admin_id: str,
    token: SuperAdminTokenDep,
    session: SessionDep,
):
    """Sweep every unsettled RECHARGE+EXPENSE row attributed to this admin
    into one new CollectionEvent — only when they still owe the house net
    of any expenses they've fronted. Super Admin only."""
    super_admin_id = token.credentials

    admin = user_service.get_user_by_id(admin_id, session)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    event = collection_service.collect_from_admin(super_admin_id, admin_id, session)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This admin has nothing outstanding to collect",
        )

    return _to_event_read(event, session)


@router.post(
    "/{admin_id}/pay",
    response_model=CollectionEventRead,
    status_code=status.HTTP_201_CREATED,
)
def pay_admin(
    admin_id: str,
    token: SuperAdminTokenDep,
    session: SessionDep,
):
    """Mirror of collect: pay this admin back for expenses they've
    fronted that exceed what they currently owe the house from recharges.
    Super Admin only."""
    super_admin_id = token.credentials

    admin = user_service.get_user_by_id(admin_id, session)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    event = collection_service.pay_admin_from_house(super_admin_id, admin_id, session)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing is owed to this admin",
        )

    return _to_event_read(event, session)


@router.get(
    "",
    response_model=list[CollectionEventRead],
    status_code=status.HTTP_200_OK,
)
def get_collection_history(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    """Readable by any admin — only a Super Admin can create new events."""
    events = collection_service.get_all_events(session, pagination.limit, pagination.offset)
    return [_to_event_read(event, session) for event in events]
