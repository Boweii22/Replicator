from __future__ import annotations

import base64
import os


class IAMReportSigner:
    """Signs report manifest bytes with the runtime service account's Google-managed key."""

    def __init__(self, service_account: str | None = None, session=None) -> None:
        self.service_account = service_account or os.environ["RUNTIME_SERVICE_ACCOUNT"]
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            session = AuthorizedSession(credentials)
        self.session = session

    def sign(self, payload: bytes) -> str:
        url = (
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{self.service_account}:signBlob"
        )
        response = self.session.post(
            url, json={"payload": base64.b64encode(payload).decode()}, timeout=30
        )
        response.raise_for_status()
        signature = response.json().get("signedBlob")
        if not signature:
            raise RuntimeError("IAM Credentials returned no signature")
        return signature
