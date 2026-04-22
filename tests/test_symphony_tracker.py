import unittest
from pathlib import Path

from symphony.models import ServiceConfig, HooksConfig
from symphony.tracker import (
    CANDIDATE_QUERY,
    ISSUE_UPDATE_DESCRIPTION_MUTATION,
    ISSUE_UPDATE_STATE_MUTATION,
    PROJECT_ISSUES_QUERY,
    LinearClient,
    _normalize_issue,
)


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
        if "workflowStates" in query:
            return {
                "data": {
                    "workflowStates": {
                        "nodes": [{"id": "done-state", "name": "Done"}],
                    }
                }
            }
        if "issueUpdate" in query:
            issue = {
                "id": variables["id"],
                "identifier": "ABC-1",
                "title": "Work",
                "state": {"name": "Done"},
                "team": {"id": "team-1"},
            }
            if "description" in variables:
                issue["description"] = variables["description"]
            return {
                "data": {
                    "issueUpdate": {
                        "success": True,
                        "issue": issue,
                    }
                }
            }
        return {
            "data": {
                "issues": {
                    "nodes": [
                        {
                            "id": "1",
                            "identifier": "ABC-1",
                            "title": "Work",
                            "state": {"name": "Todo"},
                            "team": {"id": "team-1"},
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

    def test_issue_update_mutation_sets_state_id(self) -> None:
        self.assertIn("issueUpdate", ISSUE_UPDATE_STATE_MUTATION)
        self.assertIn("stateId", ISSUE_UPDATE_STATE_MUTATION)

    def test_project_issues_query_uses_project_slug_without_state_filter(self) -> None:
        self.assertIn("slugId", PROJECT_ISSUES_QUERY)
        self.assertNotIn("$states", PROJECT_ISSUES_QUERY)

    def test_issue_update_description_mutation_sets_description(self) -> None:
        self.assertIn("issueUpdate", ISSUE_UPDATE_DESCRIPTION_MUTATION)
        self.assertIn("description", ISSUE_UPDATE_DESCRIPTION_MUTATION)

    def test_fetch_candidate_issues_normalizes_labels_and_blockers(self) -> None:
        client = FakeLinearClient()

        issues = client.fetch_candidate_issues()

        self.assertEqual(issues[0].identifier, "ABC-1")
        self.assertEqual(issues[0].labels, ("bug",))
        self.assertEqual(issues[0].team_id, "team-1")
        self.assertEqual(issues[0].blocked_by[0].state, "Done")
        self.assertEqual(client.calls[0][1]["projectSlug"], "CODEX")

    def test_complete_issue_resolves_done_state_and_updates_issue(self) -> None:
        client = FakeLinearClient()
        issue = _normalize_issue(
            {
                "id": "1",
                "identifier": "ABC-1",
                "title": "Work",
                "state": {"name": "Todo"},
                "team": {"id": "team-1"},
            }
        )

        updated = client.complete_issue(issue)

        self.assertEqual(updated.state, "Done")
        self.assertEqual(client.calls[0][1], {"teamId": "team-1", "name": "Done"})
        self.assertEqual(client.calls[1][1], {"id": "1", "stateId": "done-state"})

    def test_update_issue_description_calls_linear_mutation(self) -> None:
        client = FakeLinearClient()

        updated = client.update_issue_description("1", "Synced docs")

        self.assertEqual(updated.description, "Synced docs")
        self.assertEqual(client.calls[0][1], {"id": "1", "description": "Synced docs"})

    def test_empty_state_refresh_skips_api_call(self) -> None:
        client = FakeLinearClient()
        self.assertEqual(client.fetch_issue_states_by_ids([]), [])
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
