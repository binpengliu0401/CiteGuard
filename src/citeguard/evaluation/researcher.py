"""Gold-dataset contracts and metrics for Researcher paper assessment."""

from collections.abc import Iterable, Mapping
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
    RelevanceLevel,
    derive_relevance,
)

FACTOR_FIELDS = (
    "object_match",
    "problem_match",
    "constraint_match",
    "evidence_kind",
    "answer_coverage",
)
SCORED_RELEVANCE_LEVELS = (
    RelevanceLevel.DIRECT,
    RelevanceLevel.PARTIAL,
    RelevanceLevel.BACKGROUND,
    RelevanceLevel.IRRELEVANT,
)
PREDICTED_RELEVANCE_LEVELS = (*SCORED_RELEVANCE_LEVELS, RelevanceLevel.UNKNOWN)
DEFAULT_RELEVANCE_GRADES = {
    RelevanceLevel.DIRECT.value: 3,
    RelevanceLevel.PARTIAL.value: 2,
    RelevanceLevel.BACKGROUND.value: 1,
    RelevanceLevel.IRRELEVANT.value: 0,
}


class FactorJudgment(BaseModel):
    """One factorized relevance judgment using the production vocabulary."""

    model_config = ConfigDict(extra="forbid")

    object_match: MatchLevel
    problem_match: MatchLevel
    constraint_match: ConstraintMatch
    evidence_kind: EvidenceKind
    answer_coverage: AnswerCoverage

    @property
    def relevance(self) -> RelevanceLevel:
        """Derive the label with the same deterministic production policy."""

        return derive_relevance(
            object_match=self.object_match,
            problem_match=self.problem_match,
            constraint_match=self.constraint_match,
            evidence_kind=self.evidence_kind,
            answer_coverage=self.answer_coverage,
        )


class GoldAssessment(FactorJudgment):
    """One human-reviewable candidate annotation for a fixed subquestion."""

    item_id: str
    original_question: str
    subquestion: str
    source_id: str
    source_version_url: str
    title: str
    gold_relevance: RelevanceLevel
    annotation_reason: str

    @field_validator(
        "original_question",
        "subquestion",
        "title",
        "annotation_reason",
        mode="before",
    )
    @classmethod
    def join_wrapped_text(cls, value: object) -> object:
        """Join JSON text segments used to keep Eval data reviewable."""

        if not isinstance(value, list):
            return value
        if not value or not all(isinstance(part, str) for part in value):
            raise ValueError("wrapped Gold text must contain string segments")
        return " ".join(part.strip() for part in value)

    @field_validator(
        "item_id",
        "original_question",
        "subquestion",
        "source_id",
        "source_version_url",
        "title",
        "annotation_reason",
    )
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        """Reject incomplete annotation records."""

        if not value.strip():
            raise ValueError("gold assessment text must not be blank")
        return value

    @model_validator(mode="after")
    def validate_gold_label(self) -> Self:
        """Require a resolved four-class label consistent with Gold factors."""

        if self.gold_relevance is RelevanceLevel.UNKNOWN:
            raise ValueError(
                "unknown is a prediction abstention, not a Gold label"
            )
        if self.gold_relevance is not self.relevance:
            raise ValueError(
                "gold_relevance must match the factor-derived label"
            )
        return self


class ResearcherGoldDataset(BaseModel):
    """A versioned Researcher assessment dataset awaiting or carrying review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["3"]
    dataset_id: str
    version: str
    annotation_status: Literal["draft", "reviewed", "frozen"]
    subquestion_origin: Literal["manual", "planner"]
    relevance_grades: dict[str, int]
    items: list[GoldAssessment] = Field(min_length=1)

    @field_validator("dataset_id", "version")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        """Require stable dataset identity fields."""

        if not value.strip():
            raise ValueError("dataset identity must not be blank")
        return value

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Reject duplicate items and unstable relevance-grade mappings."""

        if self.relevance_grades != DEFAULT_RELEVANCE_GRADES:
            raise ValueError(
                "relevance_grades must use direct=3, partial=2, "
                "background=1, irrelevant=0"
            )

        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Gold item IDs must be unique")
        return self


class PredictedAssessment(FactorJudgment):
    """One system prediction matched to a Gold item by ID."""

    item_id: str

    @field_validator("item_id")
    @classmethod
    def item_id_must_not_be_blank(cls, value: str) -> str:
        """Require a usable Gold lookup key."""

        if not value.strip():
            raise ValueError("prediction item_id must not be blank")
        return value


class ResearcherPredictionSet(BaseModel):
    """Predictions for exactly one versioned Researcher Gold dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    system_id: str
    predictions: list[PredictedAssessment] = Field(min_length=1)

    @field_validator("dataset_id", "dataset_version", "system_id")
    @classmethod
    def prediction_identity_must_not_be_blank(cls, value: str) -> str:
        """Require enough identity to compare reports across system versions."""

        if not value.strip():
            raise ValueError("prediction identity must not be blank")
        return value

    @model_validator(mode="after")
    def prediction_ids_must_be_unique(self) -> Self:
        """Prevent later predictions from silently overwriting earlier ones."""

        item_ids = [prediction.item_id for prediction in self.predictions]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("prediction item IDs must be unique")
        return self


def evaluate_assessments(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> dict[str, object]:
    """Compare factor judgments and derived relevance against resolved Gold.

    Unknown predictions are reported as abstentions. They are not a fifth Gold
    class, but they still count as false negatives for the resolved Gold class.
    """

    _validate_prediction_coverage(dataset, prediction_set)
    predictions_by_id = {
        prediction.item_id: prediction
        for prediction in prediction_set.predictions
    }

    factor_correct = {field: 0 for field in FACTOR_FIELDS}
    confusion = {
        gold.value: {
            predicted.value: 0
            for predicted in PREDICTED_RELEVANCE_LEVELS
        }
        for gold in SCORED_RELEVANCE_LEVELS
    }

    for item in dataset.items:
        prediction = predictions_by_id[item.item_id]
        for field in FACTOR_FIELDS:
            if getattr(item, field) == getattr(prediction, field):
                factor_correct[field] += 1
        confusion[item.gold_relevance.value][prediction.relevance.value] += 1

    total = len(dataset.items)
    per_factor = {
        field: _ratio(correct, total)
        for field, correct in factor_correct.items()
    }
    total_factor_decisions = total * len(FACTOR_FIELDS)
    relevance_accuracy = _ratio(
        sum(
            confusion[level.value][level.value]
            for level in SCORED_RELEVANCE_LEVELS
        ),
        total,
    )
    per_class = _per_class_metrics(confusion)
    predicted_direct = sum(
        row[RelevanceLevel.DIRECT.value] for row in confusion.values()
    )
    direct_true_positive = confusion[RelevanceLevel.DIRECT.value][
        RelevanceLevel.DIRECT.value
    ]
    unknown_count = sum(
        row[RelevanceLevel.UNKNOWN.value] for row in confusion.values()
    )

    return {
        "dataset": {
            "schema_version": dataset.schema_version,
            "dataset_id": dataset.dataset_id,
            "version": dataset.version,
            "annotation_status": dataset.annotation_status,
            "subquestion_origin": dataset.subquestion_origin,
            "items": total,
        },
        "system_id": prediction_set.system_id,
        "factor_accuracy": {
            "overall": _ratio(
                sum(factor_correct.values()),
                total_factor_decisions,
            ),
            "by_factor": per_factor,
        },
        "relevance": {
            "accuracy": relevance_accuracy,
            "macro_f1": _mean(
                per_class[level.value]["f1"]
                for level in SCORED_RELEVANCE_LEVELS
            ),
            "direct_precision": (
                _ratio(direct_true_positive, predicted_direct)
                if predicted_direct
                else None
            ),
            "unknown_abstention_rate": _ratio(unknown_count, total),
            "per_class": per_class,
            "confusion_matrix": confusion,
        },
    }


def _validate_prediction_coverage(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> None:
    """Require predictions to identify and cover exactly one dataset version."""

    if prediction_set.dataset_id != dataset.dataset_id:
        raise ValueError("prediction dataset_id does not match Gold dataset")
    if prediction_set.dataset_version != dataset.version:
        raise ValueError(
            "prediction dataset_version does not match Gold dataset"
        )

    gold_ids = {item.item_id for item in dataset.items}
    prediction_ids = {
        prediction.item_id for prediction in prediction_set.predictions
    }
    missing = sorted(gold_ids - prediction_ids)
    unexpected = sorted(prediction_ids - gold_ids)
    if missing or unexpected:
        raise ValueError(
            "prediction IDs must exactly match Gold; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _per_class_metrics(
    confusion: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, float]]:
    """Calculate one-vs-rest precision, recall, and F1 for four Gold classes."""

    metrics: dict[str, dict[str, float]] = {}
    for level in SCORED_RELEVANCE_LEVELS:
        label = level.value
        true_positive = confusion[label][label]
        predicted_positive = sum(row[label] for row in confusion.values())
        actual_positive = sum(confusion[label].values())
        precision = _ratio(true_positive, predicted_positive)
        recall = _ratio(true_positive, actual_positive)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": round(f1, 6),
        }
    return metrics


def _ratio(numerator: int, denominator: int) -> float:
    """Return a stable six-decimal ratio for JSON reports."""

    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: Iterable[float]) -> float:
    """Average a finite metric sequence without adding a numeric dependency."""

    materialized = list(values)
    return round(sum(materialized) / len(materialized), 6)
