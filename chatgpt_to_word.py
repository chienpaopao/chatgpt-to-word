#!/usr/bin/env python3
"""
ChatGPT text (with LaTeX) → Word (.docx) → upload to web
Usage:
  python3 chatgpt_to_word.py input.md          # convert file
  python3 chatgpt_to_word.py                   # interactive paste mode
  echo "content" | python3 chatgpt_to_word.py  # pipe mode
"""

import sys
import os
import subprocess
import tempfile
import argparse
import re

# Suppress urllib3 warning on macOS
import warnings
warnings.filterwarnings("ignore")
import requests


# ── Upload backends ────────────────────────────────────────────────────────────

def upload_gofile(path: str) -> str:
    """Upload to gofile.io (no account needed, direct download link)."""
    # 1. Get an available server
    r = requests.get("https://api.gofile.io/servers", timeout=10)
    r.raise_for_status()
    server = r.json()["data"]["servers"][0]["name"]

    # 2. Create a guest token
    r = requests.post("https://api.gofile.io/accounts", timeout=10)
    r.raise_for_status()
    token = r.json()["data"]["token"]

    # 3. Upload
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        r = requests.post(
            f"https://{server}.gofile.io/contents/uploadFile",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, f,
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document")},
            timeout=60,
        )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"gofile error: {data}")
    return data["data"]["downloadPage"]


def upload_fileio(path: str) -> str:
    """Upload to file.io (auto-deletes after first download, 14-day expiry)."""
    with open(path, "rb") as f:
        r = requests.post(
            "https://file.io/?expires=14d",
            files={"file": (os.path.basename(path), f,
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document")},
            timeout=30,
            allow_redirects=True,
        )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"file.io error: {data}")
    return data["link"]


def upload(path: str) -> str:
    """Try gofile.io first, fall back to file.io."""
    try:
        print("  Uploading to gofile.io …", end=" ", flush=True)
        url = upload_gofile(path)
        print("OK")
        return url
    except Exception as e:
        print(f"failed ({e})")
    try:
        print("  Uploading to file.io …", end=" ", flush=True)
        url = upload_fileio(path)
        print("OK")
        return url
    except Exception as e:
        print(f"failed ({e})")
        raise RuntimeError("All upload backends failed.")


# ── LaTeX preprocessing ────────────────────────────────────────────────────────

def normalize_latex(text: str) -> str:
    """
    Normalize LaTeX delimiters to pandoc-friendly syntax.
    ChatGPT uses \\(...\\) and \\[...\\] which pandoc handles fine,
    but also sometimes $...$ / $$...$$ — keep them all.
    """
    # Replace \( ... \) with $ ... $ for inline math
    text = re.sub(r'\\\((.+?)\\\)', r'$\1$', text, flags=re.DOTALL)
    # Replace \[ ... \] with $$ ... $$ for display math
    text = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    return text


# ── Conversion ─────────────────────────────────────────────────────────────────

def convert_to_docx(md_text: str, output_path: str):
    """Convert markdown + LaTeX text to .docx via pandoc."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(md_text)
        tmp_path = tmp.name

    try:
        cmd = [
            "pandoc",
            tmp_path,
            "-o", output_path,
            "--mathml",          # renders math as MathML (supported in Word/LibreOffice)
            "--standalone",
            "--metadata", "lang=zh-TW",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"pandoc error:\n{result.stderr}")
    finally:
        os.unlink(tmp_path)


# ── Main ───────────────────────────────────────────────────────────────────────

def get_input(args) -> tuple[str, str]:
    """Return (text_content, suggested_output_name)."""
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            text = f.read()
        name = os.path.splitext(os.path.basename(args.input))[0] + ".docx"
        return text, name

    if not sys.stdin.isatty():
        text = sys.stdin.read()
        return text, "output.docx"

    # Interactive paste mode
    print("─" * 60)
    print("Paste your ChatGPT text (Markdown + LaTeX).")
    print("When done, press  Enter  then  Ctrl+D  (or Ctrl+Z on Windows).")
    print("─" * 60)
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines), "output.docx"


def main():
    parser = argparse.ArgumentParser(
        description="Convert ChatGPT text (with LaTeX) to Word and upload to web."
    )
    parser.add_argument("input", nargs="?", help="Input markdown file (optional)")
    parser.add_argument("-o", "--output", help="Output .docx filename")
    parser.add_argument("--no-upload", action="store_true",
                        help="Skip upload, keep local file only")
    args = parser.parse_args()

    # 1. Read input
    text, default_name = get_input(args)
    output_path = args.output or default_name

    # 2. Normalize LaTeX delimiters
    print(f"\n[1/3] Normalizing LaTeX …")
    text = normalize_latex(text)

    # 3. Convert to docx
    print(f"[2/3] Converting to Word ({output_path}) via pandoc …")
    convert_to_docx(text, output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"      ✓ {output_path}  ({size_kb:.1f} KB)")

    # 4. Upload
    if args.no_upload:
        print("\n[3/3] Upload skipped (--no-upload).")
        print(f"\nDone! File saved: {os.path.abspath(output_path)}")
        return

    print("[3/3] Uploading …")
    url = upload(output_path)

    print("\n" + "─" * 60)
    print(f"  Download URL: {url}")
    print("─" * 60)
    print(f"  Local copy : {os.path.abspath(output_path)}")
    print()


if __name__ == "__main__":
    main()
