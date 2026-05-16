from __future__ import annotations


class SymphonyError(RuntimeError):
    code = "symphony_error"


class WorkflowError(SymphonyError):
    pass


class MissingWorkflowFile(WorkflowError):
    code = "missing_workflow_file"


class WorkflowParseError(WorkflowError):
    code = "workflow_parse_error"


class WorkflowFrontMatterNotMap(WorkflowError):
    code = "workflow_front_matter_not_a_map"


class TemplateRenderError(WorkflowError):
    code = "template_render_error"


class ConfigValidationError(SymphonyError):
    code = "config_validation_error"

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


class TrackerError(SymphonyError):
    code = "tracker_error"


class WorkspaceError(SymphonyError):
    code = "workspace_error"


class AgentError(SymphonyError):
    code = "agent_error"

