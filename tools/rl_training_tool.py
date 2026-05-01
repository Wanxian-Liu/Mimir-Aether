"""
RL Training Tools Module - Dual-Track Architecture (方案C)

Supports two training tracks with intelligent routing:
- Track 1 (Hermes): Tinker-Atropos external training pipeline (when available)
- Track 2 (MimirAether): Native RL training using MimirAether's rl/ module

The router automatically selects the appropriate track based on:
1. Environment availability (tinker-atropos presence)
2. Configuration preferences
3. Task requirements

Usage:
    from tools.rl_training_tool import (
        rl_list_environments,
        rl_select_environment,
        rl_get_current_config,
        rl_edit_config,
        rl_start_training,
        rl_check_status,
        rl_stop_training,
        rl_get_results,
    )
"""

import ast
import asyncio
import importlib.util
import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# ---------------------------------------------------------------------------
# Track Routing Configuration
# ---------------------------------------------------------------------------

# MimirAether project root
MIMIRAETHER_ROOT = Path(__file__).parent.parent
TINKER_ATROPOS_ROOT = MIMIRAETHER_ROOT / "tinker-atropos"
ENVIRONMENTS_DIR = TINKER_ATROPOS_ROOT / "tinker_atropos" / "environments"
CONFIGS_DIR = TINKER_ATROPOS_ROOT / "configs"
LOGS_DIR = Path.home() / ".mimiraether" / "logs" / "rl_training"

# Check if Hermes track (tinker-atropos) is available
HERMES_TRACK_AVAILABLE = TINKER_ATROPOS_ROOT.exists() and ENVIRONMENTS_DIR.exists()

# Import MimirAether native RL module
try:
    sys.path.insert(0, str(MIMIRAETHER_ROOT))
    from rl import (
        TrajectoryCollector,
        RewardCalculator,
        RewardConfig,
        PPOOptimizer,
        PPOConfig,
        Trainer,
        TrainingConfig,
        Trajectory,
    )
    MIMIRAETHER_RL_AVAILABLE = True
except ImportError as e:
    MIMIRAETHER_RL_AVAILABLE = False
    _import_error = e

logger = logging.getLogger(__name__)


def _ensure_logs_dir():
    """Lazily create logs directory on first use."""
    if HERMES_TRACK_AVAILABLE:
        LOGS_DIR.mkdir(exist_ok=True)


# ============================================================================
# Router Configuration
# ============================================================================

@dataclass
class RLRouterConfig:
    """Configuration for the RL training router."""
    # Preferred track: "auto", "hermes", "mimiraether"
    preferred_track: str = "auto"
    # Hermes track settings
    hermes: Dict[str, Any] = field(default_factory=lambda: {
        "tokenizer_name": "Qwen/Qwen3-8B",
        "rollout_server_url": "http://localhost:8000",
        "use_wandb": True,
        "max_token_length": 8192,
        "max_num_workers": 2048,
        "worker_timeout": 3600,
        "total_steps": 2500,
        "steps_per_eval": 25,
        "max_batches_offpolicy": 3,
        "inference_weight": 1.0,
        "eval_limit_ratio": 0.1,
    })
    # MimirAether track settings
    mimiraether: Dict[str, Any] = field(default_factory=lambda: {
        "num_epochs": 10,
        "trajectories_per_epoch": 32,
        "eval_interval": 5,
        "checkpoint_interval": 5,
        "checkpoint_dir": str(MIMIRAETHER_ROOT / "checkpoints"),
        "save_trajectories": True,
        "trajectory_dir": str(MIMIRAETHER_ROOT / "trajectories"),
    })


# ============================================================================
# Locked Configuration (Hermes Track - Infrastructure Settings)
# ============================================================================

HERMES_LOCKED_FIELDS = {
    "env": {
        "tokenizer_name": "Qwen/Qwen3-8B",
        "rollout_server_url": "http://localhost:8000",
        "use_wandb": True,
        "max_token_length": 8192,
        "max_num_workers": 2048,
        "worker_timeout": 3600,
        "total_steps": 2500,
        "steps_per_eval": 25,
        "max_batches_offpolicy": 3,
        "inference_weight": 1.0,
        "eval_limit_ratio": 0.1,
    },
    "openai": [
        {
            "model_name": "Qwen/Qwen3-8B",
            "base_url": "http://localhost:8001/v1",
            "api_key": "x",
            "weight": 1.0,
            "num_requests_for_eval": 256,
            "timeout": 3600,
            "server_type": "sglang",
        }
    ],
    "tinker": {
        "lora_rank": 32,
        "learning_rate": 0.00004,
        "max_token_trainer_length": 9000,
        "checkpoint_dir": "./temp/",
        "save_checkpoint_interval": 25,
    },
    "slurm": False,
    "testing": False,
}

HERMES_LOCKED_FIELD_NAMES = set(HERMES_LOCKED_FIELDS.get("env", {}).keys())


# ============================================================================
# State Management
# ============================================================================

@dataclass
class EnvironmentInfo:
    """Information about a discovered environment."""
    name: str
    class_name: str
    file_path: str
    description: str = ""
    config_class: str = "BaseEnvConfig"


@dataclass
class RunState:
    """State for a training run."""
    run_id: str
    track: str  # "hermes" or "mimiraether"
    environment: str
    config: Dict[str, Any]
    status: str = "pending"  # pending, starting, running, stopping, stopped, completed, failed
    error_message: str = ""
    wandb_project: str = ""
    wandb_run_name: str = ""
    start_time: float = 0.0
    # Hermes track process handles
    api_process: Optional[subprocess.Popen] = None
    trainer_process: Optional[subprocess.Popen] = None
    env_process: Optional[subprocess.Popen] = None
    # MimirAether track handles
    trainer: Optional["Trainer"] = None
    checkpoint_path: Optional[str] = None


# Global state
_environments: List[EnvironmentInfo] = []
_current_env: Optional[str] = None
_current_config: Dict[str, Any] = {}
_env_config_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
_active_runs: Dict[str, RunState] = {}
_last_status_check: Dict[str, float] = {}
_router_config: RLRouterConfig = RLRouterConfig()

# Rate limiting for status checks (30 minutes)
MIN_STATUS_CHECK_INTERVAL = 30 * 60


# ============================================================================
# Track Router
# ============================================================================

def _get_active_track() -> str:
    """
    Determine which track to use based on availability and preference.
    
    Returns: "hermes" or "mimiraether"
    """
    if _router_config.preferred_track == "hermes":
        if HERMES_TRACK_AVAILABLE:
            return "hermes"
        logger.warning("Hermes track requested but tinker-atropos not available, falling back to MimirAether")
    
    if _router_config.preferred_track == "mimiraether":
        if MIMIRAETHER_RL_AVAILABLE:
            return "mimiraether"
        logger.warning("MimirAether track requested but rl module not available, falling back to Hermes")
    
    # Auto mode: prefer MimirAether, fallback to Hermes
    if MIMIRAETHER_RL_AVAILABLE:
        return "mimiraether"
    if HERMES_TRACK_AVAILABLE:
        return "hermes"
    
    # Neither available
    raise RuntimeError("No RL training track available. MimirAether rl/: {}, Hermes tinker-atropos: {}".format(
        MIMIRAETHER_RL_AVAILABLE, HERMES_TRACK_AVAILABLE
    ))


def _get_track_info() -> Dict[str, Any]:
    """Get information about available tracks."""
    return {
        "active_track": _get_active_track() if (MIMIRAETHER_RL_AVAILABLE or HERMES_TRACK_AVAILABLE) else "none",
        "hermes_available": HERMES_TRACK_AVAILABLE,
        "hermes_path": str(TINKER_ATROPOS_ROOT) if HERMES_TRACK_AVAILABLE else None,
        "mimiraether_available": MIMIRAETHER_RL_AVAILABLE,
        "mimiraether_rl_path": str(MIMIRAETHER_ROOT / "rl"),
        "preferred_track": _router_config.preferred_track,
    }


# ============================================================================
# Environment Discovery (Hermes Track Only)
# ============================================================================

def _scan_environments() -> List[EnvironmentInfo]:
    """Scan the environments directory for BaseEnv subclasses using AST."""
    if not HERMES_TRACK_AVAILABLE or not ENVIRONMENTS_DIR.exists():
        return []
    
    environments = []
    
    for py_file in ENVIRONMENTS_DIR.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        try:
            with open(py_file, "r") as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = ""
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr
                        
                        if base_name == "BaseEnv":
                            env_name = py_file.stem
                            description = ""
                            config_class = "BaseEnvConfig"
                            
                            for item in node.body:
                                if isinstance(item, ast.Assign):
                                    for target in item.targets:
                                        if isinstance(target, ast.Name):
                                            if target.id == "name" and isinstance(item.value, ast.Constant):
                                                env_name = item.value.value
                                            elif target.id == "env_config_cls" and isinstance(item.value, ast.Name):
                                                config_class = item.value.id
                                
                                if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                                    if isinstance(item.value.value, str) and not description:
                                        description = item.value.value.split("\n")[0].strip()
                            
                            environments.append(EnvironmentInfo(
                                name=env_name,
                                class_name=node.name,
                                file_path=str(py_file),
                                description=description or f"Environment from {py_file.name}",
                                config_class=config_class,
                            ))
                            break
        except Exception as e:
            logger.warning("Could not parse %s: %s", py_file, e)
    
    return environments


def _get_env_config_fields(env_file_path: str) -> Dict[str, Dict[str, Any]]:
    """Dynamically import an environment and extract its config fields."""
    try:
        spec = importlib.util.spec_from_file_location("env_module", env_file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["env_module"] = module
        spec.loader.exec_module(module)
        
        env_class = None
        for name, obj in vars(module).items():
            if isinstance(obj, type) and name != "BaseEnv":
                if hasattr(obj, "config_init") and callable(getattr(obj, "config_init")):
                    env_class = obj
                    break
        
        if not env_class:
            return {}
        
        config_class = None
        try:
            env_config, server_configs = env_class.config_init()
            config_class = type(env_config)
        except Exception:
            try:
                from atroposlib.envs.base import BaseEnvConfig
                config_class = BaseEnvConfig
            except ImportError:
                return {}
        
        if not config_class:
            return {}
        
        def make_serializable(val):
            if val is None:
                return None
            if hasattr(val, 'value'):
                return val.value
            if hasattr(val, 'name') and hasattr(val, '__class__') and 'Enum' in str(type(val)):
                return val.name
            return val
        
        fields = {}
        for field_name, field_info in config_class.model_fields.items():
            field_type = field_info.annotation
            default = make_serializable(field_info.default)
            description = field_info.description or ""
            
            is_locked = field_name in HERMES_LOCKED_FIELD_NAMES
            
            type_name = getattr(field_type, "__name__", str(field_type))
            if hasattr(field_type, "__origin__"):
                type_name = str(field_type)
            
            locked_value = HERMES_LOCKED_FIELDS.get("env", {}).get(field_name, default)
            current_value = make_serializable(locked_value) if is_locked else default
            
            fields[field_name] = {
                "type": type_name,
                "default": default,
                "description": description,
                "locked": is_locked,
                "current_value": current_value,
            }
        
        return fields
        
    except Exception as e:
        logger.warning("Could not introspect environment config: %s", e)
        return {}


def _initialize_environments():
    """Initialize environment list on first use."""
    global _environments
    if not _environments and HERMES_TRACK_AVAILABLE:
        _environments = _scan_environments()


# ============================================================================
# Hermes Track: Subprocess Management
# ============================================================================

async def _spawn_hermes_training_run(run_state: RunState, config_path: Path):
    """Hermes track: spawn tinker-atropos training processes."""
    run_id = run_state.run_id
    
    _ensure_logs_dir()
    
    api_log = LOGS_DIR / f"api_{run_id}.log"
    trainer_log = LOGS_DIR / f"trainer_{run_id}.log"
    env_log = LOGS_DIR / f"env_{run_id}.log"
    
    try:
        # Step 1: Start the Atropos API server
        logger.info("[%s] Starting Atropos API server (Hermes track)...", run_id)
        
        api_log_file = open(api_log, "w")
        run_state.api_log_file = api_log_file
        run_state.api_process = subprocess.Popen(
            ["run-api"],
            stdout=api_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
        )
        
        await asyncio.sleep(5)
        
        if run_state.api_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = f"API server exited with code {run_state.api_process.returncode}. Check {api_log}"
            _stop_hermes_run(run_state)
            return
        
        logger.info("[%s] Atropos API server started", run_id)
        
        # Step 2: Start the Tinker trainer
        logger.info("[%s] Starting Tinker trainer (Hermes track)", run_id)
        
        trainer_log_file = open(trainer_log, "w")
        run_state.trainer_log_file = trainer_log_file
        run_state.trainer_process = subprocess.Popen(
            [sys.executable, "launch_training.py", "--config", str(config_path)],
            stdout=trainer_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
            env={**os.environ, "TINKER_API_KEY": os.getenv("TINKER_API_KEY", "")},
        )
        
        logger.info("[%s] Waiting 30 seconds for trainer to initialize...", run_id)
        await asyncio.sleep(30)
        
        if run_state.trainer_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = f"Trainer exited with code {run_state.trainer_process.returncode}. Check {trainer_log}"
            _stop_hermes_run(run_state)
            return
        
        logger.info("[%s] Trainer started, inference server on port 8001", run_id)
        
        # Step 3: Start the environment
        logger.info("[%s] Waiting 90 more seconds before starting environment...", run_id)
        await asyncio.sleep(90)
        
        env_info = None
        for env in _environments:
            if env.name == run_state.environment:
                env_info = env
                break
        
        if not env_info:
            run_state.status = "failed"
            run_state.error_message = f"Environment '{run_state.environment}' not found"
            _stop_hermes_run(run_state)
            return
        
        logger.info("[%s] Starting environment: %s serve", run_id, env_info.file_path)
        
        env_log_file = open(env_log, "w")
        run_state.env_log_file = env_log_file
        run_state.env_process = subprocess.Popen(
            [sys.executable, str(env_info.file_path), "serve", "--config", str(config_path)],
            stdout=env_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
        )
        
        await asyncio.sleep(10)
        
        if run_state.env_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = f"Environment exited with code {run_state.env_process.returncode}. Check {env_log}"
            _stop_hermes_run(run_state)
            return
        
        run_state.status = "running"
        run_state.start_time = time.time()
        logger.info("[%s] Training run started successfully (Hermes track)!", run_id)
        
        asyncio.create_task(_monitor_hermes_run(run_state))
        
    except Exception as e:
        run_state.status = "failed"
        run_state.error_message = str(e)
        _stop_hermes_run(run_state)


async def _monitor_hermes_run(run_state: RunState):
    """Background task to monitor a Hermes training run."""
    while run_state.status == "running":
        await asyncio.sleep(30)
        
        if run_state.env_process and run_state.env_process.poll() is not None:
            exit_code = run_state.env_process.returncode
            run_state.status = "completed" if exit_code == 0 else "failed"
            run_state.error_message = f"Environment process exited with code {exit_code}" if exit_code != 0 else ""
            _stop_hermes_run(run_state)
            break
        
        if run_state.trainer_process and run_state.trainer_process.poll() is not None:
            exit_code = run_state.trainer_process.returncode
            run_state.status = "completed" if exit_code == 0 else "failed"
            run_state.error_message = f"Trainer process exited with code {exit_code}" if exit_code != 0 else ""
            _stop_hermes_run(run_state)
            break
        
        if run_state.api_process and run_state.api_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = "API server exited unexpectedly"
            _stop_hermes_run(run_state)
            break


def _stop_hermes_run(run_state: RunState):
    """Stop all processes for a Hermes training run."""
    for proc_attr in [("env_process", "env_log_file"), ("trainer_process", "trainer_log_file"), ("api_process", "api_log_file")]:
        proc_name, log_name = proc_attr
        proc = getattr(run_state, proc_name, None)
        log_file = getattr(run_state, log_name, None)
        
        if proc and proc.poll() is None:
            logger.info("[%s] Stopping %s...", run_state.run_id, proc_name)
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        if log_file:
            try:
                log_file.close()
            except Exception:
                pass
            setattr(run_state, log_name, None)
    
    if run_state.status == "running":
        run_state.status = "stopped"


# ============================================================================
# MimirAether Track: Native Training
# ============================================================================

def _spawn_mimiraether_training_run(run_state: RunState) -> bool:
    """
    MimirAether track: spawn native RL training.
    
    Returns True if training started successfully.
    """
    if not MIMIRAETHER_RL_AVAILABLE:
        run_state.error_message = "MimirAether RL module not available"
        run_state.status = "failed"
        return False
    
    try:
        # Build components
        reward_config = RewardConfig(
            base_success_reward=_router_config.mimiraether.get("base_success_reward", 1.0),
            base_failure_reward=_router_config.mimiraether.get("base_failure_reward", -0.5),
        )
        
        training_config = TrainingConfig(
            num_epochs=_router_config.mimiraether.get("num_epochs", 10),
            trajectories_per_epoch=_router_config.mimiraether.get("trajectories_per_epoch", 32),
            eval_interval=_router_config.mimiraether.get("eval_interval", 5),
            checkpoint_interval=_router_config.mimiraether.get("checkpoint_interval", 5),
            checkpoint_dir=_router_config.mimiraether.get("checkpoint_dir", str(MIMIRAETHER_ROOT / "checkpoints")),
            save_trajectories=_router_config.mimiraether.get("save_trajectories", True),
            trajectory_dir=_router_config.mimiraether.get("trajectory_dir", str(MIMIRAETHER_ROOT / "trajectories")),
        )
        
        collector = TrajectoryCollector()
        calculator = RewardCalculator(reward_config=reward_config)
        optimizer = PPOOptimizer(config=PPOConfig(
            model_dim=_router_config.mimiraether.get("model_dim", 4096),
            learning_rate=_router_config.mimiraether.get("learning_rate", 1e-4),
        ))
        
        trainer = Trainer(
            collector=collector,
            calculator=calculator,
            optimizer=optimizer,
            config=training_config,
        )
        
        run_state.trainer = trainer
        run_state.status = "running"
        run_state.start_time = time.time()
        
        logger.info("[%s] MimirAether training run started: %d epochs, %d trajectories/epoch",
            run_state.run_id, training_config.num_epochs, training_config.trajectories_per_epoch)
        
        return True
        
    except Exception as e:
        run_state.error_message = f"Failed to start MimirAether training: {e}"
        run_state.status = "failed"
        logger.error("[%s] %s", run_state.run_id, run_state.error_message)
        return False


# ============================================================================
# Tool Implementations with Dual-Track Routing
# ============================================================================

async def rl_list_environments() -> str:
    """
    List all available RL environments.
    
    Hermes track only (MimirAether track uses internal collectors).
    
    Returns:
        JSON string with list of environments and track information
    """
    track_info = _get_track_info()
    _initialize_environments()
    
    response = {
        "track_info": track_info,
        "environments": [
            {
                "name": env.name,
                "class_name": env.class_name,
                "file_path": env.file_path,
                "description": env.description,
            }
            for env in _environments
        ],
        "count": len(_environments),
        "tips": [
            f"Active track: {track_info['active_track']}",
            "Use rl_select_environment(name) to select an environment",
            "MimirAether track uses built-in RL components (TrajectoryCollector, RewardCalculator, PPOOptimizer)",
        ]
    }
    
    return json.dumps(response, indent=2)


async def rl_select_environment(name: str) -> str:
    """
    Select an RL environment for training.
    
    For Hermes track: loads environment config fields.
    For MimirAether track: sets environment name for training metadata.
    
    Args:
        name: Name of the environment to select
    
    Returns:
        JSON string with selection result and track information
    """
    global _current_env, _current_config
    
    track = _get_active_track()
    
    if track == "hermes":
        _initialize_environments()
        
        env_info = None
        for env in _environments:
            if env.name == name:
                env_info = env
                break
        
        if not env_info:
            return json.dumps({
                "error": f"Environment '{name}' not found",
                "available": [e.name for e in _environments],
            }, indent=2)
        
        _current_env = name
        
        config_fields = _get_env_config_fields(env_info.file_path)
        _env_config_cache[name] = config_fields
        
        _current_config = {}
        for field_name, field_info in config_fields.items():
            if not field_info.get("locked", False):
                _current_config[field_name] = field_info.get("default")
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _current_config["wandb_name"] = f"{name}-{timestamp}"
        
        return json.dumps({
            "message": f"Selected environment: {name}",
            "environment": name,
            "file_path": env_info.file_path,
            "track": track,
            "track_info": _get_track_info(),
        }, indent=2)
    
    else:  # mimiraether
        _current_env = name
        _current_config = {"environment": name}
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _current_config["wandb_name"] = f"mimiraether-{name}-{timestamp}"
        
        return json.dumps({
            "message": f"Selected environment: {name} (MimirAether track)",
            "environment": name,
            "track": track,
            "track_info": _get_track_info(),
            "config": {
                "num_epochs": _router_config.mimiraether.get("num_epochs", 10),
                "trajectories_per_epoch": _router_config.mimiraether.get("trajectories_per_epoch", 32),
            }
        }, indent=2)


async def rl_get_current_config() -> str:
    """
    Get the current environment configuration.
    
    Returns track-specific configuration options.
    """
    if not _current_env:
        return json.dumps({
            "error": "No environment selected. Use rl_select_environment(name) first.",
        }, indent=2)
    
    track = _get_active_track()
    
    if track == "hermes":
        config_fields = _env_config_cache.get(_current_env, {})
        
        configurable = []
        locked = []
        
        for field_name, field_info in config_fields.items():
            field_data = {
                "name": field_name,
                "type": field_info.get("type", "unknown"),
                "default": field_info.get("default"),
                "description": field_info.get("description", ""),
                "current_value": _current_config.get(field_name, field_info.get("default")),
            }
            
            if field_info.get("locked", False):
                field_data["locked_value"] = HERMES_LOCKED_FIELDS.get("env", {}).get(field_name)
                locked.append(field_data)
            else:
                configurable.append(field_data)
        
        return json.dumps({
            "environment": _current_env,
            "track": track,
            "configurable_fields": configurable,
            "locked_fields": locked,
            "tip": "Use rl_edit_config(field, value) to change any configurable field.",
        }, indent=2)
    
    else:  # mimiraether
        return json.dumps({
            "environment": _current_env,
            "track": track,
            "configurable_fields": [
                {"name": "num_epochs", "type": "int", "default": _router_config.mimiraether.get("num_epochs", 10),
                 "description": "Number of training epochs"},
                {"name": "trajectories_per_epoch", "type": "int", "default": _router_config.mimiraether.get("trajectories_per_epoch", 32),
                 "description": "Trajectories collected per epoch"},
                {"name": "learning_rate", "type": "float", "default": _router_config.mimiraether.get("learning_rate", 1e-4),
                 "description": "PPO learning rate"},
                {"name": "wandb_project", "type": "str", "default": _router_config.mimiraether.get("wandb_project", "mimiraether-rl"),
                 "description": "WandB project name"},
            ],
            "locked_fields": [
                {"name": "model_dim", "value": _router_config.mimiraether.get("model_dim", 4096),
                 "description": "Model hidden dimension (fixed)"},
            ],
            "tip": "Use rl_edit_config(field, value) to change training parameters.",
        }, indent=2)


async def rl_edit_config(field: str, value: Any) -> str:
    """
    Update a configuration field.
    
    Args:
        field: Name of the field to update
        value: New value for the field
    
    Returns:
        JSON string with updated config or error message
    """
    if not _current_env:
        return json.dumps({
            "error": "No environment selected. Use rl_select_environment(name) first.",
        }, indent=2)
    
    track = _get_active_track()
    
    if track == "hermes":
        config_fields = _env_config_cache.get(_current_env, {})
        
        if field not in config_fields:
            return json.dumps({
                "error": f"Unknown field '{field}'",
                "available_fields": list(config_fields.keys()),
            }, indent=2)
        
        field_info = config_fields[field]
        if field_info.get("locked", False):
            return json.dumps({
                "error": f"Field '{field}' is locked and cannot be changed",
                "locked_value": HERMES_LOCKED_FIELDS.get("env", {}).get(field),
            }, indent=2)
        
        _current_config[field] = value
        
        return json.dumps({
            "message": f"Updated {field} = {value}",
            "field": field,
            "value": value,
            "config": _current_config,
        }, indent=2)
    
    else:  # mimiraether
        mimiraether_fields = ["num_epochs", "trajectories_per_epoch", "learning_rate", "wandb_project", "model_dim"]
        
        if field not in mimiraether_fields:
            return json.dumps({
                "error": f"Unknown field '{field}'",
                "available_fields": mimiraether_fields,
            }, indent=2)
        
        _router_config.mimiraether[field] = value
        _current_config[field] = value
        
        return json.dumps({
            "message": f"Updated {field} = {value} (MimirAether track)",
            "field": field,
            "value": value,
            "track": track,
        }, indent=2)


async def rl_start_training() -> str:
    """
    Start a new RL training run with the current environment and config.
    
    Automatically selects track based on availability.
    
    Returns:
        JSON string with run_id and initial status
    """
    if not _current_env:
        return json.dumps({
            "error": "No environment selected. Use rl_select_environment(name) first.",
        }, indent=2)
    
    track = _get_active_track()
    
    # Generate run ID
    run_id = str(uuid.uuid4())[:8]
    
    if track == "hermes":
        if not os.getenv("TINKER_API_KEY"):
            return json.dumps({
                "error": "TINKER_API_KEY not set. Add it to environment or use MimirAether track.",
            }, indent=2)
        
        env_info = None
        for env in _environments:
            if env.name == _current_env:
                env_info = env
                break
        
        if not env_info or not Path(env_info.file_path).exists():
            return json.dumps({
                "error": f"Environment file not found for '{_current_env}'",
            }, indent=2)
        
        CONFIGS_DIR.mkdir(exist_ok=True)
        config_path = CONFIGS_DIR / f"run_{run_id}.yaml"
        
        import copy
        run_config = copy.deepcopy(HERMES_LOCKED_FIELDS)
        
        if "env" not in run_config:
            run_config["env"] = {}
        
        for field_name, value in _current_config.items():
            if value is not None and value != "":
                run_config["env"][field_name] = value
        
        wandb_project = _current_config.get("wandb_project", "atropos-tinker")
        if "tinker" not in run_config:
            run_config["tinker"] = {}
        run_config["tinker"]["wandb_project"] = wandb_project
        run_config["tinker"]["wandb_run_name"] = f"{_current_env}-{run_id}"
        
        if "wandb_name" in _current_config and _current_config["wandb_name"]:
            run_config["env"]["wandb_name"] = _current_config["wandb_name"]
        
        import yaml
        with open(config_path, "w") as f:
            yaml.dump(run_config, f, default_flow_style=False)
        
        run_state = RunState(
            run_id=run_id,
            track="hermes",
            environment=_current_env,
            config=_current_config.copy(),
            status="starting",
            wandb_project=wandb_project,
            wandb_run_name=f"{_current_env}-{run_id}",
        )
        
        _active_runs[run_id] = run_state
        asyncio.create_task(_spawn_hermes_training_run(run_state, config_path))
        
        return json.dumps({
            "run_id": run_id,
            "status": "starting",
            "environment": _current_env,
            "track": track,
            "config": _current_config,
            "wandb_project": wandb_project,
            "wandb_run_name": f"{_current_env}-{run_id}",
            "config_path": str(config_path),
            "logs": {
                "api": str(LOGS_DIR / f"api_{run_id}.log"),
                "trainer": str(LOGS_DIR / f"trainer_{run_id}.log"),
                "env": str(LOGS_DIR / f"env_{run_id}.log"),
            },
            "message": f"Training starting (Hermes track). Use rl_check_status(run_id) to monitor.",
        }, indent=2)
    
    else:  # mimiraether
        wandb_project = _current_config.get("wandb_project", "mimiraether-rl")
        
        run_state = RunState(
            run_id=run_id,
            track="mimiraether",
            environment=_current_env,
            config=_current_config.copy(),
            status="starting",
            wandb_project=wandb_project,
            wandb_run_name=f"mimiraether-{_current_env}-{run_id}",
        )
        
        _active_runs[run_id] = run_state
        
        if not _spawn_mimiraether_training_run(run_state):
            return json.dumps({
                "error": f"Failed to start MimirAether training: {run_state.error_message}",
            }, indent=2)
        
        return json.dumps({
            "run_id": run_id,
            "status": "running",
            "environment": _current_env,
            "track": track,
            "config": {
                "num_epochs": _router_config.mimiraether.get("num_epochs", 10),
                "trajectories_per_epoch": _router_config.mimiraether.get("trajectories_per_epoch", 32),
            },
            "wandb_project": wandb_project,
            "message": "Training started (MimirAether track). Use rl_check_status(run_id) to monitor.",
        }, indent=2)


async def rl_check_status(run_id: str) -> str:
    """
    Get status and metrics for a training run.
    
    Args:
        run_id: The run ID returned by rl_start_training()
    
    Returns:
        JSON string with run status and metrics
    """
    now = time.time()
    if run_id in _last_status_check:
        elapsed = now - _last_status_check[run_id]
        if elapsed < MIN_STATUS_CHECK_INTERVAL:
            remaining = MIN_STATUS_CHECK_INTERVAL - elapsed
            return json.dumps({
                "rate_limited": True,
                "run_id": run_id,
                "message": f"Rate limited. Next check available in {remaining/60:.0f} minutes.",
                "next_check_in_seconds": remaining,
            }, indent=2)
    
    _last_status_check[run_id] = now
    
    if run_id not in _active_runs:
        return json.dumps({
            "error": f"Run '{run_id}' not found",
            "active_runs": list(_active_runs.keys()),
        }, indent=2)
    
    run_state = _active_runs[run_id]
    
    result = {
        "run_id": run_id,
        "status": run_state.status,
        "track": run_state.track,
        "environment": run_state.environment,
        "wandb_project": run_state.wandb_project,
        "wandb_run_name": run_state.wandb_run_name,
    }
    
    if run_state.error_message:
        result["error"] = run_state.error_message
    
    if run_state.track == "hermes":
        if run_state.start_time:
            result["running_time_minutes"] = (time.time() - run_state.start_time) / 60
        
        processes = {
            "api": run_state.api_process.poll() if run_state.api_process else None,
            "trainer": run_state.trainer_process.poll() if run_state.trainer_process else None,
            "env": run_state.env_process.poll() if run_state.env_process else None,
        }
        result["processes"] = {
            name: "running" if code is None else f"exited ({code})"
            for name, code in processes.items()
        }
        result["logs"] = {
            "api": str(LOGS_DIR / f"api_{run_id}.log"),
            "trainer": str(LOGS_DIR / f"trainer_{run_id}.log"),
            "env": str(LOGS_DIR / f"env_{run_id}.log"),
        }
    
    elif run_state.track == "mimiraether":
        if run_state.start_time:
            result["running_time_minutes"] = (time.time() - run_state.start_time) / 60
        
        if run_state.trainer:
            trainer_status = run_state.trainer.get_status()
            result["trainer_status"] = trainer_status
    
    return json.dumps(result, indent=2)


async def rl_stop_training(run_id: str) -> str:
    """
    Stop a running training job.
    
    Args:
        run_id: The run ID to stop
    
    Returns:
        JSON string with stop confirmation
    """
    if run_id not in _active_runs:
        return json.dumps({
            "error": f"Run '{run_id}' not found",
            "active_runs": list(_active_runs.keys()),
        }, indent=2)
    
    run_state = _active_runs[run_id]
    
    if run_state.status not in ("running", "starting"):
        return json.dumps({
            "message": f"Run '{run_id}' is not running (status: {run_state.status})",
        }, indent=2)
    
    if run_state.track == "hermes":
        _stop_hermes_run(run_state)
    elif run_state.track == "mimiraether":
        run_state.trainer._should_stop = True
        run_state.status = "stopped"
    
    return json.dumps({
        "message": f"Stopped training run '{run_id}'",
        "run_id": run_id,
        "status": run_state.status,
        "track": run_state.track,
    }, indent=2)


async def rl_get_results(run_id: str) -> str:
    """
    Get final results and metrics for a training run.
    
    Args:
        run_id: The run ID to get results for
    
    Returns:
        JSON string with final results
    """
    if run_id not in _active_runs:
        return json.dumps({
            "error": f"Run '{run_id}' not found",
        }, indent=2)
    
    run_state = _active_runs[run_id]
    
    result = {
        "run_id": run_id,
        "status": run_state.status,
        "track": run_state.track,
        "environment": run_state.environment,
        "wandb_project": run_state.wandb_project,
        "wandb_run_name": run_state.wandb_run_name,
    }
    
    if run_state.error_message:
        result["error"] = run_state.error_message
    
    if run_state.track == "mimiraether" and run_state.trainer:
        trainer_status = run_state.trainer.get_status()
        result["training_history"] = trainer_status.get("training_history", {})
        result["total_trajectories"] = trainer_status.get("total_trajectories", 0)
        result["final_metrics"] = {
            "mean_reward": trainer_status.get("training_history", {}).get("epoch_rewards", [0])[-1] if trainer_status.get("training_history", {}).get("epoch_rewards") else 0,
        }
    
    return json.dumps(result, indent=2)


async def rl_list_runs() -> str:
    """
    List all training runs (active and completed).
    
    Returns:
        JSON string with list of runs and their status
    """
    runs = []
    for run_id, run_state in _active_runs.items():
        runs.append({
            "run_id": run_id,
            "environment": run_state.environment,
            "track": run_state.track,
            "status": run_state.status,
            "wandb_run_name": run_state.wandb_run_name,
        })
    
    return json.dumps({
        "runs": runs,
        "count": len(runs),
        "track_info": _get_track_info(),
    }, indent=2)


# ============================================================================
# Hermes Track: Inference Testing (requires OPENROUTER_API_KEY)
# ============================================================================

TEST_MODELS = [
    {"id": "qwen/qwen3-8b", "name": "Qwen3 8B", "scale": "small"},
    {"id": "z-ai/glm-4.7-flash", "name": "GLM-4.7 Flash", "scale": "medium"},
    {"id": "minimax/minimax-m2.7", "name": "MiniMax M2.7", "scale": "large"},
]

DEFAULT_NUM_STEPS = 3
DEFAULT_GROUP_SIZE = 16


async def rl_test_inference(
    num_steps: int = DEFAULT_NUM_STEPS,
    group_size: int = DEFAULT_GROUP_SIZE,
    models: Optional[List[str]] = None,
) -> str:
    """
    Quick inference test for any environment (Hermes track only).
    
    For MimirAether track, use rl_get_current_config to verify setup.
    
    Args:
        num_steps: Steps to run (default: 3)
        group_size: Completions per step (default: 16)
        models: Optional model IDs to test
    
    Returns:
        JSON with results per model
    """
    if not _current_env:
        return json.dumps({
            "error": "No environment selected. Use rl_select_environment(name) first.",
        }, indent=2)
    
    track = _get_active_track()
    
    if track != "hermes":
        return json.dumps({
            "error": "Inference testing is only available on Hermes track (tinker-atropos)",
            "current_track": track,
            "track_info": _get_track_info(),
            "tip": "Inference validation for MimirAether track is handled by the Trainer component",
        }, indent=2)
    
    if not HERMES_TRACK_AVAILABLE:
        return json.dumps({
            "error": "Hermes track (tinker-atropos) not available",
            "track_info": _get_track_info(),
        }, indent=2)
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return json.dumps({
            "error": "OPENROUTER_API_KEY not set. Required for inference testing.",
        }, indent=2)
    
    env_info = None
    for env in _environments:
        if env.name == _current_env:
            env_info = env
            break
    
    if not env_info:
        return json.dumps({
            "error": f"Environment '{_current_env}' not found",
        }, indent=2)
    
    if models:
        test_models = [m for m in TEST_MODELS if m["id"] in models]
        if not test_models:
            test_models = [{"id": m, "name": m, "scale": "custom"} for m in models]
    else:
        test_models = TEST_MODELS
    
    _ensure_logs_dir()
    test_output_dir = LOGS_DIR / "inference_tests"
    test_output_dir.mkdir(exist_ok=True)
    
    results = {
        "environment": _current_env,
        "environment_file": env_info.file_path,
        "track": "hermes",
        "test_config": {
            "num_steps": num_steps,
            "group_size": group_size,
        },
        "models_tested": [],
    }
    
    for model_info in test_models:
        model_id = model_info["id"]
        model_safe_name = model_id.replace("/", "_")
        
        print(f"\n{'='*60}")
        print(f"Testing with {model_info['name']} ({model_id})")
        print(f"{'='*60}")
        
        output_file = test_output_dir / f"test_{_current_env}_{model_safe_name}.jsonl"
        test_run_id = str(uuid.uuid4())[:8]
        wandb_run_name = f"test_inference_RSIAgent_{_current_env}_{test_run_id}"
        
        cmd = [
            sys.executable, env_info.file_path, "process",
            "--env.total_steps", str(num_steps),
            "--env.group_size", str(group_size),
            "--env.use_wandb", "true",
            "--env.wandb_name", wandb_run_name,
            "--env.data_path_to_save_groups", str(output_file),
            "--env.tokenizer_name", HERMES_LOCKED_FIELDS["env"]["tokenizer_name"],
            "--env.max_token_length", str(HERMES_LOCKED_FIELDS["env"]["max_token_length"]),
            "--env.max_num_workers", str(HERMES_LOCKED_FIELDS["env"]["max_num_workers"]),
            "--env.max_batches_offpolicy", str(HERMES_LOCKED_FIELDS["env"]["max_batches_offpolicy"]),
            "--openai.base_url", "https://openrouter.ai/api/v1",
            "--openai.api_key", api_key,
            "--openai.model_name", model_id,
            "--openai.server_type", "openai",
            "--openai.health_check", "false",
        ]
        
        cmd_display = " ".join(str(c) for c in cmd).replace(api_key, "***API_KEY***")
        print(f"Command: {cmd_display}")
        
        model_results = {
            "model": model_id,
            "name": model_info["name"],
            "scale": model_info["scale"],
            "wandb_run": wandb_run_name,
            "steps_tested": 0,
        }
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(TINKER_ATROPOS_ROOT),
            )
            
            stdout_lines = []
            stderr_lines = []
            
            async def read_stream(stream, lines_list, prefix=""):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().rstrip()
                    lines_list.append(decoded)
                    if any(kw in decoded.lower() for kw in ['processing', 'group', 'step', 'progress', '%', 'completed']):
                        print(f"  {prefix}{decoded}")
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_lines, "📊 "),
                        read_stream(process.stderr, stderr_lines, "⚠️ "),
                    ),
                    timeout=600,
                )
            except asyncio.TimeoutError:
                process.kill()
                raise
            
            await process.wait()
            
            log_file = test_output_dir / f"test_{_current_env}_{model_safe_name}.log"
            with open(log_file, "w") as f:
                f.write(f"Command: {cmd_display}\n")
                f.write(f"Return code: {process.returncode}\n")
                f.write("\n".join(stdout_lines))
            
            if process.returncode == 0:
                print("  ✅ Process completed successfully")
                if output_file.exists():
                    with open(output_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    item = json.loads(line)
                                    scores = item.get("scores", [])
                                    model_results["steps_tested"] += 1
                                except json.JSONDecodeError:
                                    continue
            else:
                model_results["error"] = f"Process exited with code {process.returncode}"
                print(f"  ❌ Error: {model_results['error']}")
        
        except asyncio.TimeoutError:
            model_results["error"] = "Process timed out after 10 minutes"
        except Exception as e:
            model_results["error"] = str(e)
        
        results["models_tested"].append(model_results)
    
    return json.dumps(results, indent=2)


# ============================================================================
# Requirements Check
# ============================================================================

def check_rl_python_version() -> bool:
    """Check if Python version meets the minimum for RL tools."""
    return sys.version_info >= (3, 10)


def check_rl_api_keys() -> bool:
    """Check if required API keys and Python version are available."""
    if not check_rl_python_version():
        return False
    # At least one track should have what it needs
    if HERMES_TRACK_AVAILABLE:
        tinker_key = os.getenv("TINKER_API_KEY")
        wandb_key = os.getenv("WANDB_API_KEY")
        if tinker_key and wandb_key:
            return True
    if MIMIRAETHER_RL_AVAILABLE:
        return True
    return False


def get_missing_keys() -> List[str]:
    """Get list of missing requirements for RL tools."""
    missing = []
    if not check_rl_python_version():
        missing.append(f"Python >= 3.10 (current: {sys.version_info.major}.{sys.version_info.minor})")
    if HERMES_TRACK_AVAILABLE:
        if not os.getenv("TINKER_API_KEY"):
            missing.append("TINKER_API_KEY (for Hermes track)")
        if not os.getenv("WANDB_API_KEY"):
            missing.append("WANDB_API_KEY (for Hermes track)")
    if not MIMIRAETHER_RL_AVAILABLE:
        missing.append(f"MimirAether rl/ module (import error: {_import_error if not MIMIRAETHER_RL_AVAILABLE else 'N/A'})")
    return missing


# ---------------------------------------------------------------------------
# Schemas + Registry
# ---------------------------------------------------------------------------

RL_LIST_ENVIRONMENTS_SCHEMA = {"name": "rl_list_environments", "description": "List all available RL environments. Returns track info showing which training track is active (Hermes tinker-atropos or MimirAether native). For Hermes track, returns environment names and paths.", "parameters": {"type": "object", "properties": {}, "required": []}}
RL_SELECT_ENVIRONMENT_SCHEMA = {"name": "rl_select_environment", "description": "Select an RL environment for training. Auto-selects track (Hermes or MimirAether) based on availability. MimirAether track is preferred if available.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Name of the environment to select"}}, "required": ["name"]}}
RL_GET_CURRENT_CONFIG_SCHEMA = {"name": "rl_get_current_config", "description": "Get the current environment configuration. Returns track-specific settings - Hermes track has locked infrastructure fields; MimirAether track exposes training hyperparameters.", "parameters": {"type": "object", "properties": {}, "required": []}}
RL_EDIT_CONFIG_SCHEMA = {"name": "rl_edit_config", "description": "Update a configuration field. For Hermes track: configurable env fields only. For MimirAether track: num_epochs, trajectories_per_epoch, learning_rate.", "parameters": {"type": "object", "properties": {"field": {"type": "string", "description": "Name of the field to update"}, "value": {"description": "New value for the field"}}, "required": ["field", "value"]}}
RL_START_TRAINING_SCHEMA = {"name": "rl_start_training", "description": "Start a new RL training run. Auto-routes to Hermes (tinker-atropos) or MimirAether track based on availability and configuration. MimirAether track is preferred.", "parameters": {"type": "object", "properties": {}, "required": []}}
RL_CHECK_STATUS_SCHEMA = {"name": "rl_check_status", "description": "Get status and metrics for a training run. RATE LIMITED: enforces 30-minute minimum between checks. Returns track-specific status info.", "parameters": {"type": "object", "properties": {"run_id": {"type": "string", "description": "The run ID from rl_start_training()"}}, "required": ["run_id"]}}
RL_STOP_TRAINING_SCHEMA = {"name": "rl_stop_training", "description": "Stop a running training job.", "parameters": {"type": "object", "properties": {"run_id": {"type": "string", "description": "The run ID to stop"}}, "required": ["run_id"]}}
RL_GET_RESULTS_SCHEMA = {"name": "rl_get_results", "description": "Get final results and metrics for a completed training run.", "parameters": {"type": "object", "properties": {"run_id": {"type": "string", "description": "The run ID to get results for"}}, "required": ["run_id"]}}
RL_LIST_RUNS_SCHEMA = {"name": "rl_list_runs", "description": "List all training runs (active and completed) with their status and track.", "parameters": {"type": "object", "properties": {}, "required": []}}
RL_TEST_INFERENCE_SCHEMA = {"name": "rl_test_inference", "description": "Quick inference test (Hermes track only). Runs inference + scoring using OpenRouter to validate environment setup. Not available on MimirAether track.", "parameters": {"type": "object", "properties": {"num_steps": {"type": "integer", "description": "Number of steps (default: 3)", "default": 3}, "group_size": {"type": "integer", "description": "Completions per step (default: 16)", "default": 16}, "models": {"type": "array", "items": {"type": "string"}, "description": "Optional model IDs"}}, "required": []}}

_rl_env = ["TINKER_API_KEY", "WANDB_API_KEY"]

try:
    from tools.registry import registry
    
    registry.register(name="rl_list_environments", emoji="🧪", toolset="rl", schema=RL_LIST_ENVIRONMENTS_SCHEMA,
        handler=lambda args, **kw: rl_list_environments(), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_select_environment", emoji="🧪", toolset="rl", schema=RL_SELECT_ENVIRONMENT_SCHEMA,
        handler=lambda args, **kw: rl_select_environment(name=args.get("name", "")), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_get_current_config", emoji="🧪", toolset="rl", schema=RL_GET_CURRENT_CONFIG_SCHEMA,
        handler=lambda args, **kw: rl_get_current_config(), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_edit_config", emoji="🧪", toolset="rl", schema=RL_EDIT_CONFIG_SCHEMA,
        handler=lambda args, **kw: rl_edit_config(field=args.get("field", ""), value=args.get("value")), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_start_training", emoji="🧪", toolset="rl", schema=RL_START_TRAINING_SCHEMA,
        handler=lambda args, **kw: rl_start_training(), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_check_status", emoji="🧪", toolset="rl", schema=RL_CHECK_STATUS_SCHEMA,
        handler=lambda args, **kw: rl_check_status(run_id=args.get("run_id", "")), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_stop_training", emoji="🧪", toolset="rl", schema=RL_STOP_TRAINING_SCHEMA,
        handler=lambda args, **kw: rl_stop_training(run_id=args.get("run_id", "")), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_get_results", emoji="🧪", toolset="rl", schema=RL_GET_RESULTS_SCHEMA,
        handler=lambda args, **kw: rl_get_results(run_id=args.get("run_id", "")), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_list_runs", emoji="🧪", toolset="rl", schema=RL_LIST_RUNS_SCHEMA,
        handler=lambda args, **kw: rl_list_runs(), check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
    registry.register(name="rl_test_inference", emoji="🧪", toolset="rl", schema=RL_TEST_INFERENCE_SCHEMA,
        handler=lambda args, **kw: rl_test_inference(num_steps=args.get("num_steps", 3), group_size=args.get("group_size", 16), models=args.get("models")),
        check_fn=check_rl_api_keys, requires_env=_rl_env, is_async=True)
except ImportError:
    # Registry not available (e.g., standalone usage)
    pass
