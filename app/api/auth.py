from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import timedelta
from typing import List, Optional

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.config import settings
from app.core.enums import UserRole
from app.models.user import User
from app.models.supplier import Supplier
from app.schemas.user import UserCreate, UserResponse, Token, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Re-export require_roles from canonical location
from app.core.rbac import require_roles  # noqa: E402


async def ensure_supplier_profile(user: User, db: AsyncSession) -> Supplier:
    result = await db.execute(select(Supplier).where(Supplier.user_id == user.id))
    supplier = result.scalar_one_or_none()
    if supplier is not None:
        return supplier

    supplier = Supplier(
        id=str(__import__("uuid").uuid4()),
        user_id=user.id,
        company_name=user.company_name or user.email,
        inn=user.inn or f"TMP{user.id.replace('-', '')[:10]}",
        address=user.address,
        warehouse_address=user.address,
        is_verified=False,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole(user_data.role),
        company_name=user_data.company_name,
        inn=user_data.inn,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
        if "users.phone" in msg or "phone" in msg.lower():
            raise HTTPException(status_code=400, detail="Phone already registered")
        if "users.email" in msg or "email" in msg.lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        if "role" in msg.lower():
            raise HTTPException(status_code=400, detail="Invalid role value")
        raise HTTPException(status_code=400, detail=f"Registration failed: {msg}")
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}")

    await db.refresh(user)
    if user.role == UserRole.SUPPLIER:
        await ensure_supplier_profile(user, db)
    return user


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(
        data={"sub": user.id, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    available_roles = [current_user.role]
    supplier_result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
    supplier_profile = supplier_result.scalar_one_or_none()
    if supplier_profile is not None and UserRole.SUPPLIER not in available_roles:
        available_roles.append(UserRole.SUPPLIER)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        available_roles=available_roles,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        company_name=current_user.company_name,
        created_at=current_user.created_at,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


# Password reset endpoints
from pydantic import BaseModel, EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    email: EmailStr
    reset_code: str
    new_password: str


# Simple in-memory store for reset codes (use Redis in production)
_reset_codes = {}


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset - sends reset code to email"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If email exists, reset code will be sent"}
    
    # Generate simple reset code (6 digits)
    import random
    reset_code = str(random.randint(100000, 999999))
    
    # Store code (expires in 15 minutes)
    _reset_codes[data.email] = {
        "code": reset_code,
        "expires": __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=15)
    }
    
    # Send email with reset code via Resend API
    try:
        import httpx
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #f4f6fa; padding: 40px;">
          <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color: #1e40af; margin-top: 0;">TruckGrad</h2>
            <p>Вы запросили восстановление пароля.</p>
            <p>Ваш код подтверждения:</p>
            <div style="font-size: 32px; font-weight: bold; color: #1e40af; text-align: center; padding: 20px; background: #eef2ff; border-radius: 8px; letter-spacing: 6px;">
              {reset_code}
            </div>
            <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">Код действителен 15 минут. Если вы не запрашивали восстановление — проигнорируйте это письмо.</p>
          </div>
        </body>
        </html>
        """
        
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer re_CVdS3GVk_Echch2ewCPcqKGzSSWKEZ5Jd"},
            json={
                "from": "TruckGrad <noreply@truckgrad.ru>",
                "to": [data.email],
                "subject": "TruckGrad - Код восстановления пароля",
                "html": html,
            }
        )
        print(f"Resend response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Failed to send email: {e}")
    
    return {"message": "If email exists, reset code will be sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Confirm password reset with code and new password"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or reset code")
    
    # Check reset code
    reset_data = _reset_codes.get(data.email)
    if not reset_data:
        raise HTTPException(status_code=400, detail="Reset code not requested or expired")
    
    if reset_data["code"] != data.reset_code:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    
    if __import__("datetime").datetime.utcnow() > reset_data["expires"]:
        del _reset_codes[data.email]
        raise HTTPException(status_code=400, detail="Reset code expired")
    
    # Update password
    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    
    # Clear reset code
    del _reset_codes[data.email]
    
    return {"message": "Password successfully reset"}
