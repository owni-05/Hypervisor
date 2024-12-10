from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application
    """
    app = FastAPI(
        title=Settings.PROJECT_NAME,
        description="Backend Service for Cluster Management and Deployment",
        version="0.1.0"
    )



    # Include routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["Organizations"])
    app.include_router(clusters.router, prefix="/api/v1/clusters", tags=["Clusters"])
    app.include_router(deployments.router, prefix="/api/v1/deployments", tags=["Deployments"])

    return app

app = create_application()