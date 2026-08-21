from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GuardAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GUARD_ACTION_UNSPECIFIED: _ClassVar[GuardAction]
    GUARD_ACTION_ALLOW: _ClassVar[GuardAction]
    GUARD_ACTION_DENY: _ClassVar[GuardAction]

class SettingType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SETTING_TYPE_UNSPECIFIED: _ClassVar[SettingType]
    SETTING_TYPE_STRING: _ClassVar[SettingType]
    SETTING_TYPE_BOOL: _ClassVar[SettingType]
    SETTING_TYPE_INT: _ClassVar[SettingType]
    SETTING_TYPE_ENUM: _ClassVar[SettingType]
    SETTING_TYPE_DURATION: _ClassVar[SettingType]
GUARD_ACTION_UNSPECIFIED: GuardAction
GUARD_ACTION_ALLOW: GuardAction
GUARD_ACTION_DENY: GuardAction
SETTING_TYPE_UNSPECIFIED: SettingType
SETTING_TYPE_STRING: SettingType
SETTING_TYPE_BOOL: SettingType
SETTING_TYPE_INT: SettingType
SETTING_TYPE_ENUM: SettingType
SETTING_TYPE_DURATION: SettingType

class GuardContext(_message.Message):
    __slots__ = ("agent_id", "agent_class", "session_id", "cwd", "matched_profile")
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_CLASS_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CWD_FIELD_NUMBER: _ClassVar[int]
    MATCHED_PROFILE_FIELD_NUMBER: _ClassVar[int]
    agent_id: str
    agent_class: str
    session_id: str
    cwd: str
    matched_profile: str
    def __init__(self, agent_id: _Optional[str] = ..., agent_class: _Optional[str] = ..., session_id: _Optional[str] = ..., cwd: _Optional[str] = ..., matched_profile: _Optional[str] = ...) -> None: ...

class VerdictInfo(_message.Message):
    __slots__ = ("reason", "labels", "rule_id", "ruleset_id", "confidence")
    class LabelsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    REASON_FIELD_NUMBER: _ClassVar[int]
    LABELS_FIELD_NUMBER: _ClassVar[int]
    RULE_ID_FIELD_NUMBER: _ClassVar[int]
    RULESET_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    reason: str
    labels: _containers.ScalarMap[str, str]
    rule_id: str
    ruleset_id: str
    confidence: float
    def __init__(self, reason: _Optional[str] = ..., labels: _Optional[_Mapping[str, str]] = ..., rule_id: _Optional[str] = ..., ruleset_id: _Optional[str] = ..., confidence: _Optional[float] = ...) -> None: ...

class CheckPromptRequest(_message.Message):
    __slots__ = ("ctx", "prompt")
    CTX_FIELD_NUMBER: _ClassVar[int]
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    ctx: GuardContext
    prompt: str
    def __init__(self, ctx: _Optional[_Union[GuardContext, _Mapping]] = ..., prompt: _Optional[str] = ...) -> None: ...

class PromptVerdict(_message.Message):
    __slots__ = ("action", "info", "additional_context")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    action: GuardAction
    info: VerdictInfo
    additional_context: str
    def __init__(self, action: _Optional[_Union[GuardAction, str]] = ..., info: _Optional[_Union[VerdictInfo, _Mapping]] = ..., additional_context: _Optional[str] = ...) -> None: ...

class CheckTranscriptRequest(_message.Message):
    __slots__ = ("ctx", "transcript_path", "transcript_tail", "transcript_tail_truncated", "turn_index")
    CTX_FIELD_NUMBER: _ClassVar[int]
    TRANSCRIPT_PATH_FIELD_NUMBER: _ClassVar[int]
    TRANSCRIPT_TAIL_FIELD_NUMBER: _ClassVar[int]
    TRANSCRIPT_TAIL_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    TURN_INDEX_FIELD_NUMBER: _ClassVar[int]
    ctx: GuardContext
    transcript_path: str
    transcript_tail: bytes
    transcript_tail_truncated: bool
    turn_index: int
    def __init__(self, ctx: _Optional[_Union[GuardContext, _Mapping]] = ..., transcript_path: _Optional[str] = ..., transcript_tail: _Optional[bytes] = ..., transcript_tail_truncated: _Optional[bool] = ..., turn_index: _Optional[int] = ...) -> None: ...

class TranscriptVerdict(_message.Message):
    __slots__ = ("action", "info")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    action: GuardAction
    info: VerdictInfo
    def __init__(self, action: _Optional[_Union[GuardAction, str]] = ..., info: _Optional[_Union[VerdictInfo, _Mapping]] = ...) -> None: ...

class CheckToolInputRequest(_message.Message):
    __slots__ = ("ctx", "tool_name", "tool_input_json")
    CTX_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    TOOL_INPUT_JSON_FIELD_NUMBER: _ClassVar[int]
    ctx: GuardContext
    tool_name: str
    tool_input_json: str
    def __init__(self, ctx: _Optional[_Union[GuardContext, _Mapping]] = ..., tool_name: _Optional[str] = ..., tool_input_json: _Optional[str] = ...) -> None: ...

class CheckToolOutputRequest(_message.Message):
    __slots__ = ("ctx", "tool_name", "tool_output", "tool_output_truncated")
    CTX_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    TOOL_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    TOOL_OUTPUT_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    ctx: GuardContext
    tool_name: str
    tool_output: bytes
    tool_output_truncated: bool
    def __init__(self, ctx: _Optional[_Union[GuardContext, _Mapping]] = ..., tool_name: _Optional[str] = ..., tool_output: _Optional[bytes] = ..., tool_output_truncated: _Optional[bool] = ...) -> None: ...

class ToolInputVerdict(_message.Message):
    __slots__ = ("action", "info")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    action: GuardAction
    info: VerdictInfo
    def __init__(self, action: _Optional[_Union[GuardAction, str]] = ..., info: _Optional[_Union[VerdictInfo, _Mapping]] = ...) -> None: ...

class ToolOutputVerdict(_message.Message):
    __slots__ = ("action", "info")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    action: GuardAction
    info: VerdictInfo
    def __init__(self, action: _Optional[_Union[GuardAction, str]] = ..., info: _Optional[_Union[VerdictInfo, _Mapping]] = ...) -> None: ...

class ModuleCapabilities(_message.Message):
    __slots__ = ("check_prompt", "check_transcript", "check_tool_input", "check_tool_output", "max_tool_output_bytes", "max_transcript_bytes", "max_concurrent_checks", "admin")
    CHECK_PROMPT_FIELD_NUMBER: _ClassVar[int]
    CHECK_TRANSCRIPT_FIELD_NUMBER: _ClassVar[int]
    CHECK_TOOL_INPUT_FIELD_NUMBER: _ClassVar[int]
    CHECK_TOOL_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    MAX_TOOL_OUTPUT_BYTES_FIELD_NUMBER: _ClassVar[int]
    MAX_TRANSCRIPT_BYTES_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENT_CHECKS_FIELD_NUMBER: _ClassVar[int]
    ADMIN_FIELD_NUMBER: _ClassVar[int]
    check_prompt: bool
    check_transcript: bool
    check_tool_input: bool
    check_tool_output: bool
    max_tool_output_bytes: int
    max_transcript_bytes: int
    max_concurrent_checks: int
    admin: bool
    def __init__(self, check_prompt: _Optional[bool] = ..., check_transcript: _Optional[bool] = ..., check_tool_input: _Optional[bool] = ..., check_tool_output: _Optional[bool] = ..., max_tool_output_bytes: _Optional[int] = ..., max_transcript_bytes: _Optional[int] = ..., max_concurrent_checks: _Optional[int] = ..., admin: _Optional[bool] = ...) -> None: ...

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthResponse(_message.Message):
    __slots__ = ("ready", "module_name", "module_version", "ruleset_id", "ruleset_loaded_unix", "capabilities", "interface_version", "degraded_reason")
    READY_FIELD_NUMBER: _ClassVar[int]
    MODULE_NAME_FIELD_NUMBER: _ClassVar[int]
    MODULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    RULESET_ID_FIELD_NUMBER: _ClassVar[int]
    RULESET_LOADED_UNIX_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    INTERFACE_VERSION_FIELD_NUMBER: _ClassVar[int]
    DEGRADED_REASON_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    module_name: str
    module_version: str
    ruleset_id: str
    ruleset_loaded_unix: int
    capabilities: ModuleCapabilities
    interface_version: int
    degraded_reason: str
    def __init__(self, ready: _Optional[bool] = ..., module_name: _Optional[str] = ..., module_version: _Optional[str] = ..., ruleset_id: _Optional[str] = ..., ruleset_loaded_unix: _Optional[int] = ..., capabilities: _Optional[_Union[ModuleCapabilities, _Mapping]] = ..., interface_version: _Optional[int] = ..., degraded_reason: _Optional[str] = ...) -> None: ...

class ConfigSetting(_message.Message):
    __slots__ = ("key", "value", "type", "label", "description", "allowed_values", "restart_required", "secret")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_VALUES_FIELD_NUMBER: _ClassVar[int]
    RESTART_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    SECRET_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    type: SettingType
    label: str
    description: str
    allowed_values: _containers.RepeatedScalarFieldContainer[str]
    restart_required: bool
    secret: bool
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ..., type: _Optional[_Union[SettingType, str]] = ..., label: _Optional[str] = ..., description: _Optional[str] = ..., allowed_values: _Optional[_Iterable[str]] = ..., restart_required: _Optional[bool] = ..., secret: _Optional[bool] = ...) -> None: ...

class GetConfigRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetConfigResponse(_message.Message):
    __slots__ = ("settings",)
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    settings: _containers.RepeatedCompositeFieldContainer[ConfigSetting]
    def __init__(self, settings: _Optional[_Iterable[_Union[ConfigSetting, _Mapping]]] = ...) -> None: ...

class SetConfigRequest(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class SetConfigResponse(_message.Message):
    __slots__ = ("setting", "warning")
    SETTING_FIELD_NUMBER: _ClassVar[int]
    WARNING_FIELD_NUMBER: _ClassVar[int]
    setting: ConfigSetting
    warning: str
    def __init__(self, setting: _Optional[_Union[ConfigSetting, _Mapping]] = ..., warning: _Optional[str] = ...) -> None: ...
