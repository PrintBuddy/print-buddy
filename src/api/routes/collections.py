from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import SuperAdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.collection_event import OutstandingAdminFloat, CollectionEventRead
from ...db.crud.collection_event import CollectionEventService
from ...db.crud.user import UserService


router = APIRouter()

collection_service = CollectionEventService()
user_service = UserService()


@router.get(
    "/outstanding",
    response_model=list[OutstandingAdminFloat],
    status_code=status.HTTP_200_OK,
)
def get_outstanding_floats(
    token: SuperAdminTokenDep,
    session: SessionDep,
):
    """Every admin currently holding uncollected recharge cash/transfers,
    and how much — Super Admin only."""
    results = []
    for admin_id, outstanding_amount in collection_service.get_outstanding_by_admin(session):
        admin = user_service.get_user_by_id(str(admin_id), session)
        if admin is None:
            continue
        results.append(
            OutstandingAdminFloat(
                admin_id=admin.id,
                username=admin.username,
                name=admin.name,
                surname=admin.surname,
                outstanding_amount=outstanding_amount,
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
    """Sweep every uncollected recharge Transaction attributed to this
    admin into one new CollectionEvent."""
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

    super_admin = user_service.get_user_by_id(super_admin_id, session)
    return CollectionEventRead(
        id=event.id,
        super_admin_id=event.super_admin_id,
        super_admin_username=super_admin.username if super_admin else None,
        standard_admin_id=event.standard_admin_id,
        standard_admin_username=admin.username,
        amount_collected=event.amount_collected,
        created_at=event.created_at,
    )


@router.get(
    "",
    response_model=list[CollectionEventRead],
    status_code=status.HTTP_200_OK,
)
def get_collection_history(
    token: SuperAdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    events = collection_service.get_all_events(session, pagination.limit, pagination.offset)
    results = []
    for event in events:
        super_admin = user_service.get_user_by_id(str(event.super_admin_id), session) if event.super_admin_id else None
        standard_admin = user_service.get_user_by_id(str(event.standard_admin_id), session) if event.standard_admin_id else None
        results.append(
            CollectionEventRead(
                id=event.id,
                super_admin_id=event.super_admin_id,
                super_admin_username=super_admin.username if super_admin else None,
                standard_admin_id=event.standard_admin_id,
                standard_admin_username=standard_admin.username if standard_admin else None,
                amount_collected=event.amount_collected,
                created_at=event.created_at,
            )
        )
    return results
