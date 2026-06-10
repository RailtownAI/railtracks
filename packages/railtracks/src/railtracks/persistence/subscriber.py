"""Pubsub subscriber that incrementally persists run state to SQLite.

Rather than decoding individual message payloads, the subscriber treats
the in-memory forests (`ExecutionInfo`) as the source of truth: every
event triggers a diff-sync that writes only entities whose stamp moved
since the last sync. This sidesteps subscriber-ordering concerns —
`RTState.handle` is subscribed before us and mutates the forests
synchronously, so by the time we run, the heap already reflects the
event — and it makes the subscriber idempotent: a missed event is
healed by the next one (or by the final `sync()` at session exit).

Exceptions raised here are swallowed by the Publisher (logged at debug),
so a persistence failure can never take down a run.
"""

from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional

from railtracks.pubsub.messages import FatalFailure, RequestCompletionMessage
from railtracks.state.info import ExecutionInfo
from railtracks.state.request import RequestTemplate

from .repository import SessionRepository


class PersistenceSubscriber:
    def __init__(
        self,
        repo: SessionRepository,
        *,
        session_id: str,
        info: ExecutionInfo,
    ):
        self._repo = repo
        self._session_id = session_id
        self._info = info

        self._persisted_node_steps: Dict[str, int] = {}
        self._persisted_request_steps: Dict[str, int] = {}
        self._persisted_llm_counts: Dict[str, int] = {}
        self._persisted_stamp_count = 0
        self._known_runs: set[str] = set()
        self._closed_runs: set[str] = set()

    async def handle(self, message: RequestCompletionMessage) -> None:
        if isinstance(message, FatalFailure):
            self._repo.end_session(
                self._session_id, end_time=time.time(), status="Failed"
            )
        self.sync()

    def sync(self) -> None:
        """Persist everything in the forests that changed since the last sync."""
        requests = dict(self._info.request_forest.heap())
        nodes = dict(self._info.node_forest.heap())
        run_of_node = self._assign_runs(requests.values())

        self._sync_runs(requests.values(), nodes)
        self._sync_nodes(nodes, run_of_node)
        self._sync_requests(requests.values(), run_of_node)
        self._sync_stamps()

    # ------------------------------------------------------------------

    @staticmethod
    def _assign_runs(requests: Iterable[RequestTemplate]) -> Dict[str, str]:
        """Map node_uuid -> run_id. A run is rooted at an insertion request
        (source_id is None) and its id is that request's identifier; child
        nodes inherit the run of their parent."""
        rts: List[RequestTemplate] = list(requests)
        assignment: Dict[str, str] = {}
        for rt in rts:
            if rt.source_id is None:
                assignment[rt.sink_id] = rt.identifier

        changed = True
        while changed:
            changed = False
            for rt in rts:
                if rt.source_id in assignment and rt.sink_id not in assignment:
                    assignment[rt.sink_id] = assignment[rt.source_id]
                    changed = True
        return assignment

    def _sync_runs(self, requests: Iterable[RequestTemplate], nodes: dict) -> None:
        for rt in requests:
            if rt.source_id is not None:
                continue
            run_id = rt.identifier
            if run_id not in self._known_runs:
                sink = nodes.get(rt.sink_id)
                name = sink._node.name() if sink is not None else None
                self._repo.start_run(
                    run_id=run_id,
                    session_id=self._session_id,
                    name=name,
                    start_time=rt.get_all_parents()[-1].stamp.time,
                )
                self._known_runs.add(run_id)
            if rt.status in ("Completed", "Failed") and run_id not in self._closed_runs:
                self._repo.end_run(run_id, end_time=rt.stamp.time, status=rt.status)
                self._closed_runs.add(run_id)

    def _sync_nodes(self, nodes: dict, run_of_node: Dict[str, str]) -> None:
        for ln in nodes.values():
            run_id = run_of_node.get(ln.identifier)
            if run_id is None:
                # not connected to a run yet; the next sync will pick it up
                continue
            if self._persisted_node_steps.get(ln.identifier) != ln.stamp.step:
                self._repo.persist_linked_node(ln, run_id=run_id)
                self._persisted_node_steps[ln.identifier] = ln.stamp.step
            self._sync_llm_calls(ln)

    def _sync_llm_calls(self, ln) -> None:
        details = getattr(ln._node, "details", None) or {}
        llm_details = list(details.get("llm_details", []))
        done = self._persisted_llm_counts.get(ln.identifier, 0)
        for index in range(done, len(llm_details)):
            self._repo.record_llm_call(
                llm_details[index],
                node_uuid=ln.identifier,
                session_id=self._session_id,
                call_index=index,
            )
        if llm_details:
            self._persisted_llm_counts[ln.identifier] = len(llm_details)

    def _sync_requests(
        self, requests: Iterable[RequestTemplate], run_of_node: Dict[str, str]
    ) -> None:
        for rt in requests:
            run_id = run_of_node.get(rt.sink_id)
            if run_id is None:
                continue
            if self._persisted_request_steps.get(rt.identifier) != rt.stamp.step:
                self._repo.persist_request(rt, run_id=run_id)
                self._persisted_request_steps[rt.identifier] = rt.stamp.step

    def _sync_stamps(self) -> None:
        all_stamps = list(self._info.stamper.all_stamps)
        for stamp in all_stamps[self._persisted_stamp_count :]:
            self._repo.record_stamp(self._session_id, stamp)
        self._persisted_stamp_count = len(all_stamps)
