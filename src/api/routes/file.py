from fastapi import APIRouter, status, HTTPException, UploadFile
from pathlib import Path

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.file import FileCreate, FileRead
from ...db.crud.file import FileService
from ...core.config import settings
from ...core.file_manager import FileManager


file_service = FileService()
fm = FileManager()


router = APIRouter()


@router.get(
    '',
    response_model=list[FileRead],
    status_code=status.HTTP_200_OK
)
def get_files(
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials
    files = file_service.get_files_by_user_id(user_id, session)
    return files


@router.post(
    '',
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED
)
def upload_file(
    file: UploadFile,
    token: TokenDep,
    session: SessionDep
):  
    user_id = token.credentials

    is_valid = fm.is_valid_format(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File format not supported"
        )

    path = Path(settings.UPLOAD_PATH) / str(user_id)
    path = fm.generate_file_path(path, file)
    size = fm.save_file(path, file)

    if size == -1:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size too large. Max size: {settings.MAX_FILE_SIZE_MB} MB"
        )

    file_data = FileCreate(
        filename=file.filename,  # type: ignore
        filepath=path.as_posix(),
        size_bytes=size,
        mime_type=file.content_type,  # type: ignore
        pages=fm.get_total_pages(path)
    )

    new_file = file_service.create_file(
        user_id, file_data, session
    )

    return new_file


@router.delete(
    '/{file_id}',
    response_model=FileRead,
    status_code=status.HTTP_200_OK
)
def delete_file(
    file_id: str,
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials

    if not file_service.is_file_from_user(file_id, user_id, session):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User unauthorized or file does not exist"
        )
    
    file = file_service.delete_file(file_id, session)
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    path = Path(file.filepath)
    success = fm.delete_file(path)
    print(success)

    return file
