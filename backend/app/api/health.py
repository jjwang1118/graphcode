from fastapi import APIRouter

router = APIRouter()


@router.get("/api/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
