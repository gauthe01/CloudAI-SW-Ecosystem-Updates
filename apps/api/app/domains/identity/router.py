from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import Settings, get_settings
from app.domains.identity.dependencies import (
    get_auth_service,
    get_current_auth_context,
    get_current_user,
)
from app.domains.identity.schemas import (
    AuthContextResponse,
    AuthMeResponse,
    LoginRequest,
    LogoutResponse,
    SessionResponse,
    SwitchActiveViewRequest,
    UserResponse,
)
from app.domains.identity.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    login_result = await auth_service.login(
        email=payload.email,
        password=payload.password,
        keep_signed_in=payload.keep_signed_in,
        user_agent=request.headers.get("user-agent"),
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=login_result.raw_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        expires=login_result.expires_at,
        path="/",
    )
    return SessionResponse(
        user=login_result.context.user,
        expires_at=login_result.expires_at,
        available_views=login_result.context.available_views,
        active_view=login_result.context.active_view,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogoutResponse:
    await auth_service.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return LogoutResponse()


@router.get("/me", response_model=AuthMeResponse)
async def me(
    auth_context: Annotated[AuthContextResponse, Depends(get_current_auth_context)],
) -> AuthMeResponse:
    return AuthMeResponse(
        user=auth_context.user,
        available_views=auth_context.available_views,
        active_view=auth_context.active_view,
    )


@router.patch("/active-view", response_model=AuthMeResponse)
async def switch_active_view(
    payload: SwitchActiveViewRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthMeResponse:
    auth_context = await auth_service.switch_active_view(
        raw_token=request.cookies.get(settings.session_cookie_name),
        active_view=payload.active_view,
    )
    return AuthMeResponse(
        user=auth_context.user,
        available_views=auth_context.available_views,
        active_view=auth_context.active_view,
    )


@router.get("/session-required", status_code=status.HTTP_204_NO_CONTENT)
async def session_required(_: Annotated[UserResponse, Depends(get_current_user)]) -> None:
    return None
