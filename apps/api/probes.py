"""Transactional companion commands using the existing session ledger namespace."""
import copy
from jsonschema import ValidationError
from core.contracts.guided import GUIDED, validate_probe_response
from core.contracts.validation import validate_record
from roles.pa.session import SessionCommandError, canonical_command
from .commands import CommandHandler


class ProbeCommandHandler(CommandHandler):
    def wrap(self, response):
        value = {"record_type":"RehearsalProbeResponse", "schema_version":"1.0",
                 "command":response, "probe":self.session.probe_state()}
        validate_probe_response(value)
        return value

    def handle(self, command):
        text = canonical_command(command)
        with self.session.command_transaction(), self.ledger.lock:
            existing = self.ledger.get(command["session_id"], command["idempotency_key"])
            if existing is not None:
                if existing["command"] == text:
                    return copy.deepcopy(existing["response"])
                return self.wrap(self._rejected(command,self.session,status=409,code="idempotency_conflict",
                    message="Idempotency key was already used for different content.",retryable=False))
            before = self.session.export_state()
            try:
                validate_record(command,GUIDED,"RehearsalProbeCommand")
                snapshot = self.session.apply_probe(command)
                result = dict(record_type="CommandResponse",schema_version="1.0",session_id=command["session_id"],
                              idempotency_key=command["idempotency_key"],outcome="applied",http_status=200,
                              snapshot=snapshot,error=None)
            except (ValidationError,ValueError,SessionCommandError) as exc:
                self.session.restore_state(before)
                result = self._rejected(command,self.session,
                    status=exc.http_status if isinstance(exc,SessionCommandError) else 422,
                    code=exc.code if isinstance(exc,SessionCommandError) else "invalid_payload",
                    message=str(exc),retryable=False)
            response = self.wrap(result)
            try:
                self.ledger.put(command["session_id"],command["idempotency_key"],text,response,
                                session_state=self.session.export_state())
            except Exception:
                self.session.restore_state(before)
                raise
            return copy.deepcopy(response)
