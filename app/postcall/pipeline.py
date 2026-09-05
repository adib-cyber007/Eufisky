"""Phase-5 post-call hook; intentionally a no-op during Guardian work."""


def enqueue(call_id: str) -> None:
    del call_id
