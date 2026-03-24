# OpenAI + Gemini Research Boilerplate

Dual-provider starter script for the agentic attack & defense project (OSWorld + Cedar).

## Where these files go

```
~/research/                         ← PROJECT_ROOT
├── .env                            ← Your real API keys (git-ignored)
├── .env.template                   ← Safe reference (commit this)
├── .gitignore                      ← Keeps secrets & big files out of git
├── core_code/
│   ├── cedar_enforcer.py           ← Already exists
│   └── openai_research_boilerplate.py  ← NEW — put it here
├── cedar_policies/
│   ├── agent_policy.cedar
│   └── agent_entities.json
├── osworld_framework/
├── experiments/
└── logs/                           ← Token usage logs auto-saved here
```

## Setup

```bash
# 1. Activate your existing environment
conda activate osworld

# 2. Install the two new packages
pip install openai python-dotenv

# 3. Create your .env from the template
cd ~/research
cp .env.template .env
# Edit .env → paste your real OPENAI_API_KEY and GENAI_API_KEY

# 4. Test with a dry run (zero cost)
cd ~/research/core_code
python openai_research_boilerplate.py --dry-run

# 5. Run for real with OpenAI
python openai_research_boilerplate.py --provider openai

# 6. Run for real with Gemini
python openai_research_boilerplate.py --provider gemini

# 7. Override the iteration safety valve
python openai_research_boilerplate.py --provider openai --max-iter 5
```

## What's included

| Feature | How it works |
|---|---|
| **Key security** | Both keys loaded from `~/research/.env` via `python-dotenv` |
| **Reproducibility** | Models pinned: `gpt-4o-2024-08-06` and `gemini-1.5-pro` |
| **Safety valve** | Agentic loop hard-stops at 15 iterations (matches OSWorld max_steps) |
| **Org tracking** | OpenAI `user` param set to `Research_Assistant_Jayden` |
| **Cost awareness** | `--dry-run` previews without API calls; `logs/usage_log.jsonl` tracks tokens |
| **Cedar hook** | Commented-out integration point ready for `cedar_enforcer.py` |

## Integrating Cedar

When you're ready to wire up policy enforcement, uncomment the Cedar block
near line 180 in the script and the check inside `agentic_loop()`. The hook
expects your existing `cedar_enforcer.py` API — `parse_agent_action()` and
`check_action()`.
