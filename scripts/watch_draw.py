import json
import sys
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

DRAW_URL = "http://127.0.0.1:8000/draw"


def multipart_body(image_path: Path, boundary: str) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    )
    return header.encode() + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()


def describe(event: dict) -> str:
    extras = []
    if event["canvas"]:
        extras.append(f"canvas={event['canvas']['width']}x{event['canvas']['height']}")
    if event["layer"]:
        extras.append(f"layer={len(event['layer']) // 1024}KB")
    return f"[{event['agent']:12s}] {event['status']:7s} {event['message']} {' '.join(extras)}".rstrip()


def main(image_path: Path) -> None:
    boundary = uuid.uuid4().hex
    request = Request(
        DRAW_URL,
        data=multipart_body(image_path, boundary),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlopen(request) as response:
        for line in response:
            if line.startswith(b"data: "):
                print(describe(json.loads(line[6:])), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/watch_draw.py <image-path>")
    main(Path(sys.argv[1]))
