from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="VitouLens AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "VitouLens AI",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
