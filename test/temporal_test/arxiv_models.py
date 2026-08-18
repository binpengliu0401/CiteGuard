from dataclasses import dataclass


@dataclass
class ArxivSearchInput:
    queries: list[str]
    max_results: int = 3


@dataclass
class ArxivPaper:
    title: str
    arxiv_id: str
    summary: str
    url: str


@dataclass
class ArxivQueryResult:
    query: str
    papers: list[ArxivPaper]
