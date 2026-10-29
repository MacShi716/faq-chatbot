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

# 질문에 키워드 태그가 그대로 들어 있으면 이 점수를 최소값으로 올려준다.
# (짧은 태그는 문자열 유사도가 낮게 나와서, 명백한 키워드 일치를 놓치는 문제를 보정)
TAG_HIT_SCORE = 0.7

REQUIRED_COLUMNS = {"id", "question_ko", "question_zh", "answer", "source", "checked_at"}

# 아직 확인하지 않은 답변을 표시하는 문자열. 이게 들어 있으면 "미작성"으로 본다.
PLACEHOLDER_MARKERS = ("[작성 필요]", "[작성 예정]", "[待填写]")


def is_filled(text: str) -> bool:
    """사람이 확인해 채운 답변인지. 빈 값이나 [작성 필요] 는 미작성으로 본다."""
    value = (text or "").strip()
    if not value:
        return False
    return not any(marker in value for marker in PLACEHOLDER_MARKERS)


@dataclass
class Faq:
    id: str
    question_ko: str
    question_zh: str
    answer: str
    source: str
    checked_at: str
    category: str = ""
    answer_zh: str = ""
    tags: str = ""

    def variants(self, lang: str) -> list[str]:
        value = self.question_ko if lang == "ko" else self.question_zh
        out = split_variants(value)
        return out or [""]

    def tag_list(self) -> list[str]:
        """언어와 무관한 키워드. 중국어 질문이 한국어 FAQ 에 붙을 수 있게 하는 다리 역할."""
        return split_variants(self.tags)

    def search_terms(self, lang: str) -> list[str]:
        """검색에 쓰는 모든 문자열: 질문 표현 + 키워드 태그."""
        return self.variants(lang) + self.tag_list()

    def answer_for(self, ui_lang: str) -> tuple[str, bool]:
        """표시할 답변과 '한국어 원문 폴백' 여부를 돌려준다.

        중국어 화면에서 answer_zh 가 채워져 있으면 그것을 쓰고,
        없으면 한국어 원문을 쓰되 폴백 표시를 켠다.
        """
        if ui_lang == "zh":
            # 중국어 초안이 있으면(미확인 [待填写] 표시 포함) 중국어로 보여준다.
            # 미확인 여부는 화면의 '미확인 답변' 배지가 따로 알려준다.
            if (self.answer_zh or "").strip():
                return self.answer_zh.strip(), False
            return self.answer, True
        return self.answer, False


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
                answer_zh=(row.get("answer_zh") or "").strip(),
                tags=(row.get("tags") or "").strip(),
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
            for term in faq.search_terms(lang):
                ratio = difflib.SequenceMatcher(None, q, normalize(term)).ratio()
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
                for term in faq.search_terms(lang):
                    docs.append(normalize(term))
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
    def _tag_hits(self, faq: Faq, q_norm: str) -> int:
        """질문에 통째로 들어 있는 태그 개수."""
        return sum(1 for tag in (normalize(x) for x in faq.tag_list()) if len(tag) >= 2 and tag in q_norm)

    def _tag_hit(self, faq: Faq, q_norm: str) -> bool:
        """정규화된 질문 안에 2글자 이상 태그가 통째로 들어 있는지."""
        return self._tag_hits(faq, q_norm) > 0

    def search(self, query: str, lang: str | None = None, top_k: int = 3) -> list[Match]:
        """유사도 순 상위 top_k 개를 돌려준다(임계값 미적용)."""
        query = (query or "").strip()
        if not query:
            return []
        lang = lang or detect_lang(query)
        q_norm = normalize(query)

        scored = self._score_difflib(query, lang) if self.method == "difflib" else self._score_tfidf(query, lang)
        adjusted = []
        for faq, score in scored:
            hits = self._tag_hits(faq, q_norm)
            if hits:
                score = max(score, TAG_HIT_SCORE)
            adjusted.append((faq, score, hits))

        # 동점 처리: ① 유사도 ② 태그 적중 수 ③ 질문이 짧은 쪽(더 구체적) ④ id
        adjusted.sort(key=lambda row: (-row[1], -row[2], len(normalize(row[0].question_ko)), row[0].id))
        return [Match(faq=faq, score=score, method=self.method) for faq, score, _ in adjusted[:top_k]]

    def answer(self, query: str, lang: str | None = None) -> Match | None:
        """임계값을 넘는 최상위 1건을 반환한다. 없으면 None(= 사무실 문의 안내)."""
        lang = lang or detect_lang(query)
        results = self.search(query, lang=lang, top_k=1)
        if not results:
            return None
        best = results[0]
        return best if best.score >= self.threshold else None
