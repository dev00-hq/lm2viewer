import unittest
from pathlib import Path

from symphony.models import ServiceConfig, HooksConfig
from symphony.tracker import CANDIDATE_QUERY, LinearClient, _normalize_issue


def config() -> ServiceConfig:
    return ServiceConfig(
        workflow_path=Path("WORKFLOW.md"),
        tracker_kind="linear",
        tracker_endpoint="https://example.invalid/graphql",
        tracker_api_key="token",
        tracker_project_slug="CODEX",
        active_states=("Todo",),
        terminal_states=("Done",),
        polling_interval_ms=1000,
        workspace_root=Path(".work"),
        hooks=HooksConfig(),
        max_concurrent_agents=1,
        max_concurrent_agents_by_state={},
        max_retry_backoff_ms=10000,
        max_turns=1,
        codex_command="codex app-server",
        codex_approval_policy=None,
        codex_thread_sandbox=None,
        codex_turn_sandbox_policy=None,
        codex_turn_timeout_ms=1000,
        codex_read_timeout_ms=1000,
        codex_stall_timeout_ms=0,
    )


class FakeLinearClient(LinearClient):
    def __init__(self) -> None:
        super().__init__(config())
        self.calls = []

    def graphql(self, query, variables=None):  # type: ignore[override]
        self.calls.append((query, variables))
        return {
            "data": {
                "issues": {
                    "nodes": [
                        {
                            "id": "1",
                            "identifier": "ABC-1",
                            "title": "Work",
                            "state": {"name": "Todo"},
                            "labels": {"nodes": [{"name": "Bug"}]},
                            "inverseRelations": {
                                "nodes": [
                                    {
                                        "type": "blocks",
                                        "relatedIssue": {
                                            "id": "2",
                                            "identifier": "ABC-0",
                                            "state": {"name": "Done"},
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }


class SymphonyTrackerTests(unittest.TestCase):
    def test_candidate_query_uses_project_slug_id(self) -> None:
        self.assertIn("slugId", CANDIDATE_QUERY)

    def test_fetch_candidate_issues_normalizes_labels_and_blockers(self) -> None:
        client = FakeLinearClient()

        issues = client.fetch_candidate_issues()

        self.assertEqual(issues[0].identifier, "ABC-1")
        self.assertEqual(issues[0].labels, ("bug",))
        self.assertEqual(issues[0].blocked_by[0].state, "Done")
        self.assertEqual(client.calls[0][1]["projectSlug"], "CODEX")

    def test_empty_state_refresh_skips_api_call(self) -> None:
        client = FakeLinearClient()
        self.assertEqual(client.fetch_issue_states_by_ids([]), [])
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()

