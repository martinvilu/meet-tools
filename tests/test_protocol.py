import pytest
from meet_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    PROTOCOL_VERSION,
    Source,
    StateSyncPayload,
    LeaveCallPayload,
    CommandRejectedPayload,
    PermissionDeniedPayload,
    AdmissionRequestedPayload
)


def test_command_serialization():
    cmd = Message.command(Action.TOGGLE_MIC)
    raw = cmd.to_json()
    parsed = Message.from_json(raw)

    assert parsed.version == PROTOCOL_VERSION
    assert parsed.source == Source.CLIENT
    assert parsed.type == MessageType.COMMAND
    assert parsed.action == "TOGGLE_MIC"
    assert parsed.payload == {}


def test_leave_call_payload():
    payload = LeaveCallPayload(endForAll=True)
    cmd = Message.command(Action.LEAVE_CALL, payload.model_dump())
    assert cmd.payload["endForAll"] is True


def test_state_sync_serialization():
    state = StateSyncPayload(
        inCall=True,
        micMuted=False,
        cameraOff=True,
        handRaised=False,
        participantCount=18,
        waitingRoomCount=3,
        isHost=True,
        tabId="tab-123"
    )
    msg = Message.state_sync(state)
    assert msg.action == "STATE_SYNC"
    assert msg.type == MessageType.STATE_UPDATE
    assert msg.payload["inCall"] is True
    assert msg.payload["participantCount"] == 18
    assert msg.payload["isHost"] is True


def test_error_and_rejection():
    err = Message.error("Múltiples llamadas abiertas", ErrorCode.ERR_MULTIPLE_CALLS_ACTIVE)
    assert err.type == MessageType.ERROR
    assert err.action == "COMMAND_REJECTED"
    assert err.payload["code"] == "ERR_MULTIPLE_CALLS_ACTIVE"
    assert "Múltiples" in err.payload["reason"]


def test_admission_and_permission_denied():
    adm = AdmissionRequestedPayload(count=2)
    msg_adm = Message.event(Action.ADMISSION_REQUESTED, adm.model_dump())
    assert msg_adm.payload["count"] == 2

    perm = PermissionDeniedPayload(action="MUTE_ALL", detail="Falta rol de anfitrión")
    msg_perm = Message.event(Action.PERMISSION_DENIED, perm.model_dump(), source=Source.EXTENSION)
    assert msg_perm.source == Source.EXTENSION
    assert msg_perm.payload["action"] == "MUTE_ALL"
