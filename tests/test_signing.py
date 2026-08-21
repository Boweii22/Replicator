import base64

from packages.gcp.signing import IAMReportSigner


class Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"signedBlob": "google-managed-signature"}


class Session:
    request = None

    def post(self, url: str, *, json: dict, timeout: int):
        self.request = (url, json, timeout)
        return Response()


def test_iam_signer_sends_base64_payload_to_signblob() -> None:
    session = Session()
    signer = IAMReportSigner("runtime@example.iam.gserviceaccount.com", session)
    assert signer.sign(b"manifest") == "google-managed-signature"
    assert session.request[0].endswith(":signBlob")
    assert base64.b64decode(session.request[1]["payload"]) == b"manifest"
