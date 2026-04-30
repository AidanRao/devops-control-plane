from datetime import datetime
from typing import List, Optional

from ..config import settings
from .agent_repository import AgentRecord, AgentRepository, JsonAgentRepository


class AgentRegistryService:
    def __init__(self, repository: AgentRepository) -> None:
        self.repository = repository

    def ensure_agent(self, device_id: str) -> AgentRecord:
        existing = self.repository.get_agent(device_id)
        if existing is not None:
            return existing
        return self.repository.save_agent(AgentRecord(device_id=device_id))

    def get_agent(self, device_id: str) -> Optional[AgentRecord]:
        return self.repository.get_agent(device_id)

    def list_agents(self) -> List[AgentRecord]:
        return self.repository.list_agents()

    def get_remark(self, device_id: str) -> Optional[str]:
        record = self.repository.get_agent(device_id)
        return record.remark if record else None

    def set_remark(self, device_id: str, remark: Optional[str]) -> Optional[str]:
        record = self.ensure_agent(device_id)
        record.remark = (remark or "").strip() or None
        self.repository.save_agent(record)
        return record.remark

    def upsert_device_token(
        self, device_id: str, token: str, expires_at: datetime
    ) -> AgentRecord:
        record = self.ensure_agent(device_id)
        record.device_token = token
        record.token_expires_at = expires_at
        return self.repository.save_agent(record)


agent_repository = JsonAgentRepository(
    path=settings.AGENTS_REGISTRY_PATH,
)
agent_registry = AgentRegistryService(agent_repository)
