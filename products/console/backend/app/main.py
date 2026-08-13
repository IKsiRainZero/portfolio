from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import projects_router
from .ai.chat import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title="Portfolio Console")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    app.include_router(projects_router)
    app.include_router(chat_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
