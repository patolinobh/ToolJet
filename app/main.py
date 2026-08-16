from fastapi import FastAPI
from app.api.v1.lookup import router as lookup_router

app = FastAPI(title="Vehicle History API")

app.include_router(lookup_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}
