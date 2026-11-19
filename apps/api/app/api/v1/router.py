from fastapi import APIRouter

from app.api.v1 import auth, documents, inbox, mail

router = APIRouter()
router.include_router(auth.router)
router.include_router(mail.router)
router.include_router(inbox.router)
router.include_router(documents.router)
