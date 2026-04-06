from typing import Dict
from uuid import uuid4

from ..schemas.rest import (
    CommandResultSummary,
    CommandStatusResponse,
    CreateCommandRequest,
)

# 内存中的命令与结果存储，仅用于 MVP/开发环境。
#
# _commands[task_uuid] = {
#     "request": CreateCommandRequest,
#     "status": "Pending" | "Dispatching" | "Running" | "Succeeded" | "Failed",
# }
# _results[task_uuid][agent_id] = CommandResultSummary
_commands: Dict[str, Dict] = {}
_results: Dict[str, Dict[str, CommandResultSummary]] = {}


def create_command(req: CreateCommandRequest) -> str:
    """创建命令并返回 task_uuid。

    初始状态设为 Dispatching，表示已经进入下发流程但尚未收到执行结果。
    """

    task_uuid = str(uuid4())
    _commands[task_uuid] = {
        "request": req,
        "status": "Dispatching",
    }
    return task_uuid


def get_command_status(task_uuid: str):  # -> CommandStatusResponse | None
    cmd = _commands.get(task_uuid)
    if not cmd:
        return None

    results = _results.get(task_uuid, {})
    return CommandStatusResponse(
        task_uuid=task_uuid,
        status=cmd.get("status", "Pending"),
        results=results,
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
