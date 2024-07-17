import subprocess
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


def ensure_calibre_installed():
    try:
        subprocess.run(["ebook-convert", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("ebook-convert is installed and available.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        msg = "ebook-convert is not installed or not found in PATH. Please install Calibre and ensure ebook-convert is available in your PATH."
        raise RuntimeError(msg) from None


def url_from_title(title: str):
    print("Getting URL from title......")
    url_stem = "https://scholar.google.com/scholar?hl=en&as_sdt=0%2C49&q="
    search = title.replace(" ", "+").replace("\n", "").strip('"')
    full_url = f'{url_stem}"{search}"'

    try:
        out = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(out.content, "html.parser")
        result = soup.find("div", class_="gs_scl").find("div", class_="gs_ri").find("a")
        possible_title = result.text
        possible_link = result["href"]

        if possible_title == "":
            raise ValueError("Getting URL from title failed: No matching link available.")

        print("Provided title:")
        print(title)
        print("Found following article:")
        print(possible_title)
        choice = input("\033[0;37m" + "Is this correct (y/n)? " + "\033[00m").lower()
        if choice == "y":
            return possible_link
        else:
            raise ValueError("Getting URL from title failed")
    except Exception as e:
        raise ValueError("Getting URL from title failed") from e


def url_from_doi(doi: str):
    print("Getting URL from DOI........", end="", flush=True)
    r = requests.get(f"https://doi.org/{doi}", headers={"User-Agent": "Mozilla/5.0"})

    # To handle Elsevier linkinghub redirects
    soup = BeautifulSoup(r.content, "html.parser")
    if soup.find("input", {"id": "redirectURL"}) is not None:
        url_raw = soup.find("input", {"id": "redirectURL"})["value"]
        url = unquote(url_raw.split("_returnURL")[0])
    else:
        url = r.url

    print("done")
    return url
