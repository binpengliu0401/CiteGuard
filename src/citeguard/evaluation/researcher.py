"""Gold contracts and metrics for paper relevance and MEG selection."""

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
from citeguard.researcher.schemas import GroupSupport

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
PREDICTED_RELEVANCE_LEVELS = (
    *SCORED_RELEVANCE_LEVELS,
    RelevanceLevel.UNKNOWN,
)
GROUP_SUPPORT_LEVELS = (
    GroupSupport.FULL,
    GroupSupport.PARTIAL,
    GroupSupport.NONE,
)
DEFAULT_RELEVANCE_GRADES = {
    RelevanceLevel.DIRECT.value: 3,
    RelevanceLevel.PARTIAL.value: 2,
    RelevanceLevel.BACKGROUND.value: 1,
    RelevanceLevel.IRRELEVANT.value: 0,
}


class FactorJudgment(BaseModel):
    """One factorized relevance judgment using production vocabulary."""

    model_config = ConfigDict(extra="forbid")

    object_match: MatchLevel
    problem_match: MatchLevel
    constraint_match: ConstraintMatch
    evidence_kind: EvidenceKind
    answer_coverage: AnswerCoverage

    @property
    def relevance(self) -> RelevanceLevel:
        """Derive the label with the production classification policy."""

        return derive_relevance(
            object_match=self.object_match,
            problem_match=self.problem_match,
            constraint_match=self.constraint_match,
            evidence_kind=self.evidence_kind,
            answer_coverage=self.answer_coverage,
        )


class GoldAssessment(FactorJudgment):
    """One human-reviewable paper annotation within a fixed case."""

    item_id: str
    case_id: str
    source_id: str
    source_version_url: str
    title: str
    gold_relevance: RelevanceLevel
    annotation_reason: str

    @field_validator("title", "annotation_reason", mode="before")
    @classmethod
    def join_wrapped_text(cls, value: object) -> object:
        """Join JSON segments used to keep Eval lines reviewable."""

        return _join_wrapped_text(value)

    @field_validator(
        "item_id",
        "case_id",
        "source_id",
        "source_version_url",
        "title",
        "annotation_reason",
    )
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        """Reject incomplete paper annotations."""

        if not value.strip():
            raise ValueError("gold assessment text must not be blank")
        return value

    @model_validator(mode="after")
    def validate_gold_label(self) -> Self:
        """Require a resolved label consistent with factorized Gold."""

        if self.gold_relevance is RelevanceLevel.UNKNOWN:
            raise ValueError(
                "unknown is a prediction abstention, not a Gold label"
            )
        if self.gold_relevance is not self.relevance:
            raise ValueError(
                "gold_relevance must match the factor-derived label"
            )
        return self


class GoldRequirement(BaseModel):
    """One fixed completeness requirement in an Eval research case."""

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    description: str

    @field_validator("description", mode="before")
    @classmethod
    def join_description(cls, value: object) -> object:
        """Join review-oriented JSON text segments."""

        return _join_wrapped_text(value)

    @field_validator("requirement_id", "description")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Require usable requirement identity and content."""

        if not value.strip():
            raise ValueError("Gold requirement text must not be blank")
        return value


class GroupLabel(BaseModel):
    """Gold or predicted support label for one exact source group."""

    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(min_length=1)
    support: GroupSupport

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_be_unique(cls, values: list[str]) -> list[str]:
        """Require nonblank, unique source IDs in a group."""

        return _validate_id_list(values, "group source IDs")


class GoldResearchCase(BaseModel):
    """One fixed target with paper candidates and Gold MEGs."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    original_question: str
    subquestion: str
    primary_answer_target: str
    answer_requirements: list[GoldRequirement] = Field(min_length=1)
    candidate_item_ids: list[str] = Field(min_length=1)
    group_assessments: list[GroupLabel] = Field(min_length=1)
    gold_megs: list[list[str]] = Field(min_length=1)

    @field_validator(
        "original_question",
        "subquestion",
        "primary_answer_target",
        mode="before",
    )
    @classmethod
    def join_case_text(cls, value: object) -> object:
        """Join review-oriented JSON text segments."""

        return _join_wrapped_text(value)

    @field_validator(
        "case_id",
        "original_question",
        "subquestion",
        "primary_answer_target",
    )
    @classmethod
    def case_text_must_not_be_blank(cls, value: str) -> str:
        """Reject incomplete target annotations."""

        if not value.strip():
            raise ValueError("Gold case text must not be blank")
        return value

    @field_validator("candidate_item_ids")
    @classmethod
    def candidate_items_must_be_unique(
        cls,
        values: list[str],
    ) -> list[str]:
        """Require unique candidate item references."""

        return _validate_id_list(values, "candidate item IDs")

    @field_validator("gold_megs")
    @classmethod
    def gold_megs_must_be_valid(
        cls,
        values: list[list[str]],
    ) -> list[list[str]]:
        """Require unique, nonempty source groups."""

        keys: set[frozenset[str]] = set()
        for group in values:
            _validate_id_list(group, "Gold MEG source IDs")
            key = frozenset(group)
            if key in keys:
                raise ValueError("Gold MEGs must be distinct")
            keys.add(key)
        return values

    @model_validator(mode="after")
    def case_ids_must_be_unique(self) -> Self:
        """Reject ambiguous requirement and group identities."""

        requirement_ids = [
            item.requirement_id for item in self.answer_requirements
        ]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("Gold requirement IDs must be unique")
        group_keys = [
            frozenset(item.source_ids) for item in self.group_assessments
        ]
        if len(group_keys) != len(set(group_keys)):
            raise ValueError("Gold group assessments must be unique")
        full_keys = {
            frozenset(item.source_ids)
            for item in self.group_assessments
            if item.support is GroupSupport.FULL
        }
        gold_keys = {frozenset(group) for group in self.gold_megs}
        if not full_keys:
            raise ValueError("Gold MEG cases require a FULL group label")
        minimum = min(len(group) for group in full_keys)
        expected_megs = {
            group for group in full_keys if len(group) == minimum
        }
        if gold_keys != expected_megs:
            raise ValueError(
                "Gold MEGs must exactly match minimum FULL groups"
            )
        return self


class ResearcherGoldDataset(BaseModel):
    """Versioned paper-relevance and MEG mechanism annotations."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["5"]
    dataset_id: str
    version: str
    annotation_status: Literal["draft", "reviewed", "frozen"]
    subquestion_origin: Literal["manual", "planner"]
    evaluation_scope: Literal["researcher_meg_mechanism_only"]
    open_adjudications: list[str]
    relevance_grades: dict[str, int]
    cases: list[GoldResearchCase] = Field(min_length=1)
    items: list[GoldAssessment] = Field(min_length=1)

    @field_validator("dataset_id", "version")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        """Require stable dataset identity fields."""

        if not value.strip():
            raise ValueError("dataset identity must not be blank")
        return value

    @field_validator("open_adjudications")
    @classmethod
    def adjudications_must_not_be_blank(
        cls,
        values: list[str],
    ) -> list[str]:
        """Reject empty entries in the human-review queue."""

        if any(not value.strip() for value in values):
            raise ValueError("open adjudications must not be blank")
        return values

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Validate grade mapping and all case-to-item references."""

        if (
            self.annotation_status != "draft"
            and self.open_adjudications
        ):
            raise ValueError(
                "reviewed or frozen data cannot have open adjudications"
            )
        if self.relevance_grades != DEFAULT_RELEVANCE_GRADES:
            raise ValueError("relevance_grades use an unsupported mapping")
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Gold item IDs must be unique")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Gold case IDs must be unique")

        items_by_case: dict[str, list[GoldAssessment]] = {}
        for item in self.items:
            items_by_case.setdefault(item.case_id, []).append(item)
        if set(items_by_case) != set(case_ids):
            raise ValueError("Gold items must reference exact dataset cases")

        for case in self.cases:
            case_items = items_by_case[case.case_id]
            if set(case.candidate_item_ids) != {
                item.item_id for item in case_items
            }:
                raise ValueError(
                    "candidate item IDs must exactly match case items"
                )
            source_ids = {item.source_id for item in case_items}
            referenced_groups = [
                label.source_ids for label in case.group_assessments
            ] + case.gold_megs
            if any(
                not set(group).issubset(source_ids)
                for group in referenced_groups
            ):
                raise ValueError("case groups used an unknown source ID")
        return self


class PredictedAssessment(FactorJudgment):
    """One system paper prediction matched by item ID."""

    item_id: str

    @field_validator("item_id")
    @classmethod
    def item_id_must_not_be_blank(cls, value: str) -> str:
        """Require a usable Gold lookup key."""

        if not value.strip():
            raise ValueError("prediction item_id must not be blank")
        return value


class PredictedMegCase(BaseModel):
    """Group labels and selected MEGs predicted for one case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    group_assessments: list[GroupLabel] = Field(min_length=1)
    predicted_megs: list[list[str]]

    @field_validator("case_id")
    @classmethod
    def case_id_must_not_be_blank(cls, value: str) -> str:
        """Require a stable Gold-case lookup key."""

        if not value.strip():
            raise ValueError("prediction case_id must not be blank")
        return value

    @field_validator("predicted_megs")
    @classmethod
    def predicted_megs_must_be_valid(
        cls,
        values: list[list[str]],
    ) -> list[list[str]]:
        """Reject duplicate and malformed predicted groups."""

        keys: set[frozenset[str]] = set()
        for group in values:
            _validate_id_list(group, "predicted MEG source IDs")
            key = frozenset(group)
            if key in keys:
                raise ValueError("predicted MEGs must be distinct")
            keys.add(key)
        return values


class ResearcherPredictionSet(BaseModel):
    """Predictions for exactly one versioned Researcher dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    system_id: str
    predictions: list[PredictedAssessment] = Field(min_length=1)
    meg_predictions: list[PredictedMegCase] = Field(min_length=1)

    @field_validator("dataset_id", "dataset_version", "system_id")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        """Require attributable prediction identity."""

        if not value.strip():
            raise ValueError("prediction identity must not be blank")
        return value

    @model_validator(mode="after")
    def prediction_ids_must_be_unique(self) -> Self:
        """Prevent prediction records from overwriting each other."""

        item_ids = [item.item_id for item in self.predictions]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("prediction item IDs must be unique")
        case_ids = [item.case_id for item in self.meg_predictions]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("prediction case IDs must be unique")
        return self


def evaluate_assessments(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> dict[str, object]:
    """Evaluate paper factors, group support, and minimum-group selection."""

    _validate_prediction_coverage(dataset, prediction_set)
    paper_metrics = _evaluate_papers(dataset, prediction_set)
    group_metrics = _evaluate_groups(dataset, prediction_set)
    return {
        "dataset": {
            "schema_version": dataset.schema_version,
            "dataset_id": dataset.dataset_id,
            "version": dataset.version,
            "annotation_status": dataset.annotation_status,
            "subquestion_origin": dataset.subquestion_origin,
            "evaluation_scope": dataset.evaluation_scope,
            "open_adjudications": dataset.open_adjudications,
            "cases": len(dataset.cases),
            "items": len(dataset.items),
        },
        "system_id": prediction_set.system_id,
        **paper_metrics,
        **group_metrics,
    }


def _evaluate_papers(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> dict[str, object]:
    """Calculate factor accuracy and four-class relevance metrics."""

    predictions_by_id = {
        item.item_id: item for item in prediction_set.predictions
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
    per_class = _per_class_metrics(
        confusion,
        [level.value for level in SCORED_RELEVANCE_LEVELS],
    )
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
        "factor_accuracy": {
            "overall": _ratio(
                sum(factor_correct.values()),
                total * len(FACTOR_FIELDS),
            ),
            "by_factor": per_factor,
        },
        "relevance": {
            "accuracy": _ratio(
                sum(
                    confusion[level.value][level.value]
                    for level in SCORED_RELEVANCE_LEVELS
                ),
                total,
            ),
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


def _evaluate_groups(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> dict[str, object]:
    """Calculate group-label and minimum-source-set metrics."""

    predictions_by_case = {
        item.case_id: item for item in prediction_set.meg_predictions
    }
    confusion = {
        gold.value: {predicted.value: 0 for predicted in GROUP_SUPPORT_LEVELS}
        for gold in GROUP_SUPPORT_LEVELS
    }
    complete_cases = 0
    cardinality_errors: list[int] = []
    redundant_sources = 0
    predicted_sources = 0

    for case in dataset.cases:
        prediction = predictions_by_case[case.case_id]
        predicted_labels = {
            frozenset(item.source_ids): item.support
            for item in prediction.group_assessments
        }
        for gold in case.group_assessments:
            predicted = predicted_labels[frozenset(gold.source_ids)]
            confusion[gold.support.value][predicted.value] += 1

        gold_keys = {frozenset(group) for group in case.gold_megs}
        predicted_keys = {
            frozenset(group) for group in prediction.predicted_megs
        }
        if gold_keys & predicted_keys:
            complete_cases += 1

        gold_size = min(len(group) for group in case.gold_megs)
        if prediction.predicted_megs:
            predicted_size = min(
                len(group) for group in prediction.predicted_megs
            )
            cardinality_errors.append(predicted_size - gold_size)
        for predicted_group in predicted_keys:
            predicted_sources += len(predicted_group)
            contained = [
                gold_group
                for gold_group in gold_keys
                if gold_group.issubset(predicted_group)
            ]
            if contained:
                smallest = min(len(group) for group in contained)
                redundant_sources += len(predicted_group) - smallest

    per_class = _per_class_metrics(
        confusion,
        [level.value for level in GROUP_SUPPORT_LEVELS],
    )
    return {
        "group_support": {
            "macro_f1": _mean(
                per_class[level.value]["f1"]
                for level in GROUP_SUPPORT_LEVELS
            ),
            "per_class": per_class,
            "confusion_matrix": confusion,
        },
        "meg": {
            "complete_case_rate": _ratio(
                complete_cases,
                len(dataset.cases),
            ),
            "mean_cardinality_error": _mean(cardinality_errors),
            "redundant_source_rate": _ratio(
                redundant_sources,
                predicted_sources,
            ),
        },
    }


def _validate_prediction_coverage(
    dataset: ResearcherGoldDataset,
    prediction_set: ResearcherPredictionSet,
) -> None:
    """Require predictions to cover exactly one dataset version."""

    if prediction_set.dataset_id != dataset.dataset_id:
        raise ValueError("prediction dataset_id does not match Gold dataset")
    if prediction_set.dataset_version != dataset.version:
        raise ValueError(
            "prediction dataset_version does not match Gold dataset"
        )
    _require_exact_ids(
        gold={item.item_id for item in dataset.items},
        predicted={item.item_id for item in prediction_set.predictions},
        label="prediction item",
    )
    _require_exact_ids(
        gold={case.case_id for case in dataset.cases},
        predicted={item.case_id for item in prediction_set.meg_predictions},
        label="prediction case",
    )

    prediction_by_case = {
        item.case_id: item for item in prediction_set.meg_predictions
    }
    for case in dataset.cases:
        prediction = prediction_by_case[case.case_id]
        _require_exact_ids(
            gold={
                frozenset(item.source_ids)
                for item in case.group_assessments
            },
            predicted={
                frozenset(item.source_ids)
                for item in prediction.group_assessments
            },
            label=f"{case.case_id} group",
        )
        known_sources = {
            item.source_id
            for item in dataset.items
            if item.case_id == case.case_id
        }
        if any(
            not set(group).issubset(known_sources)
            for group in prediction.predicted_megs
        ):
            raise ValueError("predicted MEG used an unknown source ID")


def _require_exact_ids(
    *,
    gold: set,
    predicted: set,
    label: str,
) -> None:
    """Raise one attributable error for missing or unexpected identifiers."""

    missing = sorted(gold - predicted, key=str)
    unexpected = sorted(predicted - gold, key=str)
    if missing or unexpected:
        raise ValueError(
            f"{label} IDs must exactly match Gold; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _per_class_metrics(
    confusion: Mapping[str, Mapping[str, int]],
    labels: list[str],
) -> dict[str, dict[str, float]]:
    """Calculate one-vs-rest precision, recall, and F1."""

    metrics: dict[str, dict[str, float]] = {}
    for label in labels:
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


def _validate_id_list(values: list[str], label: str) -> list[str]:
    """Require nonblank, unique identifier strings."""

    if any(not value.strip() for value in values):
        raise ValueError(f"{label} must not be blank")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    return values


def _join_wrapped_text(value: object) -> object:
    """Join JSON text arrays without treating arbitrary lists as prose."""

    if not isinstance(value, list):
        return value
    if not value or not all(isinstance(part, str) for part in value):
        raise ValueError("wrapped Gold text must contain string segments")
    return " ".join(part.strip() for part in value)


def _ratio(numerator: int, denominator: int) -> float:
    """Return a stable six-decimal ratio for JSON reports."""

    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: Iterable[float | int]) -> float:
    """Average a finite metric sequence without a numeric dependency."""

    materialized = list(values)
    return (
        round(sum(materialized) / len(materialized), 6)
        if materialized
        else 0.0
    )
