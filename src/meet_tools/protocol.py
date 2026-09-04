"""Protocolo JSON v1.1 para la comunicación entre Clientes, Daemon y Extensión Meet."""

from enum import Enum
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


PROTOCOL_VERSION = "1.1"


class Source(str, Enum):
    CLIENT = "client"
    DAEMON = "daemon"
    EXTENSION = "extension"


class MessageType(str, Enum):
    COMMAND = "command"
    STATE_UPDATE = "state_update"
    EVENT = "event"
    ACK = "ack"
    ERROR = "error"


class Action(str, Enum):
    # Comandos (Cliente -> Daemon -> Extensión)
    TOGGLE_MIC = "TOGGLE_MIC"
    TOGGLE_CAM = "TOGGLE_CAM"
    TOGGLE_HAND = "TOGGLE_HAND"
    ADMIT_ALL = "ADMIT_ALL"
    MUTE_ALL = "MUTE_ALL"
    LEAVE_CALL = "LEAVE_CALL"
    GET_STATE = "GET_STATE"

    # Eventos y Notificaciones
    STATE_SYNC = "STATE_SYNC"
    PAIR_REQUEST = "PAIR_REQUEST"
    PAIRING_SUCCESS = "PAIRING_SUCCESS"
    ADMISSION_REQUESTED = "ADMISSION_REQUESTED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    LOCKED_STATE = "LOCKED_STATE"
    SHOW_ALERT = "SHOW_ALERT"
    DISMISS_ALERT = "DISMISS_ALERT"
    TAB_REGISTER = "TAB_REGISTER"


class ErrorCode(str, Enum):
    ERR_MULTIPLE_CALLS_ACTIVE = "ERR_MULTIPLE_CALLS_ACTIVE"
    ERR_NO_ACTIVE_CALL = "ERR_NO_ACTIVE_CALL"
    ERR_INVALID_COMMAND = "ERR_INVALID_COMMAND"
    ERR_PERMISSION_DENIED = "ERR_PERMISSION_DENIED"
    ERR_TIMEOUT = "ERR_TIMEOUT"
    ERR_EXTENSION_DISCONNECTED = "ERR_EXTENSION_DISCONNECTED"
    ERR_MALFORMED_MESSAGE = "ERR_MALFORMED_MESSAGE"
    ERR_INVALID_PIN = "ERR_INVALID_PIN"
    ERR_PAIRING_REQUIRED = "ERR_PAIRING_REQUIRED"


class StateSyncPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    inCall: bool = False
    micMuted: bool = False
    cameraOff: bool = False
    handRaised: bool = False
    participantCount: int = 0
    waitingRoomCount: int = 0
    isHost: bool = False
    locked: bool = False
    tabId: Optional[str] = None
    pin: Optional[str] = None
    pairingUri: Optional[str] = None
    qrSvg: Optional[str] = None


class LeaveCallPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endForAll: bool = False


class AdmissionRequestedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    count: int = Field(ge=0)


class CommandRejectedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reason: str
    code: str


class PermissionDeniedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    detail: str


class TabRegisterPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tabId: str
    tabState: str = "lobby"  # "lobby", "in_call", "ended"


class Message(BaseModel):
    """Estructura de paquete JSON over WebSocket según especificación v1.1."""
    model_config = ConfigDict(extra="allow", use_enum_values=True)

    version: str = PROTOCOL_VERSION
    source: Source
    type: MessageType
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        data = json.loads(raw)
        return cls(**data)

    @classmethod
    def command(cls, action: Action | str, payload: Optional[Dict[str, Any]] = None, source: Source = Source.CLIENT) -> "Message":
        act = action.value if isinstance(action, Action) else action
        return cls(
            source=source,
            type=MessageType.COMMAND,
            action=act,
            payload=payload or {}
        )

    @classmethod
    def state_sync(cls, state: StateSyncPayload | Dict[str, Any], source: Source = Source.EXTENSION) -> "Message":
        payload = state.model_dump() if isinstance(state, StateSyncPayload) else state
        return cls(
            source=source,
            type=MessageType.STATE_UPDATE,
            action=Action.STATE_SYNC.value,
            payload=payload
        )

    @classmethod
    def event(cls, action: Action | str, payload: Dict[str, Any], source: Source = Source.DAEMON) -> "Message":
        act = action.value if isinstance(action, Action) else action
        return cls(
            source=source,
            type=MessageType.EVENT,
            action=act,
            payload=payload
        )

    @classmethod
    def ack(cls, action: str, payload: Optional[Dict[str, Any]] = None, source: Source = Source.DAEMON) -> "Message":
        return cls(
            source=source,
            type=MessageType.ACK,
            action=action,
            payload=payload or {}
        )

    @classmethod
    def error(cls, reason: str, code: ErrorCode | str, action: str = Action.COMMAND_REJECTED.value, source: Source = Source.DAEMON) -> "Message":
        c_val = code.value if isinstance(code, ErrorCode) else code
        return cls(
            source=source,
            type=MessageType.ERROR,
            action=action,
            payload={"reason": reason, "code": c_val}
        )
