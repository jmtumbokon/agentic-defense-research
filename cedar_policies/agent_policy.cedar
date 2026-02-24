permit (
  principal == Agent::"osworld-agent",
  action == Action::"open_app",
  resource == App::"chrome"
);

permit (
  principal == Agent::"osworld-agent",
  action == Action::"type_text",
  resource == App::"chrome"
);

permit (
  principal == Agent::"osworld-agent",
  action == Action::"click",
  resource == App::"chrome"
);

forbid (
  principal == Agent::"osworld-agent",
  action == Action::"open_app",
  resource == App::"terminal"
);

forbid (
  principal == Agent::"osworld-agent",
  action == Action::"delete_file",
  resource
);

forbid (
  principal == Agent::"osworld-agent",
  action == Action::"execute_command",
  resource
);