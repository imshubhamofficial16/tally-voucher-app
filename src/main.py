from fastapi import FastAPI
from src.api import health, imports

app = FastAPI(
    title="Tally XML Ingestion Service",
    description="Backend service for ingesting and normalizing Tally XML vouchers",
    version="1.0.0"
)

# Include routers
app.include_router(health.router)
app.include_router(imports.router, prefix="/api/tally")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    pass
