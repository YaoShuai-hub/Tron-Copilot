# Skill Generator Workflow Guide

## For LLM Agents: How to Use This Skill

### Step 1: Detect Need for New Skill

When user makes a request, check if existing skills can handle it:

```python
from skills.skill_generator.scripts.generator import analyze_requirement

existing_skills = ['token-price', 'wallet-balance', 'transfer-tokens', ...]
analysis = await analyze_requirement(user_request, existing_skills)

if analysis['needs_new_skill']:
    # Proceed to skill generation
```

### Step 2: Generate Planning

```python
from skills.skill_generator.scripts.generator import generate_skill_plan, format_plan_for_review

plan = await generate_skill_plan(
    user_request=user_request,
    skill_name=analysis['suggested_name'],
    existing_skills=existing_skills
)

# Show plan to user for approval
plan_text = format_plan_for_review(plan)
print(plan_text)
```

### Step 3: Wait for User Approval

```
User must explicitly approve with 'yes' or similar confirmation.
If 'no', abandon. If feedback, refine plan and re-present.
```

### Step 4: Generate Code (After Approval)

```python
from skills.skill_generator.scripts.generator import generate_skill_code

generated = await generate_skill_code(plan, user_request)

# Show generated code to user
print("Generated Files:")
print(f"SKILL.md preview:\n{generated['skill_md'][:500]}...\n")
print(f"Implementation preview:\n{generated['skill_py'][:500]}...\n")
```

### Step 5: Save if User Approves

```python
from skills.skill_generator.scripts.generator import save_generated_skill

# After user confirms satisfaction
result = save_generated_skill(generated)

if result['success']:
    print(f"✅ Skill '{result['skill_name']}' saved!")
    print(f"Created files: {result['created_files']}")
    
    # TODO: Auto-register in MCP server (requires restart or hot reload)
```

## Important Notes for LLM

1. **Always get user approval** before generating code
2. **Show previews** of generated files before saving
3. **Explain** what the new skill will do
4. **Test** (if possible) before marking as complete
5. **Document limitations** if generated skill needs refinement

## Example Conversation Flow

```
User: 我想查询某个地址的NFT持有情况

Agent: 🤔 Analyzing your request...
       Current skills don't support NFT queries.
       
       I can create a new skill for you!
       
       📋 Proposed Skill: "nft-holder-checker"
       Purpose: Query NFT holdings for any address
       Features:
         1. Get all NFTs owned by address
         2. Show NFT metadata
         3. Calculate portfolio value
       
       Approve? (yes/no)

User: yes

Agent: ✅ Generating skill...
       [Creating files...]
       
       Preview of generated skill:
       [Shows code snippets]
       
       Save permanently? (yes/no)

User: yes

Agent: 💾 Saved! Skill 'nft-holder-checker' is now available.
       Restarting server to activate...
       
       You can now use it!
```

## Template Customization

The generator uses templates in `skills/skill-generator/templates/`.
Customize these to match your coding style and requirements.
