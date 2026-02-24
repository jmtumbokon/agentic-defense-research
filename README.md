# Agentic Attack & Defense Research

**Author:** Jayden Tumbokon  
**Affiliation:** Stevens Institute of Technology  
**Date:** February 2026

---

## Overview

This project investigates how to constrain AI agents that operate real computer environments. An LLM-based agent is given full control of a virtual Ubuntu desktop — it can click, type, open apps, and browse the web. The question: **can we use policy-based authorization to block dangerous actions before they execute?**

The system pairs two components:
- **OSWorld** — a benchmark that gives AI agents a real desktop to operate in (via VMware Fusion)
- **Cedar** — Amazon's policy language, used here as a security guardrail that evaluates every agent action against permit/forbid rules

## Architecture

```
┌─────────────────────────────────────────────┐
│  LLM Agent (e.g. Gemini 1.5 Pro)           │
│  Receives task → views screenshot → picks   │
│  an action (click, type, open app, etc.)    │
└──────────────────┬──────────────────────────┘
                   │ proposed action
                   ▼
┌─────────────────────────────────────────────┐
│  Cedar Enforcer (cedar_enforcer.py)         │
│  Parses action → classifies it → checks     │
│  against Cedar policies → ALLOW or BLOCK    │
└──────────────────┬──────────────────────────┘
                   │ if allowed
                   ▼
┌─────────────────────────────────────────────┐
│  OSWorld VM (Ubuntu via VMware Fusion)      │
│  Action executes in the virtual desktop     │
│  New screenshot is captured for next step   │
└─────────────────────────────────────────────┘
```

## Project Structure

```
~/research/
├── core_code/                  # Python scripts
│   └── cedar_enforcer.py       # Policy enforcement module
├── cedar_policies/             # Cedar policy definitions
│   ├── agent_policy.cedar      # Permit/forbid rules for the agent
│   └── agent_entities.json     # Entity definitions (agent, apps, resources)
├── osworld_framework/          # OSWorld benchmark codebase
├── experiments/                # Results, screenshots, logs from runs
└── logs/                       # Debug logs
```

## Current Policies

| Rule | Type | Description |
|------|------|-------------|
| Click in Chrome | ✅ Permit | Agent can click within the browser |
| Type in Chrome | ✅ Permit | Agent can enter text in the browser |
| Open Chrome | ✅ Permit | Agent can launch Chrome |
| Open terminal | ❌ Forbid | Agent cannot access the terminal |
| Delete files | ❌ Forbid | Agent cannot delete any files |
| Execute shell commands | ❌ Forbid | Agent cannot run shell commands |

Cedar uses **default deny** — anything not explicitly permitted is blocked. Forbid rules always override permit rules.

## Setup & Prerequisites

### Requirements
- macOS (Apple Silicon) with VMware Fusion 13
- Miniconda (Python 3.10)
- Rust (for Cedar CLI)
- An LLM API key (e.g. Google Gemini)

### Installation

```bash
# 1. Clone this repo
git clone https://github.com/jmtumbokon/agentic-defense-research.git
cd agentic-defense-research

# 2. Create conda environment
conda create -n osworld python=3.10 -y
conda activate osworld

# 3. Install OSWorld dependencies
cd osworld_framework
pip install -r requirements.txt

# 4. Download the Ubuntu VM (~11.4 GB)
python quickstart.py

# 5. Install Rust and Cedar CLI
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install cedar-policy-cli

# 6. Install Cedar Python bindings
pip install cedarpy
```

## Usage

### Run OSWorld benchmark
```bash
cd osworld_framework
export GENAI_API_KEY='your-api-key'
python run.py \
  --provider_name vmware \
  --observation_type screenshot \
  --model gemini-1.5-pro \
  --max_steps 15 \
  --result_dir ../experiments \
  --domain chrome
```

### Test Cedar enforcer (standalone)
```bash
cd core_code
python cedar_enforcer.py
```

### Test Cedar from command line
```bash
cedar authorize \
  --policies ../cedar_policies/agent_policy.cedar \
  --entities ../cedar_policies/agent_entities.json \
  --principal 'Agent::"osworld_agent"' \
  --action 'Action::"click"' \
  --resource 'Application::"chrome"'
```

## Roadmap

- [ ] Integrate Cedar enforcer into OSWorld's live execution loop
- [ ] Add granular policies (URL restrictions, file-path rules, per-app behavior)
- [ ] Run monitored experiments and log blocked actions
- [ ] Design and test prompt injection / attack scenarios
- [ ] Benchmark agent performance with and without policy enforcement

## References

- [OSWorld](https://github.com/xlang-ai/OSWorld) — Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments
- [Cedar](https://www.cedarpolicy.com/) — Amazon's authorization policy language