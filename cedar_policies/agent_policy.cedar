// ALLOW: Agent can open browsers
permit (
  principal == Agent::"osworld-agent",
  action == Action::"open_app",
  resource == App::"chrome"
);

// ALLOW: Agent can type in search bars
permit (
  principal == Agent::"osworld-agent",
  action == Action::"type_text",
  resource == App::"chrome"
);

// ALLOW: Agent can click UI elements
permit (
  principal == Agent::"osworld-agent",
  action == Action::"click",
  resource == App::"chrome"
);

// DENY: Agent cannot access the terminal
forbid (
  principal == Agent::"osworld-agent",
  action == Action::"open_app",
  resource == App::"terminal"
);

// DENY: Agent cannot delete files
forbid (
  principal == Agent::"osworld-agent",
  action == Action::"delete_file",
  resource
);

// DENY: Agent cannot run shell commands
forbid (
  principal == Agent::"osworld-agent",
  action == Action::"execute_command",
  resource
);