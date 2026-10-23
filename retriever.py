# -*- coding: utf-8 -*-
"""FAQ 검색 엔진.

1단계: difflib.SequenceMatcher (문자열 유사도)
2단계: scikit-learn TF-IDF + 코사인 유사도

두 방식을 같은 인터페이스로 제공해서 평가 스크립트가 방식만 바꿔 비교할 수 있게 한다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import difflib

from normalize import detect_lang, normalize, split_variants

DEFAULT_THRESHOLD = 0.4
DEFAULT_FAQ_PATH = Path(__file__).parent / "data" / "faq.csv"

REQUIRED_COLUMNS = {"id", "question_ko", "question_zh", "answer", "source", "checked_at"}


@dataclass
class Faq:
    id: str
    question_ko: str
    question_zh: str
    answer: str
    source: str
    checked_at: str
    category: str = ""

    def variants(self, lang: str) -> list[str]:
        value = self.question_ko if lang == "ko" else self.question_zh
        out = split_variants(value)
        return out or [""]


def load_faqs(path: Path | str = DEFAULT_FAQ_PATH) -> list[Faq]:
    """CSV를 읽고 스키마를 검사한다. 잘못된 행은 조용히 버리지 않고 알려준다."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"faq.csv 필수 컬럼 누락: {sorted(missing)}")

        faqs: list[Faq] = []
        for lineno, row in enumerate(reader, start=2):
            faq_id = (row.get("id") or "").strip()
            if not faq_id:
                raise ValueError(f"faq.csv {lineno}행: id 가 비어 있습니다.")

            faq = Faq(
                id=faq_id,
                question_ko=(row.get("question_ko") or "").strip(),
                question_zh=(row.get("question_zh") or "").strip(),
                answer=(row.get("answer") or "").strip(),
                source=(row.get("source") or "").strip(),
                checked_at=(row.get("checked_at") or "").strip(),
                category=(row.get("category") or "").strip(),
            )
            if not faq.question_ko and not faq.question_zh:
                raise ValueError(f"faq.csv {lineno}행({faq_id}): 질문이 비어 있습니다.")
            faqs.append(faq)
    return faqs


@dataclass
class Match:
    faq: Faq
    score: float
    method: str


@dataclass
class Retriever:
    faqs: list[Faq]
    threshold: float = DEFAULT_THRESHOLD
    method: str = "difflib"  # 'difflib' | 'tfidf'
    _tfidf: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.method not in {"difflib", "tfidf"}:
            raise ValueError(f"지원하지 않는 방식: {self.method}")

    # ---------- 1단계: difflib ----------
    def _score_difflib(self, query: str, lang: str) -> list[tuple[Faq, float]]:
        q = normalize(query)
        scored = []
        for faq in self.faqs:
            best = 0.0
            for variant in faq.variants(lang):
                ratio = difflib.SequenceMatcher(None, q, normalize(variant)).ratio()
                best = max(best, ratio)
            scored.append((faq, best))
        return scored

    # ---------- 2단계: TF-IDF ----------
    def _score_tfidf(self, query: str, lang: str) -> list[tuple[Faq, float]]:
        # 무거운 의존성은 2단계에서만 필요하므로 지연 임포트한다.
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        cache_key = lang
        if cache_key not in self._tfidf:
            # 한국어/중국어는 공백 분절이 없어 문자 n-gram 이 안정적이다.
            docs, owner = [], []
            for faq in self.faqs:
                for variant in faq.variants(lang):
                    docs.append(normalize(variant))
                    owner.append(faq)
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
            matrix = vectorizer.fit_transform(docs)
            self._tfidf[cache_key] = (vectorizer, matrix, owner)

        vectorizer, matrix, owner = self._tfidf[cache_key]
        query_vec = vectorizer.transform([normalize(query)])
        sims = cosine_similarity(query_vec, matrix)[0]

        best_by_faq: dict[str, tuple[Faq, float]] = {}
        for faq, sim in zip(owner, sims):
            if faq.id not in best_by_faq or sim > best_by_faq[faq.id][1]:
                best_by_faq[faq.id] = (faq, float(sim))
        return list(best_by_faq.values())

    # ---------- 공개 API ----------
    def search(self, query: str, lang: str | None = None, top_k: int = 3) -> list[Match]:
        """유사도 순 상위 top_k 개를 돌려준다(임계값 미적용)."""
        query = (query or "").strip()
        if not query:
            return []
        lang = lang or detect_lang(query)

        scored = self._score_difflib(query, lang) if self.method == "difflib" else self._score_tfidf(query, lang)
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [Match(faq=faq, score=score, method=self.method) for faq, score in scored[:top_k]]

    def answer(self, query: str, lang: str | None = None) -> Match | None:
        """임계값을 넘는 최상위 1건을 반환한다. 없으면 None(= 사무실 문의 안내)."""
        lang = lang or detect_lang(query)
        results = self.search(query, lang=lang, top_k=1)
        if not results:
            return None
        best = results[0]
        return best if best.score >= self.threshold else None
