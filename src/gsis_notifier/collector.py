from __future__ import annotations

import html as html_lib
import json
import logging
import re
import unicodedata
from datetime import date, datetime, time, timezone
from typing import Any, Iterable
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import Article, CollectionOutcome

LOGGER = logging.getLogger(__name__)
DOI_PREFIX = "10.1080/10095020"
DOI_RE = re.compile(r"10\.1080/10095020(?:\.\d+)+", re.IGNORECASE)
CANONICAL_PREFIX = "https://www.tandfonline.com/doi/full/"
DEFAULT_CROSSREF_URL = "https://api.crossref.org/journals/1009-5020/works"
DEFAULT_DOAJ_URL = "https://doaj.org/api/search/articles"
DEFAULT_DOAJ_ISSN = "1993-5153"


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    decoded = unquote(value).strip()
    match = DOI_RE.search(decoded)
    return match.group(0).lower().rstrip(".,;)") if match else ""


def canonical_link(doi: str) -> str:
    return f"{CANONICAL_PREFIX}{doi}"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(html_lib.unescape(value).split())


def _split_keywords(raw_values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for part in re.split(r"\s*[;,|]\s*", raw):
            keyword = _clean_text(part)
            key = keyword.casefold()
            if keyword and key not in seen:
                seen.add(key)
                result.append(keyword)
    return result


def _crossref_date(item: dict[str, Any]) -> str | None:
    for key in ("published-online", "published", "issued", "created"):
        value = item.get(key)
        if key == "created" and isinstance(value, dict):
            timestamp = value.get("date-time")
            if timestamp:
                return str(timestamp)
        if isinstance(value, dict):
            parts = value.get("date-parts")
            if parts and isinstance(parts, list) and parts[0]:
                values = [int(part) for part in parts[0]]
                return "-".join(
                    f"{part:02d}" if index else str(part)
                    for index, part in enumerate(values)
                )
    return None


def _crossref_abstract(value: str | None) -> str:
    if not value:
        return ""
    return _clean_text(BeautifulSoup(value, "lxml").get_text(" ", strip=True))


def _crossref_title(value: str | None) -> str:
    if not value:
        return ""
    # Crossref titles may contain inline math markup such as NO<sub>2</sub>.
    # Removing sub/sup tags before stripping other markup preserves NO2 rather
    # than introducing a false space that would break title verification.
    without_scripts = re.sub(
        r"\s*<(?:sub|sup)(?:\s[^>]*)?>|</(?:sub|sup)>", "", value, flags=re.I
    )
    return _clean_text(BeautifulSoup(without_scripts, "lxml").get_text(" ", strip=True))


def _doaj_doi(bibjson: dict[str, Any]) -> str:
    for identifier in bibjson.get("identifier") or []:
        if not isinstance(identifier, dict):
            continue
        if str(identifier.get("type") or "").casefold() == "doi":
            return normalize_doi(str(identifier.get("id") or ""))
    return ""


def _parse_crossref_items(items: Iterable[dict[str, Any]]) -> dict[str, Article]:
    articles: dict[str, Article] = {}
    for item in items:
        doi = normalize_doi(str(item.get("DOI") or ""))
        if not doi.startswith(DOI_PREFIX):
            continue

        containers = " ".join(str(x) for x in item.get("container-title") or [])
        if containers and "geo-spatial information science" not in containers.casefold():
            continue

        titles = item.get("title") or []
        title = _crossref_title(str(titles[0])) if titles else ""
        if not title:
            continue

        articles[doi] = Article(
            doi=doi,
            title=title,
            link=canonical_link(doi),
            abstract=_crossref_abstract(item.get("abstract")),
            keywords=[],
            published_online=_crossref_date(item),
            source="crossref-publisher-deposit",
        )
    return articles


def _parse_doaj_results(results: Iterable[dict[str, Any]]) -> dict[str, Article]:
    articles: dict[str, Article] = {}
    for result in results:
        bibjson = result.get("bibjson")
        if not isinstance(bibjson, dict):
            continue

        doi = _doaj_doi(bibjson)
        if not doi.startswith(DOI_PREFIX):
            continue

        journal = bibjson.get("journal") or {}
        journal_title = _clean_text(str(journal.get("title") or ""))
        if journal_title and journal_title.casefold() != "geo-spatial information science":
            continue

        keywords = bibjson.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = [str(keywords)]

        articles[doi] = Article(
            doi=doi,
            title=_clean_text(str(bibjson.get("title") or "")),
            link=canonical_link(doi),
            abstract=_clean_text(str(bibjson.get("abstract") or "")),
            keywords=_split_keywords(str(keyword) for keyword in keywords),
            published_online=None,
            source="doaj",
        )
    return articles


def _same_title(left: str, right: str) -> bool:
    def key(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", _clean_text(value)).casefold()
        return re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)

    return bool(key(left)) and key(left) == key(right)


class GSISCollector:
    def __init__(
        self,
        crossref_url: str = DEFAULT_CROSSREF_URL,
        doaj_url: str = DEFAULT_DOAJ_URL,
        doaj_issn: str = DEFAULT_DOAJ_ISSN,
        timeout: int = 30,
        user_agent: str = "GSIS-Notifier/0.2.1",
        session: requests.Session | None = None,
    ) -> None:
        self.crossref_url = crossref_url.rstrip("/")
        self.doaj_url = doaj_url.rstrip("/")
        self.doaj_issn = doaj_issn.strip()
        self.timeout = timeout
        self.session = session or self._build_session(user_agent)

    @staticmethod
    def _build_session(user_agent: str) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json",
            }
        )
        return session

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    def _discover_crossref(self, since: date) -> dict[str, Article]:
        from_date = datetime.combine(since, time.min, tzinfo=timezone.utc).date().isoformat()
        response = self._get(
            self.crossref_url,
            params={
                "filter": f"from-online-pub-date:{from_date}",
                "sort": "published",
                "order": "desc",
                "rows": 100,
                "select": "DOI,title,abstract,published,published-online,issued,created,URL,container-title",
            },
        )
        items = response.json().get("message", {}).get("items", [])
        if not isinstance(items, list):
            raise ValueError("Crossref response does not contain a valid items list")
        return _parse_crossref_items(item for item in items if isinstance(item, dict))

    def _discover_doaj(self) -> dict[str, Article]:
        query = f"bibjson.journal.issns.exact:{self.doaj_issn}"
        response = self._get(
            f"{self.doaj_url}/{query}",
            params={
                "pageSize": 100,
                "sort": "created_date:desc",
            },
        )
        results = response.json().get("results", [])
        if not isinstance(results, list):
            raise ValueError("DOAJ response does not contain a valid results list")
        return _parse_doaj_results(
            result for result in results if isinstance(result, dict)
        )

    def collect(self, since: date) -> CollectionOutcome:
        errors: list[str] = []
        crossref_ok = False
        doaj_ok = False
        crossref_articles: dict[str, Article] = {}
        doaj_articles: dict[str, Article] = {}

        try:
            crossref_articles = self._discover_crossref(since)
            crossref_ok = True
        except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"Crossref discovery failed: {exc}")

        try:
            doaj_articles = self._discover_doaj()
            doaj_ok = True
        except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"DOAJ metadata retrieval failed: {exc}")

        articles: list[Article] = []
        for doi, crossref_article in crossref_articles.items():
            doaj_article = doaj_articles.get(doi)

            if doaj_article is None:
                if crossref_article.is_summarizable:
                    articles.append(crossref_article)
                else:
                    errors.append(
                        f"Pending {doi}: DOAJ has not provided a complete abstract yet"
                    )
                continue

            if not _same_title(crossref_article.title, doaj_article.title):
                errors.append(
                    f"Pending {doi}: Crossref/DOAJ title mismatch; metadata not merged"
                )
                continue

            abstract = doaj_article.abstract or crossref_article.abstract
            source = "crossref+doaj" if doaj_article.abstract else "crossref-publisher-deposit"
            merged = Article(
                doi=doi,
                title=crossref_article.title,
                link=canonical_link(doi),
                abstract=abstract,
                keywords=doaj_article.keywords,
                published_online=crossref_article.published_online,
                source=source,
            )
            if merged.is_summarizable:
                articles.append(merged)
            else:
                errors.append(
                    f"Pending {doi}: complete verified metadata is not available yet"
                )

        unique = {article.doi: article for article in articles}
        ordered = sorted(
            unique.values(), key=lambda article: article.published_online or "", reverse=True
        )
        LOGGER.info("Collected %d summarizable GSIS articles", len(ordered))
        return CollectionOutcome(
            articles=ordered,
            errors=errors,
            crossref_source_succeeded=crossref_ok,
            doaj_source_succeeded=doaj_ok,
        )
