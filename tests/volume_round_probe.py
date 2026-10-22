"""Exercise a paid partial round across container replacement (CI only).

Run seed before replacing the container and check afterward using the SAME
mounted disk. Only loopback origins are allowed; never mutates live staging.
"""
import argparse
import http.cookiejar
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed", "check"))
    parser.add_argument("--url", default="http://127.0.0.1:18086")
    parser.add_argument("--snapshot", required=True, type=Path)
    args = parser.parse_args()
    assert urlsplit(args.url).hostname in ("127.0.0.1", "localhost", "::1")
    jar = http.cookiejar.CookieJar()
    client = build_opener(HTTPCookieProcessor(jar))
    saved = json.loads(args.snapshot.read_text()) if args.mode == "check" else None

    def request(path, payload=None):
        headers = {"x-uno-client": "spin-ui"}
        if saved:
            headers["Cookie"] = saved["cookie"]
        body = None if payload is None else json.dumps(payload).encode()
        if body:
            headers["Content-Type"] = "application/json"
        with client.open(Request(args.url + path, data=body, headers=headers), timeout=15) as response:
            return json.load(response)

    state = request("/api/orbit/state")
    if args.mode == "seed":
        payload = {"request_id": "volume_" + secrets.token_hex(12), "stake": 25}
        result = request("/api/orbit/pick", payload)
        assert not result["replayed"]
        assert result["account"]["balance"] == state["account"]["balance"] - 25
        args.snapshot.write_text(json.dumps({
            "cookie": "; ".join(f"{c.name}={c.value}" for c in jar),
            "payload": payload, "result": result,
        }))
        args.snapshot.chmod(0o600)
    else:
        expected = saved["result"]
        assert state["account"] == expected["account"], "Account/balance lost on replacement"
        assert state["round"] == expected["round"], "Paid round lost on replacement"
        replay = request("/api/orbit/pick", saved["payload"])
        assert replay["replayed"] is True
        assert replay["account"] == expected["account"], "Retry charged coins again"
        assert replay["round"] == expected["round"], "Retry advanced the round"
    print(f"PASS: persistent paid round {args.mode}")


if __name__ == "__main__":
    main()
