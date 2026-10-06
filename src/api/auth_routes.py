from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.config.database import get_db
from src.schemas.db_models import User, Company
from src.api.auth import get_password_hash, verify_password, create_access_token
from datetime import timedelta
from src.config.settings import settings

router = APIRouter(prefix="/auth", tags=["Autenticação"])

class RegisterRequest(BaseModel):
    company_name: str
    cnpj: str
    user_name: str
    email: str
    password: str

@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Verifica se a empresa já existe pelo CNPJ
    result = await db.execute(select(Company).filter(Company.cnpj == data.cnpj))
    existing_company = result.scalars().first()
    
    if existing_company:
        raise HTTPException(status_code=400, detail="Empresa com este CNPJ já está cadastrada.")
        
    result = await db.execute(select(User).filter(User.email == data.email))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="E-mail já está em uso.")

    # Cria a Empresa
    new_company = Company(name=data.company_name, cnpj=data.cnpj)
    db.add(new_company)
    await db.commit()
    await db.refresh(new_company)

    # Cria o Usuário Admin da Empresa
    new_user = User(
        name=data.user_name,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_admin=True,
        company_id=new_company.id
    )
    db.add(new_user)
    await db.commit()

    return {"message": "Cadastro realizado com sucesso!"}


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "company_id": user.company_id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user_name": user.name}

@router.post("/demo")
async def login_demo(db: AsyncSession = Depends(get_db)):
    # Tenta achar o user primeiro
    res_user = await db.execute(select(User).filter(User.email == "demo@demo.com"))
    demo_user = res_user.scalars().first()
    
    if demo_user:
        company_id = demo_user.company_id
        user_id = demo_user.id
        user_name = demo_user.name
    else:
        # Se não existe o user, confere a empresa
        res_comp = await db.execute(select(Company).filter(Company.cnpj == "00000000000000"))
        demo_company = res_comp.scalars().first()
        
        if not demo_company:
            demo_company = Company(name="Demo Corp", cnpj="00000000000000")
            db.add(demo_company)
            await db.commit()
            await db.refresh(demo_company)
            
        demo_user = User(
            name="Visitante Demo",
            email="demo@demo.com",
            hashed_password=get_password_hash("demo"),
            is_admin=True,
            company_id=demo_company.id
        )
        db.add(demo_user)
        await db.commit()
        await db.refresh(demo_user)
        
        company_id = demo_company.id
        user_id = demo_user.id
        user_name = demo_user.name

    access_token = create_access_token(
        data={"sub": user_id, "company_id": company_id}, 
        expires_delta=timedelta(minutes=60)
    )
    return {"access_token": access_token, "token_type": "bearer", "user_name": user_name}
