# Agent Skills Specification (Anthropic)

> ## Documentation Index
> Fetch the complete documentation index at: https://agentskills.io/llms.txt
> Use this file to discover all available pages before exploring further.

## What are skills?

> Agent Skills are a lightweight, open format for extending AI agent capabilities with specialized knowledge and workflows.

At its core, a skill is a folder containing a `SKILL.md` file. This file includes metadata (`name` and `description`, at minimum) and instructions that tell an agent how to perform a specific task. Skills can also bundle scripts, templates, and reference materials.

```directory
my-skill/
├── SKILL.md          # Required: instructions + metadata
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

## How skills work

Skills use **progressive disclosure** to manage context efficiently:

1. **Discovery**: At startup, agents load only the name and description of each available skill, just enough to know when it might be relevant.

2. **Activation**: When a task matches a skill's description, the agent reads the full `SKILL.md` instructions into context.

3. **Execution**: The agent follows the instructions, optionally loading referenced files or executing bundled code as needed.

This approach keeps agents fast while giving them access to more context on demand.

## The SKILL.md file

Every skill starts with a `SKILL.md` file containing YAML frontmatter and Markdown instructions:

```markdown
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents.
---

# PDF Processing

## When to use this skill
Use this skill when the user needs to work with PDF files...

## How to extract text
1. Use pdfplumber for text extraction...

## How to fill forms
...
```

The following frontmatter is required at the top of `SKILL.md`:

* `name`: A short identifier
* `description`: When to use this skill

The Markdown body contains the actual instructions and has no specific restrictions on structure or content.

This simple format has some key advantages:

* **Self-documenting**: A skill author or user can read a `SKILL.md` and understand what it does, making skills easy to audit and improve.

* **Extensible**: Skills can range in complexity from just text instructions to executable code, assets, and templates.

* **Portable**: Skills are just files, so they're easy to edit, version, and share.

## SKILL.md Best Practices

### 1. Clear Frontmatter

Always include:
- `name`: Kebab-case identifier (e.g., `token-price`, `wallet-balance`)
- `description`: One-line summary of when to use this skill

Optional but recommended:
- `version`: Semantic version (e.g., `1.0.0`)
- `author`: Creator name or organization
- `tags`: Array of relevant tags

### 2. Structured Content

Organize your SKILL.md with clear sections:

```markdown
# [Skill Name]

## When to use this skill
Clear criteria for when to activate this skill

## Prerequisites
What the user needs before using this skill

## How to [Primary Function]
Step-by-step instructions

## Examples
Concrete usage examples

## Error Handling
How to handle common failures

## Limitations
What this skill cannot do
```

### 3. Progressive Disclosure

Start with high-level guidance, then provide detail:

```markdown
## How to query blockchain data

Quick version: Call the API endpoint with the address.

Detailed steps:
1. Validate the address format
2. Construct the API request
3. Handle rate limits
4. Parse the response
...
```

### 4. Code Examples

Include executable code when helpful:

```markdown
## Example Usage

```python
from skills.token_price.scripts.fetch_price import get_token_price

price = await get_token_price("TRX")
print(f"Current price: ${price}")
```
```

### 5. Reference External Resources

Link to APIs, documentation, or bundled files:

```markdown
## API Reference

See the [TronScan API Documentation](https://tronscan.org/api-docs)

For detailed examples, see: `references/api_examples.md`
```

## Directory Structure Standards

### Minimal Skill
```
my-skill/
└── SKILL.md
```

### Standard Skill
```
token-price/
├── SKILL.md
└── scripts/
    └── fetch_price.py
```

### Complex Skill
```
swap-tokens/
├── SKILL.md
├── scripts/
│   ├── build_swap.py
│   └── helpers.py
├── references/
│   ├── sunswap_api.md
│   └── examples.md
└── assets/
    └── route_templates.json
```

## Integration with MCP (Model Context Protocol)

BlockChain-Copilot uses MCP to expose skills as tools. Each skill should:

1. **Be self-contained**: All logic in `scripts/`
2. **Export clear functions**: Easy to wrap in MCP tools
3. **Handle errors gracefully**: Return structured error messages
4. **Document parameters**: Clear function signatures

Example MCP integration:

```python
# In src/tool_wrappers.py
from skills.token_price.scripts.fetch_price import get_token_price

async def tool_get_token_price(symbol: str) -> str:
    """
    Get current token price.
    
    Args:
        symbol: Token symbol (e.g., 'TRX', 'USDT')
    """
    result = await get_token_price(symbol)
    return format_price_output(result)

# In src/main.py
@mcp.tool()
async def get_token_price(symbol: str) -> str:
    """Get current price of a token."""
    return await tool_get_token_price(symbol)
```

## Skill Naming Conventions

Use kebab-case for skill names:
- ✅ `token-price`
- ✅ `wallet-balance`
- ✅ `address-risk-checker`
- ❌ `TokenPrice`
- ❌ `wallet_balance`

Function names should be:
- Python functions: `snake_case`
- MCP tools: `snake_case`
- Skill folders: `kebab-case`

## Version Control

Include version in frontmatter:

```yaml
---
name: token-price
description: Get real-time token prices from multiple sources
version: 1.2.0
---
```

Follow semantic versioning:
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

## Testing Skills

Each skill should be testable:

```
token-price/
├── SKILL.md
├── scripts/
│   └── fetch_price.py
└── tests/
    └── test_fetch_price.py
```

## Security Considerations

Skills handling blockchain data should:

1. **Never store private keys**
2. **Validate all addresses** before API calls
3. **Handle API failures** gracefully
4. **Rate limit** API requests
5. **Sanitize user input**
6. **Return unsigned transactions** for user approval

## Example: Complete SKILL.md Template

```markdown
---
name: example-skill
description: A template for creating new skills
version: 1.0.0
author: BlockChain-Copilot Team
tags: [template, example]
---

# Example Skill

## When to use this skill

Use this skill when you need to demonstrate skill structure.

## Prerequisites

- Valid API key in config.toml
- Python 3.8+

## How to use

1. Import the skill:
```python
from skills.example_skill.scripts.main import execute
```

2. Call the function:
```python
result = await execute(param="value")
```

## Examples

### Basic Usage
```python
result = await execute(param="test")
print(result)  # Output: {...}
```

## Error Handling

Common errors:
- `InvalidParameterError`: Check parameter format
- `APIError`: Verify API key and network connection

## Limitations

- Only supports Nile testnet currently
- Maximum 100 requests per minute

## API Reference

See [API Documentation](references/api.md)
```

## Next Steps

* [View full specification](https://agentskills.io/specification)
* [See example skills](https://github.com/anthropics/skills)
* [Read best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
* [Reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref)
