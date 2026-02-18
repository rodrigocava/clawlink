# Subscription Verification — Phase 2

This document describes the work needed to complete subscription verification
after Phase 1 (StoreKit 2 JWS activation) is live.

Phase 1 covers the happy path: user subscribes → app activates → syncs work.
Phase 2 covers lifecycle events: renewals, cancellations, refunds, grace periods.

---

## What Phase 1 Doesn't Handle

| Scenario | Phase 1 | Phase 2 |
|----------|---------|---------|
| New subscription | ✅ `/activate` called by app | — |
| App launch after renewal | ✅ app re-calls `/activate` | — |
| Subscription cancelled mid-period | ⚠️ still works until `active_until` | ✅ webhook marks expired |
| Refund issued | ⚠️ still works until `active_until` | ✅ webhook marks expired immediately |
| Billing retry / grace period | ⚠️ stops working at `active_until` | ✅ webhook extends grace period |
| App uninstalled, reinstalled | ⚠️ user must re-enter credentials | ✅ restore purchases flow |
| Family sharing | ❌ not supported | ✅ appAccountToken per member |

---

## New Endpoint: POST /apple/notifications

Apple sends a JWS-signed notification to this URL on every subscription event.
Register it in App Store Connect → Your App → App Store → App Information → App Store Server Notifications.

```
URL: https://server.clawpulse.app/apple/notifications
Version: Version 2 (signedPayload format)
```

### Notification types to handle

| Type | Subtype | Action |
|------|---------|--------|
| `SUBSCRIBED` | `INITIAL_BUY` | Mark subscriber active (belt + suspenders with /activate) |
| `DID_RENEW` | — | Update `active_until` to new expiry date |
| `EXPIRED` | `VOLUNTARY` / `BILLING_RETRY` | Set `active_until = now` (deactivate) |
| `REFUND` | — | Set `active_until = now` (deactivate immediately) |
| `DID_FAIL_TO_RENEW` | `GRACE_PERIOD` | Extend `active_until` by grace period (16 days) |
| `GRACE_PERIOD_EXPIRED` | — | Set `active_until = now` |
| `REVOKE` | — | Family sharing revoked — deactivate that member |

### Implementation sketch

```python
@app.post("/apple/notifications", tags=["Subscription"])
async def apple_notifications(request: Request):
    body = await request.json()
    signed_payload = body.get("signedPayload")
    if not signed_payload:
        raise HTTPException(status_code=400, detail="Missing signedPayload")

    # Verify the outer JWS (same Apple Root CA G3 verification)
    notification = await verify_apple_jws(signed_payload)

    # The notification wraps another JWS in data.signedTransactionInfo
    notification_type = notification.get("notificationType")
    subtype = notification.get("subtype")

    signed_tx = notification.get("data", {}).get("signedTransactionInfo")
    transaction = await verify_apple_jws(signed_tx) if signed_tx else {}

    original_tx_id = transaction.get("originalTransactionId")
    expires_ms = transaction.get("expiresDate")

    db = await get_db()
    try:
        if notification_type in ("EXPIRED", "REFUND", "GRACE_PERIOD_EXPIRED", "REVOKE"):
            # Deactivate immediately
            await db.execute(
                "UPDATE subscribers SET active_until = ?, updated_at = ? WHERE original_transaction_id = ?",
                (now_utc(), now_utc(), original_tx_id),
            )
        elif notification_type == "DID_RENEW" or (
            notification_type == "DID_FAIL_TO_RENEW" and subtype == "GRACE_PERIOD"
        ):
            active_until = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc).isoformat()
            await db.execute(
                "UPDATE subscribers SET active_until = ?, updated_at = ? WHERE original_transaction_id = ?",
                (active_until, now_utc(), original_tx_id),
            )
        await db.commit()
    finally:
        await db.close()

    return {"status": "ok"}
```

---

## Restore Purchases Flow (iOS)

When a user reinstalls the app or gets a new device, they need to restore their subscription.

**iOS side:**
```swift
// After user taps "Restore Purchases"
for await result in Transaction.currentEntitlements {
    if case .verified(let transaction) = result {
        // Re-send the JWS to /activate
        await activateOnServer(jwsRepresentation: transaction.jwsRepresentation)
    }
}
```

**Server side:** `/activate` already handles this — it's an UPSERT, so re-activating just refreshes `active_until`. No changes needed.

---

## Env Vars for Phase 2

```bash
# Already in Phase 1
REQUIRE_SUBSCRIPTION=true
APPLE_ENVIRONMENT=Production   # or Sandbox

# New in Phase 2
# (none required — webhook verification uses same Apple Root CA G3)
```

---

## Testing Phase 2

Use Apple's [Sandbox environment](https://developer.apple.com/documentation/storekit/testing_in_xcode)
and set `APPLE_ENVIRONMENT=Sandbox` on a test server instance.

Apple provides a [StoreKit Testing](https://developer.apple.com/documentation/xcode/setting-up-storekit-testing-in-xcode)
tool in Xcode that can simulate renewals, cancellations, and refunds instantly.

---

*Phase 1 completed: 2026-02-18*
*Phase 2 target: before or shortly after App Store launch*
