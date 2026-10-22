#!/bin/env python3
# @https://raw.githubusercontent.com/Pependr/wsync/refs/heads/master/wsync.py

import os
import sys

from urllib import request

import asyncio


async def extract_url_label(path: str) -> str:
    with open(path, mode="r") as file:
        for line in file:
            if "@" in line:
                return line[line.find("@") + 1:].strip()
    
    raise RuntimeError(f"Could not find url in {path}")


def extract_etag(path: str) -> bytes | None:
    try:
        return os.getxattr(path, "user.etag")
    except OSError as err:
        if err.errno == 61:
            return None
        raise err


async def request_etag(url: str) -> str:
    req = request.Request(url, method="HEAD")
    with request.urlopen(req) as conn:
        return conn.getheader("etag")


async def download_file(path: str, url: str, file_etag: str) -> bool:
    req = request.Request(url, method="GET")
    req.add_header("If-None-Match", file_etag)
    
    try:
        with request.urlopen(req) as conn:
            with open(path, mode="wb") as file:
                while chunk := conn.read(1024):
                    file.write(chunk)

            os.setxattr(path, "user.etag", conn.getheader("etag").encode())
    except request.HTTPError as err:
        if err.getcode() == 304:
            return False
        raise err

    return True


async def file_worker(path: str) -> bool:
    etag = extract_etag(path)
    url  = await extract_url_label(path)

    if etag is None:
        etag = await request_etag(url)
        os.setxattr(path, "user.etag", etag.encode())
        return False

    return await download_file(path, url, etag.decode())


async def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} [INPUT FILES]", file=sys.stderr)
        return 1

    workers: list[asyncio.Task[bool]] = [
        asyncio.create_task(file_worker(path), name=path)
        for path in sys.argv[1:]
    ]

    async for task in asyncio.as_completed(workers):
        path = task.get_name()

        if await task:
            print(f"Updated {path}", file=sys.stderr)
        else:
            print(f"{path} is up to date", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

