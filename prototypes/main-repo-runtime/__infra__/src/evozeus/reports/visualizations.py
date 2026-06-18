from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from evozeus.factors.protocol import FactorResult


@dataclass(frozen=True)
class WordCloudTerm:
    text: str
    weight: int
    source_factor_ids: list[str]


@dataclass(frozen=True)
class ResultVisualization:
    component: str
    title: str
    description: str
    input_fields: list[str]
    output_fields: list[str]
    terms: list[WordCloudTerm]


def build_result_visualizations(results: list[FactorResult]) -> list[ResultVisualization]:
    return [_build_word_cloud(results)]


def _build_word_cloud(results: list[FactorResult]) -> ResultVisualization:
    weights: Counter[str] = Counter()
    sources: dict[str, set[str]] = defaultdict(set)
    for result in results:
        for term in _terms_from_result(result):
            weights[term] += 1
            sources[term].add(result.factor_id)

    terms = [
        WordCloudTerm(text=text, weight=weight, source_factor_ids=sorted(sources[text]))
        for text, weight in weights.items()
    ]
    terms.sort(key=lambda term: (-term.weight, term.text))
    return ResultVisualization(
        component="word_cloud",
        title="高频信号词云",
        description="从 selected FactorResult 的 tags 和 verdict signals 中聚合高频词，保留 factor 来源用于追溯。",
        input_fields=["tags.type", "tags.value", "verdict_signals", "factor_id"],
        output_fields=["terms.text", "terms.weight", "terms.source_factor_ids"],
        terms=terms,
    )


def _terms_from_result(result: FactorResult) -> list[str]:
    terms: list[str] = []
    for tag in result.tags:
        value = _clean_term(tag.get("value"))
        tag_type = _clean_term(tag.get("type"))
        if value:
            terms.append(value)
        elif tag_type:
            terms.append(tag_type)
    terms.extend(_clean_term(verdict) for verdict in result.verdict_signals)
    return [term for term in terms if term]


def _clean_term(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
