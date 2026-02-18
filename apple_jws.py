"""
Apple StoreKit 2 JWS Transaction Verification
==============================================
Verifies signed transactions returned by StoreKit 2 purchases.

The JWS is a 3-part base64url string (header.payload.signature).
The header contains an x5c certificate chain signed by Apple Root CA G3.
The signature is ES256 (ECDSA P-256 + SHA-256).

Ref: https://developer.apple.com/documentation/appstoreserverapi/jwstransactiondecodedpayload
"""

import base64
import json
from typing import Any

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding as rsa_padding
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

# ── Apple Root CA G3 ─────────────────────────────────────────────────────────
# ECDSA P-384 root. Fingerprint verifiable at https://www.apple.com/certificateauthority/
APPLE_ROOT_CA_G3_URL = "https://www.apple.com/certificateauthority/AppleRootCA-G3.cer"
APPLE_ROOT_CA_G3_SHA256 = "63343abfb89a6a03ebb57e2b7b5338e9725e932753e2c18ce075d42cc6fa5870"

_cached_root_ca: x509.Certificate | None = None


async def _get_apple_root_ca() -> x509.Certificate:
    """Fetch and cache Apple Root CA G3. Verifies fingerprint before caching."""
    global _cached_root_ca
    if _cached_root_ca is not None:
        return _cached_root_ca

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(APPLE_ROOT_CA_G3_URL)
        resp.raise_for_status()
        cert = x509.load_der_x509_certificate(resp.content)

    fp = cert.fingerprint(hashes.SHA256()).hex()
    if fp != APPLE_ROOT_CA_G3_SHA256:
        raise ValueError(f"Apple Root CA G3 fingerprint mismatch: got {fp}")

    _cached_root_ca = cert
    return cert


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _verify_cert_signed_by(child: x509.Certificate, issuer: x509.Certificate) -> None:
    """Verify that child certificate's signature was made by issuer's private key."""
    pub_key = issuer.public_key()
    hash_alg = child.signature_hash_algorithm

    try:
        if isinstance(pub_key, ec.EllipticCurvePublicKey):
            pub_key.verify(child.signature, child.tbs_certificate_bytes, ec.ECDSA(hash_alg))
        elif isinstance(pub_key, rsa.RSAPublicKey):
            pub_key.verify(child.signature, child.tbs_certificate_bytes, rsa_padding.PKCS1v15(), hash_alg)
        else:
            raise ValueError(f"Unsupported issuer key type: {type(pub_key)}")
    except InvalidSignature:
        raise ValueError("Certificate signature verification failed")


async def verify_apple_jws(token: str) -> dict[str, Any]:
    """
    Verify an Apple StoreKit 2 JWS transaction string.

    Steps:
      1. Decode JWS header → extract x5c certificate chain
      2. Verify each cert in chain is signed by the next
      3. Verify chain root traces to Apple Root CA G3
      4. Verify JWS signature using the leaf cert's public key
      5. Decode and return the payload

    Returns the decoded payload dict on success.
    Raises ValueError with a descriptive message on any failure.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWS: expected header.payload.signature")

    header_b64, payload_b64, sig_b64 = parts

    # ── Decode header ─────────────────────────────────────────────────────────
    try:
        header = json.loads(_b64url_decode(header_b64))
    except Exception:
        raise ValueError("Cannot decode JWS header")

    x5c = header.get("x5c", [])
    if len(x5c) < 2:
        raise ValueError("JWS missing certificate chain (x5c header)")

    # ── Parse certificate chain ───────────────────────────────────────────────
    # x5c[0] = leaf (signing cert)
    # x5c[1] = Apple WorldWide Developer Relations intermediate
    # Root CA is NOT included in the chain — we verify against our cached copy
    try:
        certs = [x509.load_der_x509_certificate(base64.b64decode(c)) for c in x5c]
    except Exception as e:
        raise ValueError(f"Cannot parse certificate chain: {e}")

    # ── Verify chain: each cert signed by the next ────────────────────────────
    for i in range(len(certs) - 1):
        try:
            _verify_cert_signed_by(certs[i], certs[i + 1])
        except ValueError as e:
            raise ValueError(f"Chain broken at position {i}: {e}")

    # ── Verify chain root is signed by Apple Root CA G3 ──────────────────────
    apple_root = await _get_apple_root_ca()
    try:
        _verify_cert_signed_by(certs[-1], apple_root)
    except ValueError:
        raise ValueError("Certificate chain does not trace to Apple Root CA G3")

    # ── Verify JWS signature with leaf cert public key ────────────────────────
    signing_input = f"{header_b64}.{payload_b64}".encode()
    raw_sig = _b64url_decode(sig_b64)

    if len(raw_sig) != 64:
        raise ValueError(f"Unexpected ES256 signature length: {len(raw_sig)} (expected 64)")

    # ES256 raw signature = R || S (32 bytes each) → convert to DER for cryptography lib
    r = int.from_bytes(raw_sig[:32], "big")
    s = int.from_bytes(raw_sig[32:], "big")
    der_sig = encode_dss_signature(r, s)

    try:
        certs[0].public_key().verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise ValueError("JWS signature is invalid")

    # ── Decode and return payload ─────────────────────────────────────────────
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise ValueError("Cannot decode JWS payload")

    return payload
