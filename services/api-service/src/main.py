import os
import sys
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-service")

app = FastAPI(
    title="Child Safety Guardian API",
    description="Backend API for Child Safety Guardian monitoring, telemetry ingestion, and alert management.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Kubernetes Probes & Root Info (Essential for GitOps / K3s)
# -------------------------------------------------------------
@app.get("/", tags=["System"])
def root_status():
    return {
        "status": "online",
        "service": "child-safety-guardian-api",
        "message": "Child Safety Guardian API is running",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("APP_ENV", "production")
    }

@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["System"])
def health_check():
    """Kubernetes liveness probe: confirms the process is alive."""
    return {"status": "healthy"}

@app.get("/readyz", status_code=status.HTTP_200_OK, tags=["System"])
def readiness_check():
    """Kubernetes readiness probe: confirms the pod can accept traffic."""
    return {"status": "ready"}

# -------------------------------------------------------------
# Modular Domain Routers (Graceful loading for CI/CD)
# -------------------------------------------------------------
try:
    from audio_guardian import router as audio_router
    app.include_router(audio_router, prefix="/api/audio", tags=["Audio Guardian"])
    logger.info("Loaded Audio Guardian router successfully.")
except Exception as e:
    logger.warning(f"Audio Guardian router skipped (not installed in CI test run): {e}")

try:
    from nanny_cam_guardian import router as nanny_router
    app.include_router(nanny_router.router, prefix="/api/iot", tags=["Nanny Cam Guardian (MM-ODG)"])
    logger.info("Loaded Nanny Cam router successfully.")
except Exception as e:
    logger.warning(f"Nanny Cam router skipped (not installed in CI test run): {e}")

try:
    from app.api.v1.router import api_v1_router
    app.include_router(api_v1_router, prefix="/api/v1")
    logger.info("Loaded Safety Alert Pipeline API (v1).")
except Exception as e:
    logger.warning(f"Safety Alert Pipeline router skipped: {e}")

# Legal RAG Sub-module loading
try:
    rag_backend_path = os.path.join(os.path.dirname(__file__), "legal-rag-backend")
    if os.path.isdir(rag_backend_path):
        if rag_backend_path not in sys.path:
            sys.path.insert(0, rag_backend_path)

        app_module_stash = {k: sys.modules.pop(k) for k in list(sys.modules.keys()) if k == 'app' or k.startswith('app.')}

        from app.routers.rag import router as rag_router
        from app.routers.legal import router as legal_router
        app.include_router(rag_router)
        app.include_router(legal_router)

        for k, v in app_module_stash.items():
            if k not in sys.modules:
                sys.modules[k] = v
        logger.info("Loaded Legal RAG routers successfully.")
except Exception as e:
    logger.warning(f"Could not load Legal RAG routers: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)