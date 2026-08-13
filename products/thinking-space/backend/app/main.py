from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.services.seed import seed_v1_data
from app.database import SessionLocal
from app.routes import dimensions, entries, index, diagnose, cross_links, export, layer_links, layers


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_v1_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="思考空间 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

app.include_router(dimensions.router)
app.include_router(entries.router)
app.include_router(index.router)
app.include_router(diagnose.router)
app.include_router(cross_links.router)
app.include_router(export.router)
app.include_router(layer_links.router)
app.include_router(layers.router)
