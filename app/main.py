"""
Academy FastAPI 스타터 템플릿
─────────────────────────────────────────────────────────────
DB 접근:
  환경변수(DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASS)는
  서버의 provision 과정에서 자동으로 .env에 기록됩니다.
  로컬 개발 시에는 프로젝트 루트에 .env 파일을 만들어 사용하세요.

    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=mydb
    DB_USER=myuser
    DB_PASS=mypassword

엔드포인트 추가 방법:
  app/routers/ 폴더를 만들어 라우터 파일을 분리하고
  아래 include_router 예시처럼 등록하세요.
─────────────────────────────────────────────────────────────
"""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .database import Base, engine, get_db
from .models import Item
from .routers import risk as risk_router


# ── 앱 시작 시 테이블 자동 생성 ───────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="DPA API — 질병 확률 알리미", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# /v1/risk, /v1/exposure, /v1/risk/timeseries 등
app.include_router(risk_router.router)


# ── Request / Response 스키마 ──────────────────────────────────
class ItemCreate(BaseModel):
    title: str
    content: Optional[str] = None


class ItemOut(BaseModel):
    id: int
    title: str
    content: Optional[str]
    model_config = {"from_attributes": True}


# ── 헬스체크 (필수 — 배포 시 health check가 이 엔드포인트를 호출합니다) ──
@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB 연결 실패: {e}")


@app.get("/")
async def root():
    return {"message": "Hello from Academy API!"}


# ── 예시 CRUD (items 테이블) ───────────────────────────────────

# get로 http://localhost:8000/items
@app.get("/items", response_model=list[ItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).order_by(Item.id))
    return result.scalars().all()

# post로 http://localhost:8000/items
@app.post("/items", response_model=ItemOut, status_code=201)
async def create_item(body: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(title=body.title, content=body.content)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


# get으로 http://localhost:8000/items
@app.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()


# ── 라우터 추가 예시 ───────────────────────────────────────────
# from .routers import posts
# app.include_router(posts.router, prefix="/posts", tags=["posts"])

# ── 프론트용 공개 설정 (지도 API 키 등 — 브라우저에 노출되는 값만) ──
@app.get("/config")
async def public_config():
    return {
        "naverMapsClientId": os.getenv("NAVER_MAPS_CLIENT_ID", ""),
        "kakaoMapsAppKey":   os.getenv("KAKAO_MAPS_APP_KEY",   ""),
    }
