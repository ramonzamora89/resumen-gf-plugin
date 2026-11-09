#!/usr/bin/env python3
"""Renderiza docs/manual.html a manual-instalacion.pdf (raíz del repositorio).

Usa Chrome o Edge sin ventana (headless), que respeta @page, el pie de página y la portada.
WeasyPrint se cae en Windows (SIGSEGV por fontconfig), por eso no se usa aquí.

Uso: python docs/build_manual.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_DIR = DOCS_DIR.parent

CANDIDATOS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def navegador():
    for c in CANDIDATOS:
        if Path(c).exists():
            return c
    for n in ("google-chrome", "chromium", "chrome", "msedge"):
        if shutil.which(n):
            return shutil.which(n)
    sys.exit("No encontré Chrome ni Edge para generar el PDF.")


def main():
    html_path = DOCS_DIR / "manual.html"
    pdf_path = REPO_DIR / "manual-instalacion.pdf"
    subprocess.run([
        navegador(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ], check=True, capture_output=True)
    print(f"PDF generado: {pdf_path}")


if __name__ == "__main__":
    main()
