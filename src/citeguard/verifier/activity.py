"""Temporal Activity for deterministic report verification."""

from temporalio import activity
from temporalio.exceptions import ApplicationError

from citeguard.domain.report import VerificationResult
from citeguard.verifier.contracts import VerifierInput
from citeguard.verifier.verification import verify_report


@activity.defn(name="verify_report")
async def verify_written_report(
    verifier_input: VerifierInput,
) -> VerificationResult:
    """Apply side-effect-free Verifier hard gates.

    Args:
        verifier_input: Exact evidence context and candidate Writer report.

    Returns:
        Approval or attributable content failures.

    Raises:
        ApplicationError: If report structure cannot map to an input
            subquestion and therefore has no valid content-retry target.

    Retry behavior:
        Content failures are normal return values. Unmappable structure is a
        deterministic non-retryable Activity failure.
    """

    try:
        return verify_report(verifier_input)
    except (TypeError, ValueError) as exc:
        raise ApplicationError(
            str(exc),
            type="InvalidVerifierReport",
            non_retryable=True,
        ) from exc
