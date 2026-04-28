from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from ..schemas.rest import (
    AgentCommandHistoryItem,
    CommandResultSummary,
    CommandStatusResponse,
    CreateCommandRequest,
)

# 内存中的命令与结果存储，仅用于 MVP/开发环境。
#
# _commands[task_uuid] = {
#     "request": CreateCommandRequest,
#     "status": "Pending" | "Dispatching" | "Running" | "Succeeded" | "Failed",
#     "targets": ["agent_id", ...],  # 目标 Agent 列表；为空表示广播
#     "created_at": datetime,        # 命令创建时间（UTC）
# }
# _results[task_uuid][agent_id] = CommandResultSummary
_commands: Dict[str, Dict] = {}
_results: Dict[str, Dict[str, CommandResultSummary]] = {}


def create_command(req: CreateCommandRequest) -> str:
    """创建命令并返回 task_uuid。

    初始状态设为 Dispatching，表示已经进入下发流程但尚未收到执行结果。
    targets 为空列表时表示广播到所有在线 Agent。
    """

    task_uuid = str(uuid4())
    _commands[task_uuid] = {
        "request": req,
        "status": "Dispatching",
        "targets": req.targets or [],
        "created_at": datetime.utcnow(),
    }
    return task_uuid


def get_command_status(task_uuid: str):  # -> CommandStatusResponse | None
    cmd = _commands.get(task_uuid)
    if not cmd:
        return None

    targets = cmd.get("targets", [])
    results = _results.get(task_uuid, {})
    if targets:
        filtered = {k: v for k, v in results.items() if k in targets}
    else:
        filtered = results
    return CommandStatusResponse(
        task_uuid=task_uuid,
        status=cmd.get("status", "Pending"),
        results=list(filtered.values()),
    )


def update_result(task_uuid: str, agent_id: str, result: CommandResultSummary) -> None:
    """供 WS result.chunk 处理逻辑调用，用于更新内存结果与任务状态机。

    行为包含两部分：
    - 按 agent 聚合 stdout/stderr：在已有输出基础上 append 新分片内容；
    - 驱动命令级状态机：
      - Pending:      尚未调度（当前实现中不会返回该状态）；
      - Dispatching:  已创建命令、正在下发到 Agent；
      - Running:      收到至少一个非 final 分片；
      - Succeeded:    收到 final 分片且 exitCode == 0；
      - Failed:       收到 final 分片且 exitCode != 0，或 exitCode 缺失。
    """

    # 0) 过滤非目标 Agent 的结果。
    cmd = _commands.get(task_uuid)
    if cmd:
        targets = cmd.get("targets", [])
        if targets and agent_id not in targets:
            return

    # 1) 按 agent 聚合 stdout/stderr。
    bucket = _results.setdefault(task_uuid, {})
    existing = bucket.get(agent_id)

    if existing is not None:
        stdout = (existing.stdout or "") + (result.stdout or "")
        stderr = (existing.stderr or "") + (result.stderr or "")

        # 状态与 exitCode 聚合：以最新的 final 分片为准。
        if result.status == "Finished":
            status = "Finished"
        else:
            status = existing.status or result.status

        exit_code = result.exitCode if result.exitCode is not None else existing.exitCode
    else:
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        status = result.status
        exit_code = result.exitCode

    merged = CommandResultSummary(
        agent_id=agent_id,
        status=status,
        exitCode=exit_code,
        stdout=stdout if stdout != "" else None,
        stderr=stderr if stderr != "" else None,
    )

    bucket[agent_id] = merged

    # 2) 驱动命令级状态机。
    cmd = _commands.setdefault(task_uuid, {"status": "Dispatching"})
    current = cmd.get("status", "Dispatching")

    # 非 final 分片：将命令状态至少提升到 Running。
    if result.status == "Running":
        if current in {"Pending", "Dispatching"}:
            cmd["status"] = "Running"
        return

    # final 分片：根据 exitCode 决定 Succeeded / Failed。
    if result.status == "Finished":
        if exit_code is not None and exit_code == 0:
            cmd["status"] = "Succeeded"
        else:
            cmd["status"] = "Failed"


def list_commands_for_agent(device_id: str) -> List[AgentCommandHistoryItem]:
    """列出某个 Agent 参与过的所有命令，按创建时间倒序。

    匹配规则：
    - 命令 targets 明确包含该 device_id；或
    - 命令为广播（targets 为空）且该 Agent 上报过结果。
    """

    items: List[AgentCommandHistoryItem] = []
    for task_uuid, cmd in _commands.items():
        targets = cmd.get("targets", [])
        agent_result = _results.get(task_uuid, {}).get(device_id)
        is_target = device_id in targets if targets else agent_result is not None
        if not is_target:
            continue

        req: CreateCommandRequest = cmd.get("request")
        items.append(
            AgentCommandHistoryItem(
                task_uuid=task_uuid,
                command=req.command if req else "",
                status=(agent_result.status if agent_result else cmd.get("status", "Pending")),
                exitCode=agent_result.exitCode if agent_result else None,
                createdAt=cmd.get("created_at") or datetime.utcnow(),
                stdout=agent_result.stdout if agent_result else None,
                stderr=agent_result.stderr if agent_result else None,
            )
        )

    items.sort(key=lambda it: it.createdAt, reverse=True)
    return items
