# Local Certificate Mounts

Place local corporate CA bundle files in this folder when Docker needs to trust
an enterprise endpoint.

Example `.env` value:

```env
AI_CA_BUNDLE=/app/certs/arm-enterprise-ca.pem
```

Do not commit certificate files, private keys, or secret material. This folder is
mounted read-only into the API and worker containers at `/app/certs`.
