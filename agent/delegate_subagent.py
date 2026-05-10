#!/usr/bin/env python3
"""
SubagentManager - Simple task delegation and result collection for MimirAether.

This module provides a simple framework for delegating tasks to sub-agents
and collecting their results.
"""

import json
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
import os


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a delegable task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class SubagentManager:
    """
    Manages task delegation to sub-agents and result collection.
    
    Supports:
    - Creating tasks
    - Delegating to different agent types (claude-code, codex, hermes-agent)
    - Collecting and aggregating results
    - Persisting task state
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        if workspace_dir is None:
            from mimir_constants import get_mimir_home

            workspace_dir = get_mimir_home() / "tasks"
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self._load_state()
    
    def _load_state(self):
        """Load persisted task state."""
        state_file = self.workspace_dir / "state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    self.tasks = {
                        k: Task(**v, status=TaskStatus(v["status"]))
                        for k, v in data.get("tasks", {}).items()
                    }
            except Exception as e:
                print(f"Warning: Failed to load state: {e}")
    
    def _save_state(self):
        """Persist task state."""
        state_file = self.workspace_dir / "state.json"
        try:
            with open(state_file, "w") as f:
                json.dump({
                    "tasks": {k: v.to_dict() for k, v in self.tasks.items()}
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save state: {e}")
    
    def create_task(self, description: str) -> Task:
        """Create a new task."""
        task = Task(description=description)
        self.tasks[task.id] = task
        self._save_state()
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def delegate_task(
        self,
        task_id: str,
        agent_type: str = "claude-code",
        agent_config: Optional[dict] = None
    ) -> bool:
        """
        Delegate a task to a sub-agent.
        
        Args:
            task_id: The task to delegate
            agent_type: Type of agent (claude-code, codex, hermes-agent)
            agent_config: Additional configuration for the agent
            
        Returns:
            True if delegation was initiated successfully
        """
        task = self.tasks.get(task_id)
        if not task:
            print(f"Task {task_id} not found")
            return False
        
        if task.status != TaskStatus.PENDING:
            print(f"Task {task_id} is not in pending state")
            return False
        
        task.status = TaskStatus.RUNNING
        task.assigned_agent = agent_type
        self._save_state()
        
        # Execute the agent
        try:
            result = self._execute_agent(agent_type, task.description, agent_config or {})
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()
        
        self._save_state()
        return True
    
    def _execute_agent(
        self,
        agent_type: str,
        description: str,
        config: dict
    ) -> dict:
        """Execute an agent with the given task description."""
        # Check if agent CLI is available
        agent_cmd = agent_type
        
        if agent_type == "claude-code":
            agent_cmd = self._find_command(["claude", "claude-code"]) or "claude"
        elif agent_type == "codex":
            agent_cmd = "codex"
        elif agent_type == "hermes-agent":
            agent_cmd = "hermes"
        
        # Build command
        cmd = [agent_cmd, description]
        
        # Execute with timeout
        timeout = config.get("timeout", 300)
        cwd = config.get("cwd", str(Path.cwd()))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            raise Exception(f"Agent execution timed out after {timeout}s")
        except FileNotFoundError:
            raise Exception(f"Agent '{agent_cmd}' not found in PATH")
    
    def _find_command(self, candidates: list[str]) -> Optional[str]:
        """Find the first available command."""
        for cmd in candidates:
            try:
                subprocess.run(["which", cmd], capture_output=True, check=True)
                return cmd
            except subprocess.CalledProcessError:
                continue
        return None
    
    def collect_results(self, task_ids: Optional[list[str]] = None) -> dict:
        """
        Collect results from completed tasks.
        
        Args:
            task_ids: Specific task IDs to collect, or None for all completed
            
        Returns:
            Dictionary mapping task IDs to their results
        """
        if task_ids:
            tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        else:
            tasks = [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
        
        return {
            task.id: {
                "description": task.description,
                "result": task.result,
                "completed_at": task.completed_at
            }
            for task in tasks
        }
    
    def aggregate_results(self, task_ids: Optional[list[str]] = None) -> str:
        """
        Aggregate results into a summary string.
        """
        results = self.collect_results(task_ids)
        
        if not results:
            return "No completed tasks to aggregate."
        
        lines = ["=" * 60, "TASK RESULTS SUMMARY", "=" * 60, ""]
        
        for tid, data in results.items():
            lines.append(f"Task: {data['description']}")
            lines.append(f"  ID: {tid}")
            lines.append(f"  Completed: {data['completed_at']}")
            
            if data["result"]:
                result = data["result"]
                if isinstance(result, dict):
                    if "stdout" in result:
                        lines.append(f"  Output: {result['stdout'][:200]}...")
                    if result.get("returncode", 0) != 0:
                        lines.append(f"  Error: {result.get('stderr', 'Unknown')[:200]}")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            print(f"Cannot cancel task {task_id} with status {task.status.value}")
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now().isoformat()
        self._save_state()
        return True
    
    def clear_completed(self) -> int:
        """Remove completed and failed tasks from state."""
        to_remove = [
            tid for tid, t in self.tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        for tid in to_remove:
            del self.tasks[tid]
        self._save_state()
        return len(to_remove)


# CLI interface
def main():
    """Command-line interface for SubagentManager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Subagent Task Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create task
    create_parser = subparsers.add_parser("create", help="Create a new task")
    create_parser.add_argument("description", help="Task description")
    
    # List tasks
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", choices=["pending", "running", "completed", "failed"], 
                            help="Filter by status")
    
    # Delegate task
    delegate_parser = subparsers.add_parser("delegate", help="Delegate a task")
    delegate_parser.add_argument("task_id", help="Task ID")
    delegate_parser.add_argument("--agent", default="claude-code", help="Agent type")
    
    # Collect results
    collect_parser = subparsers.add_parser("collect", help="Collect results")
    collect_parser.add_argument("--tasks", nargs="*", help="Specific task IDs")
    
    # Aggregate results
    agg_parser = subparsers.add_parser("aggregate", help="Aggregate results")
    agg_parser.add_argument("--tasks", nargs="*", help="Specific task IDs")
    
    args = parser.parse_args()
    
    manager = SubagentManager()
    
    if args.command == "create":
        task = manager.create_task(args.description)
        print(f"Created task: {task.id}")
    
    elif args.command == "list":
        status = TaskStatus(args.status) if args.status else None
        tasks = manager.list_tasks(status)
        for t in tasks:
            print(f"[{t.id}] {t.status.value:10} {t.description[:50]}")
    
    elif args.command == "delegate":
        success = manager.delegate_task(args.task_id, args.agent)
        if success:
            print(f"Delegated task {args.task_id}")
        else:
            print(f"Failed to delegate task {args.task_id}")
    
    elif args.command == "collect":
        results = manager.collect_results(args.tasks)
        print(json.dumps(results, indent=2))
    
    elif args.command == "aggregate":
        print(manager.aggregate_results(args.tasks))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
