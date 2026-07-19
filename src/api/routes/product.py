from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.product import ProductCreate, ProductUpdate, ProductRead, ProductPurchaseResult
from ...db.crud.product import ProductService


router = APIRouter()

product_service = ProductService()


@router.get(
    "",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
)
def get_products(
    token: TokenDep,
    session: SessionDep,
):
    """The "Extras" store — active products only for regular users."""
    return product_service.get_all_products(session, active_only=True)


@router.post(
    "/{product_id}/purchase",
    response_model=ProductPurchaseResult,
    status_code=status.HTTP_200_OK,
)
def purchase_product(
    product_id: str,
    token: TokenDep,
    session: SessionDep,
):
    user_id = token.credentials
    result = product_service.purchase_product(product_id, user_id, session)

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if result.reason == "inactive":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This product is no longer available")
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

    product = product_service.get_product_by_id(product_id, session)
    return ProductPurchaseResult(
        product=ProductRead.model_validate(product), new_balance=result.new_balance
    )


# ─── Admin ────────────────────────────────────────────────────────────────────

@router.get(
    "/admin",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
)
def get_all_products_admin(
    token: AdminTokenDep,
    session: SessionDep,
):
    """Every product, including inactive ones — for management."""
    return product_service.get_all_products(session, active_only=False)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    data: ProductCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    return product_service.create_product(
        data.name, data.price, session,
        inventory_item_id=str(data.inventory_item_id) if data.inventory_item_id else None,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
)
def update_product(
    product_id: str,
    data: ProductUpdate,
    token: AdminTokenDep,
    session: SessionDep,
):
    product = product_service.update_product(
        product_id, session,
        name=data.name,
        price=data.price,
        is_active=data.is_active,
        inventory_item_id=str(data.inventory_item_id) if data.inventory_item_id else None,
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
