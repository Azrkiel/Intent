import json

QUALIFIED_VERSION = "0.164.0"


class CodexError(RuntimeError):
    """Redacted, actionable integration errors; never forward raw RPC exceptions."""


def decode(line: bytes) -> dict:
    try:
        value = json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
        if "id" in value and (isinstance(value["id"], bool) or not isinstance(value["id"], (int, str))):
            raise ValueError()
        if "method" in value:
            if not isinstance(value["method"], str) or not isinstance(value.get("params", {}), dict):
                raise ValueError()
        elif "id" not in value or ("result" in value) == ("error" in value):
            raise ValueError()
        return value
    except (ValueError, UnicodeError) as error:
        raise CodexError("Codex returned invalid protocol data") from error
