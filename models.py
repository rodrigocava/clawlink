"""
ClawPulse — Pydantic models (request bodies + response shapes)
"""
from typing import List

from pydantic import BaseModel, field_validator


class SyncUpload(BaseModel):
    token: str
    payload: str  # base64-encoded AES-256-GCM encrypted blob

    @field_validator("token")
    @classmethod
    def token_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Token must be at least 8 characters")
        return v

    @field_validator("payload")
    @classmethod
    def payload_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Payload cannot be empty")
        return v


class Datapoint(BaseModel):
    payload: str
    created_at: str
    expires_at: str


class SyncResponse(BaseModel):
    count: int
    datapoints: List[Datapoint]


class CountResponse(BaseModel):
    count: int
    oldest: str | None
    newest: str | None


class StatusResponse(BaseModel):
    status: str
    message: str


class ActivateRequest(BaseModel):
    token: str            # UUID in plaintext — matched against appAccountToken in JWS
    jws_transaction: str  # StoreKit 2 signed transaction string

    @field_validator("token")
    @classmethod
    def token_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Token must be at least 8 characters")
        return v

    @field_validator("jws_transaction")
    @classmethod
    def jws_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("jws_transaction cannot be empty")
        return v
