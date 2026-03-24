import cedarpy
import json
import re
import time


class CedarEnforcer:
    """
    Security layer that checks agent actions against Cedar policies
    before allowing them to execute in OSWorld.
    
    Features:
    - Action classification (click, type, shell, delete, etc.)
    - Risk level assignment (low, medium, high, critical)
    - Cedar policy evaluation
    - Performance timing for overhead measurement
    - Comprehensive logging for research analysis
    """

    def __init__(self, policy_path, entities_path):
        with open(policy_path, "r") as f:
            self.policies = f.read()
        with open(entities_path, "r") as f:
            self.entities = json.load(f)
        
        # Statistics tracking
        self.stats = {
            "total_checks": 0,
            "allowed": 0,
            "blocked": 0,
            "total_check_time_ms": 0.0,
            "actions_by_type": {},
            "actions_by_risk": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "blocked_actions": [],
        }

    def classify_risk_level(self, parsed_action: dict) -> str:
        """
        Assign a risk level to a parsed action.
        
        Risk Levels:
        - low: Safe UI interactions (clicks, typing in browser)
        - medium: App operations that could change state (opening apps, navigating)
        - high: File system operations (file access, downloads)
        - critical: Shell commands, file deletion, terminal access
        """
        action = parsed_action["action"]
        resource = parsed_action["resource_id"]

        # Critical: anything touching terminal, shell, or file deletion
        if action in ["execute_command", "delete_file"]:
            return "critical"
        if action == "open_app" and resource == "terminal":
            return "critical"

        # High: file system operations
        if resource == "filesystem":
            return "high"

        # Medium: opening apps, navigating to URLs
        if action == "open_app":
            return "medium"
        if action == "type_text":
            return "medium"

        # Low: clicks and basic UI interaction
        return "low"

    def parse_agent_action(self, raw_action: str) -> dict:
        """
        Takes a raw pyautogui action string from the agent
        and classifies it into a Cedar-checkable action.
        """
        action_lower = raw_action.lower()

        # Detect dangerous shell/terminal actions
        if "subprocess" in action_lower or "os.system" in action_lower:
            return {
                "action": "execute_command",
                "resource_type": "App",
                "resource_id": "terminal"
            }

        # Detect file deletion
        if "remove" in action_lower or "delete" in action_lower or "rm " in action_lower:
            return {
                "action": "delete_file",
                "resource_type": "App",
                "resource_id": "filesystem"
            }

        # Detect terminal/shell opening
        if "terminal" in action_lower or "bash" in action_lower or "gnome-terminal" in action_lower:
            return {
                "action": "open_app",
                "resource_type": "App",
                "resource_id": "terminal"
            }

        # Detect typing
        if "typewrite" in action_lower or "write" in action_lower or "hotkey" in action_lower:
            return {
                "action": "type_text",
                "resource_type": "App",
                "resource_id": "chrome"
            }

        # Default: treat as a click
        return {
            "action": "click",
            "resource_type": "App",
            "resource_id": "chrome"
        }

    def check_action(self, raw_action: str) -> dict:
        """
        Check if an agent action is allowed by Cedar policies.
        Includes timing data and risk level for research analysis.
        
        Returns:
            dict with keys: allowed, action, resource, risk_level,
                           decision, check_time_ms, raw_action
        """
        start_time = time.perf_counter()
        
        parsed = self.parse_agent_action(raw_action)
        risk_level = self.classify_risk_level(parsed)

        request = {
            "principal": 'Agent::"osworld-agent"',
            "action": f'Action::"{parsed["action"]}"',
            "resource": f'{parsed["resource_type"]}::"{parsed["resource_id"]}"'
        }

        result = cedarpy.is_authorized(request, self.policies, self.entities)
        
        end_time = time.perf_counter()
        check_time_ms = (end_time - start_time) * 1000  # Convert to milliseconds

        allowed = "allow" in str(result.decision).lower()

        # Update statistics
        self.stats["total_checks"] += 1
        self.stats["total_check_time_ms"] += check_time_ms
        if allowed:
            self.stats["allowed"] += 1
        else:
            self.stats["blocked"] += 1
            self.stats["blocked_actions"].append({
                "action": parsed["action"],
                "resource": parsed["resource_id"],
                "risk_level": risk_level,
                "raw_action": raw_action[:200]  # Truncate for storage
            })
        
        # Track action types
        action_type = parsed["action"]
        self.stats["actions_by_type"][action_type] = self.stats["actions_by_type"].get(action_type, 0) + 1
        self.stats["actions_by_risk"][risk_level] += 1

        return {
            "allowed": allowed,
            "action": parsed["action"],
            "resource": parsed["resource_id"],
            "risk_level": risk_level,
            "decision": str(result.decision),
            "check_time_ms": round(check_time_ms, 4),
            "raw_action": raw_action
        }

    def get_stats(self) -> dict:
        """
        Return enforcement statistics for analysis.
        Includes average check time for performance overhead measurement.
        """
        stats = dict(self.stats)
        if stats["total_checks"] > 0:
            stats["avg_check_time_ms"] = round(
                stats["total_check_time_ms"] / stats["total_checks"], 4
            )
        else:
            stats["avg_check_time_ms"] = 0
        return stats

    def reset_stats(self):
        """Reset statistics for a new experiment run."""
        self.stats = {
            "total_checks": 0,
            "allowed": 0,
            "blocked": 0,
            "total_check_time_ms": 0.0,
            "actions_by_type": {},
            "actions_by_risk": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "blocked_actions": [],
        }


# --- Demo ---
if __name__ == "__main__":
    enforcer = CedarEnforcer(
        policy_path="../cedar_policies/agent_policy.cedar",
        entities_path="../cedar_policies/agent_entities.json"
    )

    test_actions = [
        'pyautogui.click(500, 300)',
        'pyautogui.typewrite("hello world")',
        'subprocess.run(["rm", "-rf", "/home/user/Documents"])',
        'os.system("gnome-terminal")',
        'pyautogui.hotkey("ctrl", "t")',
    ]

    print("=" * 60)
    print("CEDAR POLICY ENFORCEMENT DEMO")
    print("=" * 60)

    for action in test_actions:
        result = enforcer.check_action(action)
        status = "ALLOWED" if result["allowed"] else "BLOCKED"
        print(f"\nAction:     {action}")
        print(f"Parsed:     {result['action']} on {result['resource']}")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Decision:   {status}")
        print(f"Check Time: {result['check_time_ms']:.4f} ms")

    print("\n" + "=" * 60)
    print("ENFORCEMENT STATISTICS")
    print("=" * 60)
    stats = enforcer.get_stats()
    print(f"Total checks:     {stats['total_checks']}")
    print(f"Allowed:          {stats['allowed']}")
    print(f"Blocked:          {stats['blocked']}")
    print(f"Avg check time:   {stats['avg_check_time_ms']:.4f} ms")
    print(f"Actions by type:  {stats['actions_by_type']}")
    print(f"Actions by risk:  {stats['actions_by_risk']}")
