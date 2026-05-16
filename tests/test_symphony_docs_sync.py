import tempfile
import unittest
from pathlib import Path

from symphony.docs_sync import (
    DocsLinearSync,
    parse_plan_milestones,
    render_linear_state,
    status_from_linear_state,
)
from symphony.models import Issue


PLAN = """# Plans

### M3: Model Evidence Exports

Linear: LM2-5

Status: planned.

Deliverable:

- Export evidence.

### M4: Contract Draft

Linear: LM2-6

Status: planned.

## Evidence Rules

This must not sync into M4.
"""


class FakeTracker:
    def __init__(self, issues):
        self.issues = issues
        self.updated = []

    def fetch_project_issues(self):
        return list(self.issues)

    def update_issue_description(self, issue_id, description):
        self.updated.append((issue_id, description))
        return self.issues[0]


class SymphonyDocsSyncTests(unittest.TestCase):
    def test_parse_plan_milestones_reads_linear_bound_sections(self) -> None:
        milestones = parse_plan_milestones(PLAN)

        self.assertEqual(len(milestones), 2)
        self.assertEqual(milestones[0].number, "M3")
        self.assertEqual(milestones[0].title, "Model Evidence Exports")
        self.assertEqual(milestones[0].linear_identifier, "LM2-5")
        self.assertNotIn("Evidence Rules", milestones[1].body)

    def test_render_linear_state_lists_current_issue_state(self) -> None:
        state = render_linear_state(
            [
                Issue(
                    id="1",
                    identifier="LM2-5",
                    title="Export evidence",
                    description=None,
                    priority=3,
                    state="In Progress",
                    branch_name=None,
                    url="https://linear.app/example/LM2-5",
                )
            ]
        )

        self.assertIn("[LM2-5](https://linear.app/example/LM2-5)", state)
        self.assertIn("| In Progress | 3 | Export evidence |", state)

    def test_status_from_linear_state_maps_execution_state_to_doc_status(self) -> None:
        self.assertEqual(status_from_linear_state("Done"), "implemented.")
        self.assertEqual(status_from_linear_state("In Progress"), "in progress.")
        self.assertEqual(status_from_linear_state("Todo"), "planned.")

    def test_sync_pulls_state_to_docs_and_pushes_docs_to_linear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "plans.md").write_text(PLAN, encoding="utf-8")
            issue = Issue(
                id="linear-id",
                identifier="LM2-5",
                title="Export evidence",
                description=None,
                priority=3,
                state="Done",
                branch_name=None,
                url=None,
            )
            second = Issue(
                id="linear-id-2",
                identifier="LM2-6",
                title="Contract",
                description=None,
                priority=3,
                state="Todo",
                branch_name=None,
                url=None,
            )
            tracker = FakeTracker([issue, second])

            DocsLinearSync(root, tracker).sync()

            plans = (docs / "plans.md").read_text(encoding="utf-8")
            state = (docs / "linear-state.md").read_text(encoding="utf-8")
            self.assertIn("Status: implemented.", plans)
            self.assertIn("| LM2-5 | Done | 3 | Export evidence |", state)
            self.assertEqual(tracker.updated[0][0], "linear-id")
            self.assertIn("Synced from `docs/plans.md` milestone M3", tracker.updated[0][1])
            self.assertNotIn("Evidence Rules", tracker.updated[1][1])


if __name__ == "__main__":
    unittest.main()
