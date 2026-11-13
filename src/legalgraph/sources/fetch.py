"""Fetching originals exactly as their index describes, or taking them from a page saved by hand."""

import gzip
import io
import re
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date

from bs4 import BeautifulSoup

from legalgraph.load import REPO_ROOT
from legalgraph.sources.constants import USER_AGENT
from legalgraph.sources.model import Original, Source, SourceError, sha256

RENDERER = REPO_ROOT / "tools" / "render" / "render.ts"
SAVED_FROM = re.compile(rb"saved from url=\(\d+\)(\S+?)\s*-->")


def download(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data: bytes = response.read()
            if response.headers.get("Content-Encoding") == "gzip":  # servers that insist on compression (eCFR)
                data = gzip.decompress(data)
            return data
    except Exception as error:
        # urllib's certificate store misses some national portals (ris.bka.gv.at, pgdlisboa.pt,
        # riksdagen.se, api.sejm.gov.pl); curl uses the system keychain where urllib does not.
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        return subprocess.run(
            ["curl", "-sfL", "-A", USER_AGENT, "-m", "60", url], capture_output=True, check=True
        ).stdout


def html_fragment(page: bytes, selector: str) -> bytes:
    """The element matching `selector`, as BeautifulSoup serialises it. Pages change with every
    request (session tokens, timestamps); the fragment holding the law text does not."""
    fragment = BeautifulSoup(page, "html.parser").select_one(selector)
    if fragment is None:
        raise SourceError(f"Selector {selector!r} matched nothing")
    return (str(fragment) + "\n").encode("utf-8")


def zip_member(original: Original, data: bytes) -> bytes:
    if not original.member:
        raise SourceError(f"{original.file}: zip-member needs `member`")
    archive = zipfile.ZipFile(io.BytesIO(data))
    if original.member not in archive.namelist():
        raise SourceError(f"{original.file.name}: the zip holds {', '.join(archive.namelist())}, not {original.member}")
    return archive.read(original.member)


def render(url: str, wait: str | None) -> bytes:
    """The page as a browser shows it, for portals that build the law text with JavaScript: headless
    Chromium through tools/render (bun and Playwright, `make render-install` once per host)."""
    command = ["bun", str(RENDERER), url, *(["--wait", wait] if wait else [])]
    try:
        return subprocess.run(command, capture_output=True, check=True, timeout=180).stdout
    except FileNotFoundError as error:
        raise SourceError("rendered originals need bun: https://bun.sh, then `make render-install`") from error
    except subprocess.CalledProcessError as error:
        raise SourceError(f"rendering {url} failed: {error.stderr.decode(errors='replace')[-500:]}") from error


def fetch(original: Original) -> bytes:
    if original.pause:
        time.sleep(original.pause)
    if original.fetch == "rendered":
        if not original.selector:
            raise SourceError(f"{original.file}: rendered needs `selector`")
        return html_fragment(render(original.url, original.wait), original.selector)
    data = download(original.url, original.headers)
    if original.fetch == "zip-member":
        return zip_member(original, data)
    if original.fetch == "html-fragment":
        if not original.selector:
            raise SourceError(f"{original.file}: html-fragment needs `selector`")
        return html_fragment(data, original.selector)
    return data


def saved_url(page: bytes) -> str | None:
    """The address a browser-saved page comes from: its `<!-- saved from url=(…) -->` marker."""
    match = SAVED_FROM.search(page[:8192])
    return match.group(1).decode("utf-8", "replace") if match else None


def same_saved_url(url: str, listed: str) -> bool:
    """A saved page's marker matches the original's URL: the browser percent-encodes it and may keep
    a scroll anchor (#Text), both of which are cosmetic here."""
    decode = urllib.parse.unquote
    return decode(url.split("#", 1)[0]) == decode(listed.split("#", 1)[0])


def fetch_saved(original: Original, page: bytes) -> bytes:
    """The original cut out of a page saved by hand in a browser, with the same cut fetch makes:
    the fragment for html-fragment, the file itself otherwise."""
    if original.fetch in ("html-fragment", "rendered"):
        if not original.selector:
            raise SourceError(f"{original.file.name}: {original.fetch} needs `selector`")
        return html_fragment(page, original.selector)
    if original.fetch == "file":
        return page
    raise SourceError(f"{original.file.name}: --saved works for html-fragment and file originals")


def record_fetch(source: Source, original: Original, data: bytes, on: date) -> bool:
    """Write a freshly fetched original and update its sha256 and retrieved_on in source.yaml.
    Returns False when nothing changed."""
    digest = sha256(data)
    if digest == original.sha256 and original.file.exists():
        return False
    original.file.write_bytes(data)
    text = source.index.read_text()
    pattern = re.compile(rf"(retrieved_on: )\S+(\n\s+sha256: ){re.escape(original.sha256)}(?=\s)")
    updated, count = pattern.subn(rf"\g<1>{on.isoformat()}\g<2>{digest}", text)
    if count != 1:
        raise SourceError(f"{source.index}: write `retrieved_on` directly above `sha256` for {original.file.name}")
    source.index.write_text(updated)
    return True
