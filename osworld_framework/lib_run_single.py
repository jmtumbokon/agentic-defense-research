import datetime
import json
import logging
import os
import time
from wrapt_timeout_decorator import *
from lib_results_logger import log_task_completion
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "core_code"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from cedar_enforcer import CedarEnforcer
except ImportError:
    CedarEnforcer = None

logger = logging.getLogger("desktopenv.experiment")


def run_single_example(
    agent, env, example, max_steps, instruction, args, example_result_dir, scores
):
    runtime_logger = setup_logger(example, example_result_dir)

    # Initialize Cedar enforcer if enabled via --cedar_enforcer flag
    enforcer = None
    cedar_enabled = getattr(args, "cedar_enforcer", False)
    if cedar_enabled:
        if CedarEnforcer is None:
            logger.warning("Cedar enforcer requested but cedarpy not installed. Running without enforcement.")
        else:
            try:
                enforcer = CedarEnforcer(
                    policy_path=os.path.join(
                        os.path.dirname(__file__), "..", "cedar_policies", "agent_policy.cedar"
                    ),
                    entities_path=os.path.join(
                        os.path.dirname(__file__), "..", "cedar_policies", "agent_entities.json"
                    ),
                )
                logger.info("Cedar enforcer ENABLED for this run")
            except Exception as e:
                logger.error(f"Failed to initialize Cedar enforcer: {e}. Running without enforcement.")
                enforcer = None

    if not cedar_enabled:
        logger.info("Cedar enforcer DISABLED (baseline mode)")

    # Reset environment first to get fresh VM IP
    env.reset(task_config=example)

    # Reset agent with fresh VM IP (for snapshot reverts)
    try:
        agent.reset(runtime_logger, vm_ip=env.vm_ip)
    except Exception as e:
        agent.reset(vm_ip=env.vm_ip)

    time.sleep(5)  # Wait for the environment to be ready
    obs = env._get_obs()  # Get the initial observation
    done = False
    step_idx = 0

    # Track timing for performance comparison
    task_start_time = time.perf_counter()
    total_cedar_time_ms = 0.0
    total_action_time_ms = 0.0

    env.controller.start_recording()

    while not done and step_idx < max_steps:
        response, actions = agent.predict(instruction, obs)
        for action in actions:
            # Capture the timestamp before executing the action
            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S%f")
            logger.info("Step %d: %s", step_idx + 1, action)

            # Cedar Policy Check (if enabled)
            cedar_result = None
            if enforcer is not None:
                cedar_result = enforcer.check_action(action)
                total_cedar_time_ms += cedar_result["check_time_ms"]

                if not cedar_result["allowed"]:
                    logger.warning(
                        "BLOCKED by Cedar: %s -> %s on %s (risk: %s, time: %.4fms)",
                        action,
                        cedar_result["action"],
                        cedar_result["resource"],
                        cedar_result["risk_level"],
                        cedar_result["check_time_ms"],
                    )
                    # Log blocked action to trajectory
                    with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                        f.write(
                            json.dumps(
                                {
                                    "step_num": step_idx + 1,
                                    "action_timestamp": action_timestamp,
                                    "action": action,
                                    "cedar_decision": "BLOCKED",
                                    "cedar_action": cedar_result["action"],
                                    "cedar_resource": cedar_result["resource"],
                                    "cedar_risk_level": cedar_result["risk_level"],
                                    "cedar_check_time_ms": cedar_result["check_time_ms"],
                                }
                            )
                        )
                        f.write("\n")
                    continue  # Skip execution of blocked action

                logger.info(
                    "Cedar ALLOWED: %s (risk: %s, time: %.4fms)",
                    action,
                    cedar_result["risk_level"],
                    cedar_result["check_time_ms"],
                )

            # Execute the action and measure time
            action_start = time.perf_counter()
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            action_end = time.perf_counter()
            action_time_ms = (action_end - action_start) * 1000
            total_action_time_ms += action_time_ms

            logger.info("Reward: %.2f", reward)
            logger.info("Done: %s", done)

            # Save screenshot
            with open(
                os.path.join(
                    example_result_dir, f"step_{step_idx + 1}_{action_timestamp}.png"
                ),
                "wb",
            ) as _f:
                _f.write(obs["screenshot"])

            # Log trajectory with timing and Cedar info
            traj_entry = {
                "step_num": step_idx + 1,
                "action_timestamp": action_timestamp,
                "action": action,
                "response": response,
                "reward": reward,
                "done": done,
                "info": info,
                "action_execution_time_ms": round(action_time_ms, 2),
                "screenshot_file": f"step_{step_idx + 1}_{action_timestamp}.png",
            }

            # Add Cedar info if enforcer is enabled
            if cedar_result is not None:
                traj_entry["cedar_decision"] = "ALLOWED"
                traj_entry["cedar_action"] = cedar_result["action"]
                traj_entry["cedar_resource"] = cedar_result["resource"]
                traj_entry["cedar_risk_level"] = cedar_result["risk_level"]
                traj_entry["cedar_check_time_ms"] = cedar_result["check_time_ms"]

            with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps(traj_entry))
                f.write("\n")

            if done:
                logger.info("The episode is done.")
                break
        step_idx += 1

    # Task complete - measure total time
    task_end_time = time.perf_counter()
    task_total_time_s = task_end_time - task_start_time

    time.sleep(5)  # Wait for the environment to settle
    result = env.evaluate()
    logger.info("Result: %.2f", result)
    scores.append(result)

    # Write result file
    with open(
        os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(f"{result}\n")

    # Write timing summary for this task
    timing_summary = {
        "task_id": example.get("id", "unknown"),
        "task_total_time_s": round(task_total_time_s, 2),
        "total_action_time_ms": round(total_action_time_ms, 2),
        "total_cedar_time_ms": round(total_cedar_time_ms, 4),
        "cedar_enabled": cedar_enabled,
        "score": result,
        "steps_executed": step_idx,
    }

    # Add Cedar stats if enforcer was used
    if enforcer is not None:
        timing_summary["cedar_stats"] = enforcer.get_stats()

    with open(os.path.join(example_result_dir, "timing.json"), "w") as f:
        json.dump(timing_summary, f, indent=2)

    logger.info(
        "Task timing: total=%.2fs, actions=%.2fms, cedar_overhead=%.4fms, cedar=%s",
        task_total_time_s,
        total_action_time_ms,
        total_cedar_time_ms,
        "ON" if cedar_enabled else "OFF",
    )

    # Log task completion to results.json
    log_task_completion(example, result, example_result_dir, args)

    env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))


def setup_logger(example, example_result_dir):
    runtime_logger = logging.getLogger(f"desktopenv.example.{example['id']}")
    runtime_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(
        os.path.join(example_result_dir, "runtime.log")
    )
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    runtime_logger.addHandler(file_handler)
    return runtime_logger
