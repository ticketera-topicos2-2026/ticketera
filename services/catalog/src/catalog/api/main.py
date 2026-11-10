"""FastAPI application of the catalog service."""

from fastapi import FastAPI

# The gateway publishes this service under /api/catalog (D-29, DS-11).
app = FastAPI(title="catalog", root_path="/api/catalog")
