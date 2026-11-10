"""FastAPI application of the sales service."""

from fastapi import FastAPI

# The gateway publishes this service under /api/sales (D-29, DS-11).
app = FastAPI(title="sales", root_path="/api/sales")

