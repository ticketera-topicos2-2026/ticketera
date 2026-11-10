"""FastAPI application of the payments service."""

from fastapi import FastAPI

# The gateway publishes this service under /api/payments (D-29, DS-11).
app = FastAPI(title="payments", root_path="/api/payments")