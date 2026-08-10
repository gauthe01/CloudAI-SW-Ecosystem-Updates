import base64
import hashlib
import hmac
import secrets

LOCAL_SECRET_PREFIX = "managed-local-v2"


def encrypt_local_secret(*, secret_name: str, value: str, master_key: str) -> str:
    nonce = secrets.token_bytes(16)
    value_bytes = value.encode()
    key_stream = _key_stream(
        secret_name=secret_name,
        master_key=master_key,
        nonce=nonce,
        length=len(value_bytes),
    )
    encrypted = bytes(value ^ key for value, key in zip(value_bytes, key_stream, strict=True))
    return f"{LOCAL_SECRET_PREFIX}:{base64.urlsafe_b64encode(nonce + encrypted).decode('ascii')}"


def decrypt_local_secret(*, secret_name: str, ciphertext: str, master_key: str) -> str | None:
    if not ciphertext.startswith(f"{LOCAL_SECRET_PREFIX}:"):
        return None
    encoded = ciphertext.split(":", 1)[1]
    try:
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except ValueError:
        return None
    if len(payload) < 17:
        return None
    nonce = payload[:16]
    encrypted = payload[16:]
    key_stream = _key_stream(
        secret_name=secret_name,
        master_key=master_key,
        nonce=nonce,
        length=len(encrypted),
    )
    decrypted = bytes(value ^ key for value, key in zip(encrypted, key_stream, strict=True))
    try:
        return decrypted.decode()
    except UnicodeDecodeError:
        return None


def fingerprint_secret(*, secret_name: str, value: str, master_key: str) -> str:
    return hmac.new(
        key=master_key.encode(),
        msg=f"{secret_name}:{value}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _key_stream(*, secret_name: str, master_key: str, nonce: bytes, length: int) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        stream.extend(
            hmac.new(
                key=master_key.encode(),
                msg=nonce + secret_name.encode() + counter.to_bytes(4, "big"),
                digestmod=hashlib.sha256,
            ).digest()
        )
        counter += 1
    return bytes(stream[:length])
