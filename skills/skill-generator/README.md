# Skill Generator - Self-Evolution README

## 🌟 Revolutionary Feature

The **Skill Generator** is a meta-skill that enables your AI agent to **create new skills on demand**. This is true self-evolution!

## Quick Start

### Run the Demo

```bash
cd project/BlockChain-Copilot
python skills/skill-generator/demo.py
```

This interactive demo will walk you through:
1. Analyzing a user request
2. Generating a planning document
3. Creating skill code
4. Saving the skill

### For LLM Integration

When integrating with an LLM (like Claude, GPT-4, etc.), add the prompt from `LLM_PROMPT.py` to your system message. This teaches the LLM how to use the skill generator.

## How It Works

### The Workflow

```
User Request
    ↓
Analyze: Need new skill?
    ↓ Yes
Generate Planning
    ↓
User Reviews & Approves
    ↓
Generate Code (SKILL.md + Python)
    ↓
User Reviews Code
    ↓
Save to Disk
    ↓
Auto-Register (optional)
    ↓
New Skill Active! 🎉
```

### Example: Creating an NFT Tracker

**User:** "我想查询某个地址的NFT持有情况"

**Agent:** 
```
🤔 Analyzing... No existing NFT skill found.

I can create one for you!

📋 Proposed: "nft-holder-checker"
Features:
  1. Query NFT holdings
  2. Show metadata
  3. Calculate value

Approve? (yes/no)
```

**User:** "yes"

**Agent:**
```
✅ Generating...
📄 Created SKILL.md
🐍 Created implementation
💾 Saved!

New skill ready: get_nft_holdings()
```

## Files Structure

```
skills/skill-generator/
├── SKILL.md              # Documentation
├── WORKFLOW.md           # Usage guide
├── LLM_PROMPT.py         # System prompt for LLMs
├── README.md            # This file
├── demo.py              # Interactive demo
├── scripts/
│   └── generator.py     # Core implementation
└── templates/           # Code templates (future)
```

## API Reference

### `analyze_requirement(user_request, existing_skills)`
Determines if a new skill is needed.

**Returns:** 
```python
{
    'needs_new_skill': bool,
    'reason': str,
    'suggested_name': str,
    'complexity': str
}
```

### `generate_skill_plan(user_request, skill_name, existing_skills)`
Creates detailed planning for the new skill.

**Returns:**
```python
{
    'skill_name': str,
    'purpose': str,
    'key_features': List[str],
    'data_sources': List[str],
    'implementation_steps': List[str],
    'estimated_complexity': str,
    'files_to_create': List[str],
    'files_to_modify': List[str]
}
```

### `generate_skill_code(plan, user_request)`
Generates the actual skill implementation.

**Returns:**
```python
{
    'skill_md': str,       # SKILL.md content
    'skill_py': str,       # Python implementation
    'mcp_wrapper': str,    # MCP tool wrapper
    'skill_name': str
}
```

### `save_generated_skill(generated_code)`
Saves the generated skill to disk.

**Returns:**
```python
{
    'success': bool,
    'skill_name': str,
    'created_files': List[str],
    'skill_dir': str
}
```

## Current Limitations

### Cannot Generate (Yet)
- Skills requiring external packages not in requirements
- Skills needing blockchain write operations (for safety)
- Skills with complex UI components

### Can Generate
- ✅ Read-only blockchain queries
- ✅ Data analysis and reporting
- ✅ Transaction builders (unsigned)
- ✅ Custom alerts and monitoring

## Future Enhancements

- [ ] Advanced LLM integration for better code quality
- [ ] Automatic testing of generated skills
- [ ] Skill versioning and updates
- [ ] Community skill marketplace
- [ ] Hot reload (no server restart needed)
- [ ] Skill templates library
- [ ] Usage analytics

## Safety Features

1. **User Approval Required**: Code is never executed without review
2. **Sandboxed Testing**: Generated skills tested in isolation
3. **Version Control**: All generated skills tracked
4. **Rollback**: Easy to delete if not working
5. **Code Review**: User sees all generated code before saving

## Philosophy

> "The best AI agent is one that can teach itself new tricks."

Traditional agents are limited by their pre-programmed capabilities. With the Skill Generator, your agent can adapt to ANY blockchain task by creating new skills on demand.

This is the future of AI agents: **continuous, user-guided evolution**.

## Contributing

Ideas for improving the skill generator:
- Better code generation templates
- More comprehensive error handling
- Automated testing frameworks
- Skill composition (combining multiple skills)
- Natural language to code improvements

## License

Part of BlockChain-Copilot project.
