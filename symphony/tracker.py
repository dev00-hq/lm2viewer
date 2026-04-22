from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .errors import TrackerError
from .models import BlockerRef, Issue, ServiceConfig


CANDIDATE_QUERY = """
query SymphonyCandidateIssues($projectSlug: String!, $states: [String!], $after: String) {
  issues(
    first: 50
    after: $after
    filter: { project: { slugId: { eq: $projectSlug } }, state: { name: { in: $states } } }
    orderBy: createdAt
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      branchName
      url
      createdAt
      updatedAt
      state { name }
      labels { nodes { name } }
      inverseRelations { nodes { type relatedIssue { id identifier state { name } } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

STATE_QUERY = """
query SymphonyIssueStates($ids: [ID!]!) {
  issues(filter: { id: { in: $ids } }) {
    nodes {
      id
      identifier
      title
      description
      priority
      branchName
      url
      createdAt
      updatedAt
      state { name }
      labels { nodes { name } }
      inverseRelations { nodes { type relatedIssue { id identifier state { name } } } }
    }
  }
}
"""

TERMINAL_QUERY = """
query SymphonyTerminalIssues($projectSlug: String!, $states: [String!], $after: String) {
  issues(
    first: 50
    after: $after
    filter: { project: { slugId: { eq: $projectSlug } }, state: { name: { in: $states } } }
    orderBy: createdAt
  ) {
    nodes { id identifier state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class LinearClient:
    def __init__(self, config: ServiceConfig) -> None:
        self.endpoint = config.tracker_endpoint
        self.api_key = config.tracker_api_key
        self.project_slug = config.tracker_project_slug
        self.active_states = list(config.active_states)
        self.terminal_states = list(config.terminal_states)

    def fetch_candidate_issues(self) -> list[Issue]:
        return self._fetch_paged(CANDIDATE_QUERY, self.active_states)

    def fetch_terminal_issues(self) -> list[Issue]:
        return self._fetch_paged(TERMINAL_QUERY, self.terminal_states)

    def fetch_issue_states_by_ids(self, ids: list[str]) -> list[Issue]:
        if not ids:
            return []
        data = self.graphql(STATE_QUERY, {"ids": ids})
        nodes = data.get("data", {}).get("issues", {}).get("nodes")
        if not isinstance(nodes, list):
            raise TrackerError("linear_malformed_response: missing issues.nodes")
        return [_normalize_issue(node) for node in nodes if isinstance(node, dict)]

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "content-type": "application/json",
                "authorization": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raise TrackerError(f"linear_api_status: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise TrackerError(f"linear_transport_error: {exc}") from exc
        if status != 200:
            raise TrackerError(f"linear_api_status: {status}")
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TrackerError("linear_malformed_response: invalid json") from exc
        if data.get("errors"):
            raise TrackerError(f"linear_graphql_errors: {data['errors']}")
        return data

    def _fetch_paged(self, query: str, states: list[str]) -> list[Issue]:
        if not states:
            return []
        after: str | None = None
        issues: list[Issue] = []
        while True:
            data = self.graphql(
                query,
                {"projectSlug": self.project_slug, "states": states, "after": after},
            )
            issue_data = data.get("data", {}).get("issues", {})
            nodes = issue_data.get("nodes")
            if not isinstance(nodes, list):
                raise TrackerError("linear_malformed_response: missing issues.nodes")
            issues.extend(_normalize_issue(node) for node in nodes if isinstance(node, dict))
            page_info = issue_data.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                return issues
            after = page_info.get("endCursor")


def _normalize_issue(node: dict[str, Any]) -> Issue:
    state = (node.get("state") or {}).get("name") if isinstance(node.get("state"), dict) else node.get("state")
    labels = []
    raw_labels = node.get("labels", {}).get("nodes", []) if isinstance(node.get("labels"), dict) else node.get("labels", [])
    if isinstance(raw_labels, list):
        labels = [str(item.get("name", item)).lower() if isinstance(item, dict) else str(item).lower() for item in raw_labels]

    blockers: list[BlockerRef] = []
    relations = node.get("inverseRelations", {}).get("nodes", []) if isinstance(node.get("inverseRelations"), dict) else []
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict) or relation.get("type") != "blocks":
                continue
            related = relation.get("relatedIssue")
            if isinstance(related, dict):
                blockers.append(
                    BlockerRef(
                        id=_optional_str(related.get("id")),
                        identifier=_optional_str(related.get("identifier")),
                        state=_optional_str((related.get("state") or {}).get("name") if isinstance(related.get("state"), dict) else related.get("state")),
                    )
                )

    return Issue(
        id=str(node.get("id", "")),
        identifier=str(node.get("identifier", "")),
        title=str(node.get("title", "")),
        description=_optional_str(node.get("description")),
        priority=_optional_int(node.get("priority")),
        state=str(state or ""),
        branch_name=_optional_str(node.get("branchName") or node.get("branch_name")),
        url=_optional_str(node.get("url")),
        labels=tuple(labels),
        blocked_by=tuple(blockers),
        created_at=_optional_str(node.get("createdAt") or node.get("created_at")),
        updated_at=_optional_str(node.get("updatedAt") or node.get("updated_at")),
    )


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

