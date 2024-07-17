import json
import os
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from time import sleep

import pypandoc
import requests
from bs4 import BeautifulSoup

_publishers = list()
_publisher_domains = dict()
_publisher_names = list()


class Publisher(ABC):
    """General class for scientific article publishers"""

    def __init__(self, url, doi=None, out_format="epub"):
        self.url = url
        self.doi = doi

    def get_final_url(self):
        pass

    def check_fulltext(self):
        pass

    def soupify(self):
        try:
            return self.soupify_webdriver()
        except (ImportError, OSError):
            return self.soupify_localfile()

    def soupify_localfile(self):
        while True:
            path = input("Local .html file path (use SingleFile extension):\n")
            if os.path.exists(path):
                break
            print("File not found")

        with open(path) as handle:
            self.soup = BeautifulSoup(handle, "html.parser")

    def soupify_webdriver(self):
        """Get HTML from article's page"""
        from selenium import webdriver  # type: ignore noqa: F401
        from selenium.webdriver.firefox.firefox_binary import FirefoxBinary  # type: ignore noqa: F401

        self.get_final_url()
        os.environ["MOZ_HEADLESS"] = "1"
        print("Starting headless browser...", end="", flush=True)

        if os.name == "posix":
            binary = FirefoxBinary("firefox")
        elif os.name == "nt":
            binary = FirefoxBinary("C:/Program Files/Mozilla Firefox/firefox.exe")
        else:
            raise OSError("Unknown OS")

        try:
            driver_options = webdriver.FirefoxOptions()
            driver_options.binary = binary
            driver = webdriver.Firefox(options=driver_options)
            print("done")
        except Exception as e:
            print(e)
            raise OSError("Failed to load Firefox; is it installed?")

        print("Loading page................", end="", flush=True)
        driver.get(self.url)

        if self.doi is not None:
            sleep(5)  # To allow redirects

        sleep(5)
        print("done")
        self.url = driver.current_url

        self.soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

    def doi2json(self):
        """Get a dictionary of metadata for a given DOI."""
        url = "http://dx.doi.org/" + self.doi
        headers = {"accept": "application/json"}
        r = requests.get(url, headers=headers)
        self.meta = r.json()

    @abstractmethod
    def get_doi(self):
        pass

    def get_metadata(self):
        """Extract metadata from DOI"""
        self.doi2json()

        self.title = self.meta["title"]

        self.author_surnames = []
        self.author_givennames = []
        for i in self.meta["author"]:
            self.author_surnames.append(i["family"])
            self.author_givennames.append(i["given"])

        self.journal = self.meta["container-title"]

        if "published-print" in self.meta.keys():
            self.year = str(self.meta["published-print"]["date-parts"][0][0])
        else:
            self.year = str(self.meta["published-online"]["date-parts"][0][0])

        try:
            self.volume = str(self.meta["volume"])
        except Exception:
            self.volume = ""

        try:
            self.pages = str(self.meta["page"])
        except Exception:
            self.pages = ""

    @abstractmethod
    def get_abstract(self):
        pass

    @abstractmethod
    def get_keywords(self):
        pass

    @abstractmethod
    def get_body(self):
        pass

    @abstractmethod
    def get_references(self):
        pass

    def get_citation(self, link=False):
        """Generate a formatted citation from metadata"""
        all_authors = "; ".join(
            f"{surname}, {given_name}"
            for surname, given_name in zip(self.author_surnames, self.author_givennames, strict=True)
        )

        all_authors = all_authors.strip(".")

        if link:
            doi = f'<a href="https://dx.doi.org/{self.doi}">{self.doi}</a>'
        else:
            doi = self.doi

        if self.volume != "":
            return f"{all_authors}. {self.year}. {self.title}. {self.journal} {self.volume}; {self.pages}. doi: {doi}"
        else:
            return f"{all_authors}. {self.year}. {self.title}. {self.journal}. doi: {doi}"

    def extract_data(self):
        self.check_fulltext()
        print("Extracting data from HTML...", end="", flush=True)
        self.get_doi()
        self.get_metadata()
        self.get_abstract()
        self.get_keywords()
        self.get_body()
        self.get_references()
        print("done")

    def epubify(self, output=None):
        """Convert data into epub format"""

        all_authors = "; ".join(
            f"{surname}, {given_name}"
            for surname, given_name in zip(self.author_surnames, self.author_givennames, strict=True)
        )

        args = []
        args.append("-M")
        args.append('title="' + self.title + '"')
        args.append("-M")
        args.append('author="' + all_authors + '"')
        # args.append('--parse-raw')
        args.append("--webtex")

        if output is None:
            self.output = f"{self.author_surnames[0]}_{self.year}.epub"
        else:
            self.output = output

        output_raw = os.path.join(tempfile.gettempdir(), "raw.epub")

        combined = f"{self.get_citation(link=True)}{self.abstract}{self.body}{self.references}"

        print("Generating epub.............", end="", flush=True)
        pypandoc.convert_text(combined, format="html", to="epub+raw_html", extra_args=args, outputfile=output_raw)

        if shutil.which("ebook-convert") is None:
            raise OSError("Failed to find ebook-convert, is Calibre installed?")

        subprocess.check_output(["ebook-convert", output_raw, self.output, "--no-default-epub-cover"])
        print("done")


def register_publisher(publisher):
    _publishers.append(publisher)
    _publisher_names.append(publisher.name)
    for d in publisher.domains:
        _publisher_domains[d] = publisher


def get_publishers():
    return _publisher_domains


def list_publishers():
    return _publisher_names


def match_publisher(url, doi):
    """Match a URL to a publisher class"""
    domain = ".".join(url.split("//")[-1].split("/")[0].split("?")[0].split(".")[-2:])
    if domain == "doi.org":
        sys.exit("DOI not found; is it correct?")

    try:
        art = get_publishers()[domain](url=url, doi=doi)
        print("Matched URL to publisher: " + art.name)
        return art
    except Exception:
        sys.exit("Publisher [" + domain + "] not supported.")
