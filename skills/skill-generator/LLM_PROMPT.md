# LLM Prompt: How to Generate Skills Following Anthropic Specification

When generating new skills for BlockChain-Copilot, you MUST follow the Anthropic Agent Skills specification.

## Required Reading

**BEFORE generating any skill, read:**
`skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md`

This document contains the official specification that all generated skills must follow.

## Key Requirements from Spec

### 1. SKILL.md Frontmatter (REQUIRED)

```yaml
---
name: skill-name-in-kebab-case
description: One-line description of when to use this skill
version: 1.0.0
generated: true  # Mark as auto-generated
author: AI Agent (Self-Generated)
tags: [auto-generated, blockchain, tron]  # Add relevant tags
---
```

### 2. SKILL.md Structure (REQUIRED)

```markdown
# Skill Name

## When to use this skill
Clear criteria for activation

## Prerequisites
What's needed before using

## Features
List of capabilities

## Data Sources
Which APIs/services used

## How to use
Step-by-step with code examples

## Error Handling
Common errors and solutions

## Limitations
What it cannot do

## References
Links to docs, specs
```

### 3. Directory Structure (REQUIRED)

```
new-skill/
├── SKILL.md              # Required
└── scripts/
    └── main.py          # Main implementation
```

Optional but recommended:
```
new-skill/
├── SKILL.md
├── scripts/
│   ├── main.py
│   └── helpers.py       # If needed
├── references/          # Documentation
│   └── api_docs.md
└── tests/              # Unit tests
    └── test_main.py
```

### 4. Code Standards

**Python Implementation MUST:**
- Export an `execute_skill()` async function
- Accept `**kwargs` for flexibility
- Return Dict with: `{'success': bool, 'message': str, 'data': dict}`
- Include error handling with try/except
- Validate inputs
- Document parameters with docstrings

**Example:**

```python
"""
skill-name - Auto-generated skill
Purpose: [Description]
"""
import httpx
from typing import Dict
from src.config import Config

async def execute_skill(**kwargs) -> Dict:
    """
    Execute the main functionality.
    
    Args:
        **kwargs: Skill-specific parameters
        
    Returns:
        Dict with execution results
    """
    try:
        # Validate inputs
        # Call APIs
        # Process data
        
        return {
            'success': True,
            'message': 'Execution successful',
            'data': {}
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Execution failed'
        }
```

### 5. Naming Conventions (REQUIRED)

- **Skill folders**: `kebab-case` (e.g., `token-price`)
- **Python files**: `snake_case` (e.g., `fetch_price.py`)
- **Functions**: `snake_case` (e.g., `get_token_price`)
- **MCP tools**: `snake_case` (e.g., `tool_get_token_price`)

### 6. Security Requirements (CRITICAL)

Generated skills MUST:
- ✅ Never store private keys
- ✅ Validate all addresses before API calls
- ✅ Return unsigned transactions only
- ✅ Handle API rate limits
- ✅ Sanitize user inputs
- ✅ Use proper error handling

### 7. MCP Integration Template

When generating a skill, also provide the MCP wrapper code:

```python
# Add to src/tool_wrappers.py
skill_module = _load_skill_module(project_root / "skills/{skill-name}/scripts/main.py")
skill_execute = skill_module.execute_skill

async def tool_{skill_name}(**kwargs) -> str:
    """
    {skill description}
    """
    print(f"\\n🔧 [SKILL CALL] {skill-name}")
    print(f"   Status: Executing...\\n")
    
    result = await skill_execute(**kwargs)
    
    if result.get('success'):
        return format_success_output(result)
    else:
        return format_error_output(result)

# Add to src/main.py
@mcp.tool()
async def {skill_name}(**kwargs) -> str:
    """{skill description}"""
    return await tool_{skill_name}(**kwargs)
```

## Generation Workflow

1. **Read the spec**: Load `ANTHROPIC_SKILLS_SPEC.md` content
2. **Analyze request**: Understand what user needs
3. **Plan structure**: Decide sections and features
4. **Generate SKILL.md**: Follow spec template exactly
5. **Generate code**: Follow Python standards
6. **Generate MCP wrapper**: Provide integration code
7. **Document limitations**: Be honest about auto-generation

## Quality Checklist

Before presenting a generated skill to user:

- [ ] SKILL.md has valid YAML frontmatter
- [ ] SKILL.md follows section structure from spec
- [ ] Code has proper error handling
- [ ] Function returns structured Dict
- [ ] Security requirements met
- [ ] Naming conventions followed
- [ ] MCP integration code provided
- [ ] Limitations documented

## Example Generation Prompt

When user requests: "我想查询NFT持有情况"

Your response should:

1. Acknowledge: "I'll create a new skill following the Agent Skills specification"
2. Show plan: Display the structure you'll create
3. Generate: Create SKILL.md and code following ALL requirements above
4. Explain: Tell user what was created and how to use it

## Critical Reminder

**Every generated skill MUST reference the spec:**

Add to SKILL.md:
```markdown
## References

This skill follows the Anthropic Agent Skills specification.
See: `skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md`
```

This ensures consistency and quality across all generated skills.
