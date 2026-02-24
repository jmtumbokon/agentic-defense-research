import cedarpy
import json
import re


class CedarEnforcer:
    """
    Security layer that checks agent actions against Cedar policies
    before allowing them to execute in OSWorld.
    """

    def __init__(self, policy_path, entities_path):
        with open(policy_path, "r") as f:
            self.policies = f.read()
        with open(entities_path, "r") as f:
            self.entities = json.load(f)

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
        Returns {"allowed": True/False, "reason": "..."}
        """
        parsed = self.parse_agent_action(raw_action)

        request = {
            "principal": 'Agent::"osworld-agent"',
            "action": f'Action::"{parsed["action"]}"',
            "resource": f'{parsed["resource_type"]}::"{parsed["resource_id"]}"'
        }

        result = cedarpy.is_authorized(request, self.policies, self.entities)

        return {
            "allowed": "allow" in str(result.decision).lower(),
            "action": parsed["action"],
            "resource": parsed["resource_id"],
            "decision": str(result.decision),
            "raw_action": raw_action
        }


# --- Demo ---
if __name__ == "__main__":
    enforcer = CedarEnforcer(
        policy_path="../cedar_policies/agent_policy.cedar",
        entities_path="../cedar_policies/agent_entities.json"
    )

    # Test actions
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
        status = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(f"\nAction:   {action}")
        print(f"Parsed:   {result['action']} on {result['resource']}")
        print(f"Decision: {status}")

if __name__ == "__main__":
    enforcer = CedarEnforcer(
        policy_path="../cedar_policies/agent_policy.cedar",
        entities_path="../cedar_policies/agent_entities.json"
    )

    # Debug: test a raw Cedar request directly
    import cedarpy

    request = {
        "principal": 'Agent::"osworld-agent"',
        "action": 'Action::"click"',
        "resource": 'App::"chrome"'
    }

    result = cedarpy.is_authorized(request, enforcer.policies, enforcer.entities)
    print("Debug decision:", result.decision)
    print("Debug diagnostics:", result.diagnostics)