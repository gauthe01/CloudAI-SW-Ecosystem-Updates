import hashlib
import hmac
import time


def verify_slack_signature(
    *,
    signing_secret: str,
    raw_body: bytes,
    timestamp: str | None,
    signature: str | None,
    now_seconds: int | None = None,
    tolerance_seconds: int = 300,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    current_time = now_seconds if now_seconds is not None else int(time.time())
    if abs(current_time - timestamp_int) > tolerance_seconds:
        return False

    base_string = b"v0:" + timestamp.encode() + b":" + raw_body
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        base_string,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
