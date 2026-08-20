"""Bounded concurrent supervisor for independent blind review providers."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from copy import deepcopy
from typing import Any, Mapping

from .review_models import ArchitectureReviewIncomplete, ReviewProvider
from .review_packet import build_review_requests, freeze_review_set
from .review_validation import require_contract_integrity


class ArchitectureReviewSupervisor:
    def __init__(
        self,
        review_contract: dict[str, Any],
        architecture_contract: dict[str, Any],
    ) -> None:
        require_contract_integrity(review_contract, "review contract")
        require_contract_integrity(architecture_contract, "architecture contract")
        self._review_contract = deepcopy(review_contract)
        self._architecture_contract = deepcopy(architecture_contract)

    def run_blind_reviews(
        self,
        packet: dict[str, Any],
        providers: Mapping[str, ReviewProvider],
    ) -> dict[str, Any]:
        require_contract_integrity(self._review_contract, "review contract")
        require_contract_integrity(
            self._architecture_contract, "architecture contract"
        )
        lanes = self._review_contract["required_lanes"]
        if set(providers) != set(lanes):
            raise ArchitectureReviewIncomplete(
                "one injected provider per required lane is required"
            )
        requests = build_review_requests(packet, self._review_contract)
        workers = min(self._review_contract["max_parallelism"], len(lanes))
        timeout = float(
            self._review_contract.get("provider_timeout_seconds", 3600.0)
        )
        executor = ThreadPoolExecutor(max_workers=workers)
        futures: dict[Future[dict[str, Any]], str] = {}
        try:
            futures = {
                executor.submit(
                    providers[request["lane_id"]], deepcopy(request)
                ): request["lane_id"]
                for request in requests
            }
            done, not_done = wait(tuple(futures), timeout=timeout)
            if not_done:
                timed_out = sorted(futures[future] for future in not_done)
                for future in not_done:
                    future.cancel()
                raise ArchitectureReviewIncomplete(
                    "required blind review providers timed out: "
                    + ",".join(timed_out)
                )
            reports: list[dict[str, Any]] = []
            failures: list[str] = []
            for future in done:
                lane = futures[future]
                try:
                    report = future.result()
                except Exception:
                    failures.append(lane)
                    continue
                if not isinstance(report, dict):
                    failures.append(lane)
                    continue
                reports.append(report)
            if failures:
                raise ArchitectureReviewIncomplete(
                    "required blind review providers failed: "
                    + ",".join(sorted(failures))
                )
            return freeze_review_set(
                reports,
                packet,
                self._review_contract,
                self._architecture_contract,
            )
        finally:
            # A Python thread cannot be force-killed safely. Provider adapters must
            # also enforce their own I/O timeout; this prevents the supervisor from
            # waiting indefinitely and cancels work that has not started.
            executor.shutdown(wait=False, cancel_futures=True)
