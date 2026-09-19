"""Reject secrets in repository-bound metadata without logging or rewriting values."""
import re
from urllib.parse import parse_qsl, urlsplit

from analyzers.bundle_validation import require

_SECRET_KEYS = {
    "password", "passwd", "secret", "client_secret", "api_key", "apikey",
    "access_token", "refresh_token", "auth_token", "authorization", "bearer_token",
    "access_key", "secret_access_key", "aws_access_key_id", "aws_secret_access_key",
    "private_key", "credential", "credentials", "token", "cookie", "cookies",
}
_SIGNED_QUERY_KEYS = {
    "sig", "signature", "token", "access_token", "auth", "authorization", "key",
    "x-amz-signature", "x-amz-credential", "x-amz-security-token",
    "x-goog-signature", "x-goog-credential", "googleaccessid",
    "awsaccesskeyid", "policy", "key-pair-id",
}
_REDACTED = {"", "<redacted>", "[redacted]", "redacted"}
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_SECRET_TEXT = re.compile(
    r"-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----|\bBearer\s+[A-Za-z0-9_.~+/=-]+|"
    r"\b(?:password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)


def validate_repository_metadata(value):
    """Narrow disclosure gate, not a claim to detect every possible secret."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[-\s]", "_", key).lower()
            if normalized in _SECRET_KEYS:
                require(child is None or (isinstance(child, str) and child.lower() in _REDACTED),
                        "Repository metadata contains credential material; supply a redacted, rehashed bundle")
            validate_repository_metadata(child)
    elif isinstance(value, list):
        for child in value:
            validate_repository_metadata(child)
    elif isinstance(value, str):
        require(not _SECRET_TEXT.search(value),
                "Repository metadata contains credential material; supply a redacted, rehashed bundle")
        for match in _URL.finditer(value):
            try:
                url = urlsplit(match.group(0))
                query_keys = {k.lower() for k, _ in parse_qsl(url.query, keep_blank_values=True)}
                unsafe = bool(url.username or url.password or query_keys.intersection(_SIGNED_QUERY_KEYS))
            except ValueError:
                unsafe = True
            require(not unsafe,
                    "Repository metadata contains an authenticated/signed URL; supply a redacted, rehashed bundle")
