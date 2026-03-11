from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from .routes import auth, user, printer, file, print, voucher, transaction, telegram, refund, stats, group
from .routes import settings as settings_routes

from ..core.logger import logger
from ..core.config import settings
from ..core.utils import generate_time
from ..core.healthcheck import run_healthcheck


router = APIRouter(prefix="/api")


@router.get("/", status_code=status.HTTP_200_OK)
def root():
    logger.info("Base route accessed")
    
    health = run_healthcheck()
    overall_ok = all(c["status"] == "ok" for c in health.values())

    return {
        "app": "Printing Backend Service",
        "version": settings.VERSION,
        "status": "ok" if overall_ok else "error",
        "timestamp": generate_time(),
        "health_summary": {
            key: value["status"] for key, value in health.items()
        },
        "docs": "/docs",
        "health_endpoint": "/api/health"
    }


@router.get("/health")
def health_check():
    """
    Health check endpoint for Docker and monitoring.
    Returns HTTP 200 if all critical components are OK,
    HTTP 503 if any critical component is failing.
    """
    status_info = run_healthcheck()
    
    # Determine overall status
    overall_ok = all(component["status"] == "ok" for component in status_info.values())

    # Log if there is a failure
    if not overall_ok:
        failed_components = [name for name, comp in status_info.items() if comp["status"] != "ok"]
        logger.warning(f"Health check failed for components: {failed_components}")

    # Return HTTP 200 if healthy, 503 if any failure
    return JSONResponse(
        content={
            "status": "ok" if overall_ok else "error",
            "components": status_info
        },
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )


@router.get(
    "/version",
    status_code=status.HTTP_200_OK,
    summary="Get the current version of the PrintBuddy App"
)
def get_version():
    """
    Endpoint to retrieve the current version of the PrintBuddy App.
    """
    logger.info("Version endpoint accessed")
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": generate_time()
    }


router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(user.router, prefix="/users", tags=["users"])
router.include_router(printer.router, prefix="/printers", tags=["printers"])
router.include_router(file.router, prefix="/files", tags=["files"])
router.include_router(print.router, prefix="/print", tags=["print"])
router.include_router(voucher.router, prefix="/vouchers", tags=["vouchers"])
router.include_router(transaction.router, prefix="/transactions", tags=["transactions"])
router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
router.include_router(refund.router, prefix="/refunds", tags=["refunds"])
router.include_router(settings_routes.router, prefix="/settings", tags=["settings"])
router.include_router(stats.router, prefix="/stats", tags=["stats"])
router.include_router(group.router, prefix="/groups", tags=["groups"])
