import hashlib
import hmac

SUPPORTED_HMAC_ALGORITHMS = {
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
}


def verify_jira_signature(
    *,
    webhook_secret: str,
    raw_body: bytes,
    signature: str | None,
) -> bool:
    if not signature:
        return False

    algorithm, separator, provided_digest = signature.partition("=")
    if not separator or not provided_digest:
        return False

    digestmod = SUPPORTED_HMAC_ALGORITHMS.get(algorithm.lower())
    if digestmod is None:
        return False

    expected = algorithm.lower() + "=" + hmac.new(
        webhook_secret.encode(),
        raw_body,
        digestmod,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
