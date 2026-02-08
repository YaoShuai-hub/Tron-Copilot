"""
Skill Generator - Meta-skill that creates new skills based on user requirements.
Enables self-evolution of the agent.

References Anthropic's Agent Skills specification for proper formatting.
See: skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md
"""
from typing import Dict, List, Any
from pathlib import Path
import json
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"  # System skills
PERSONAL_SKILLS_DIR = PROJECT_ROOT / "personal-skills"  # User-generated skills
SPEC_PATH = PROJECT_ROOT / "skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md"

def _load_skills_spec() -> str:
    """Load the Anthropic skills specification for reference."""
    try:
        if SPEC_PATH.exists():
            return SPEC_PATH.read_text(encoding='utf-8')
    except:
        pass
    return ""

# Load spec at module level for reference
SKILLS_SPECIFICATION = _load_skills_spec()

async def analyze_requirement(user_request: str, existing_skills: List[str]) -> Dict:
    """
    Analyze user requirement and determine if new skill is needed.
    
    Args:
        user_request: User's request description
        existing_skills: List of existing skill names
        
    Returns:
        Dict with analysis results
    """
    # This would use LLM to analyze the request
    # For now, simplified logic
    
    return {
        'needs_new_skill': True,  # Would be determined by LLM
        'reason': 'No existing skill covers this functionality',
        'suggested_name': _suggest_skill_name(user_request),
        'complexity': _estimate_complexity(user_request)
    }

async def generate_skill_plan(
    user_request: str,
    skill_name: str,
    existing_skills: List[str]
) -> Dict:
    """
    Generate detailed planning for a new skill.
    
    Returns:
        Dict with skill planning ready for user review
    """
    # This would use LLM to generate comprehensive planning
    # Template-based for now
    
    plan = {
        'skill_name': skill_name,
        'purpose': f"Implement functionality requested: {user_request}",
        'key_features': [
            "Feature 1: Based on user request analysis",
            "Feature 2: Core functionality",
            "Feature 3: Error handling and edge cases"
        ],
        'data_sources': [
            "TronScan API",
            "TronGrid API"
        ],
        'implementation_steps': [
            "1. Create SKILL.md documentation",
            "2. Implement core Python logic",
            "3. Add error handling",
            "4. Create MCP tool wrapper",
            "5. Register in main.py",
            "6. Write tests"
        ],
        'estimated_complexity': 'Medium',
        'estimated_time': '2-3 hours',
        'files_to_create': [
            f"personal-skills/{skill_name}/SKILL.md",
            f"personal-skills/{skill_name}/scripts/main.py"
        ],
        'files_to_modify': [
            "src/tool_wrappers.py",
            "src/main.py"
        ]
    }
    
    return plan

async def generate_skill_code(plan: Dict, user_request: str) -> Dict:
    """
    Generate actual skill implementation code based on approved plan.
    
    Returns:
        Dict with generated files content
    """
    skill_name = plan['skill_name']
    
    # Generate SKILL.md
    skill_md = _generate_skill_documentation(plan, user_request)
    
    # Generate Python implementation
    skill_py = _generate_skill_implementation(plan, user_request)
    
    # Generate MCP wrapper
    mcp_wrapper = _generate_mcp_wrapper(plan)
    
    return {
        'skill_md': skill_md,
        'skill_py': skill_py,
        'mcp_wrapper': mcp_wrapper,
        'skill_name': skill_name
    }

def save_generated_skill(generated_code: Dict) -> Dict:
    """
    Save generated skill files to disk in personal-skills/ directory.
    
    Returns:
        Dict with created file paths
    """
    skill_name = generated_code['skill_name']
    # Save to personal-skills directory (not system skills)
    skill_dir = PERSONAL_SKILLS_DIR / skill_name
    
    # Ensure personal-skills directory exists
    PERSONAL_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)
    
    created_files = []
    
    # Save SKILL.md
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(generated_code['skill_md'], encoding='utf-8')
    created_files.append(str(skill_md_path))
    
    # Save implementation
    skill_py_path = skill_dir / "scripts" / "main.py"
    skill_py_path.write_text(generated_code['skill_py'], encoding='utf-8')
    created_files.append(str(skill_py_path))
    
    # Save metadata
    metadata = {
        'created_at': datetime.now().isoformat(),
        'generated': True,
        'version': '1.0.0'
    }
    metadata_path = skill_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    created_files.append(str(metadata_path))
    
    return {
        'success': True,
        'skill_name': skill_name,
        'created_files': created_files,
        'skill_dir': str(skill_dir)
    }

async def refine_skill(skill_name: str, error: str, code: str, client: Any) -> Dict:
    """
    Refine a skill implementation based on execution error.
    
    Args:
        skill_name: Name of the skill
        error: Error message from execution
        code: Original source code
        client: AsyncOpenAI client instance
        
    Returns:
        Dict with success status and message
    """
    print(f"🔧 [SKILL GENERATOR] Refining skill '{skill_name}' based on error...")
    
    try:
        # Construct prompt
        prompt = f"""
You are an expert Python developer for the TRON blockchain.
The following skill code failed during execution.

Skill: {skill_name}
Error: {error}

Code:
```python
{code}
```

Please analyze the error and rewritten the COMPLETE Python code to fix it.
Ensure the code:
1. Handles the error case robustly.
2. Maintains the original functionality.
3. Imports all necessary modules.
4. Uses `src.config.Config` for configuration.

Return ONLY the Python code block. checking for ```python and ```.
"""
        # Call LLM
        response = await client.chat.completions.create(
            model="qwen-plus", # Or usage Config.AI_MODEL if available
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant. Return only code."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        refined_code = response.choices[0].message.content
        
        # Extract code block
        if "```python" in refined_code:
            refined_code = refined_code.split("```python")[1].split("```")[0].strip()
        elif "```" in refined_code:
            refined_code = refined_code.split("```")[1].split("```")[0].strip()
            
        # Save refined code
        skill_dir = PERSONAL_SKILLS_DIR / skill_name
        skill_py_path = skill_dir / "scripts" / "main.py"
        
        # Backup original
        backup_path = skill_dir / "scripts" / f"main.py.bak_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            skill_py_path.rename(backup_path)
        except:
            pass
            
        skill_py_path.write_text(refined_code, encoding='utf-8')
        
        return {
            'success': True,
            'message': f"Skill refined and saved. Backup at {backup_path.name}"
        }
        
    except Exception as e:
        print(f"❌ Refinement failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Helper functions

def _suggest_skill_name(user_request: str) -> str:
    """Generate skill name from user request."""
    # Simplified - would use LLM for better naming
    import re
    # Extract key words and convert to kebab-case
    words = re.findall(r'\w+', user_request.lower())
    return '-'.join(words[:3]) if words else 'custom-skill'

def _estimate_complexity(user_request: str) -> str:
    """Estimate implementation complexity."""
    # Simplified heuristic
    if len(user_request) > 200:
        return "High"
    elif len(user_request) > 100:
        return "Medium"
    else:
        return "Low"

def _generate_skill_implementation(plan: Dict, user_request: str) -> str:
    """Generate Python implementation."""
    skill_name = plan['skill_name']
    
    # improved: Check if template exists
    template_dir = SKILLS_DIR / "skill-generator" / "templates" / skill_name
    if template_dir.exists():
        script_path = template_dir / "scripts" / "main.py"
        if script_path.exists():
            return script_path.read_text(encoding='utf-8')

    code = f'''"""
{skill_name.replace('-', ' ').title()} - Generated skill
Purpose: {plan['purpose']}
"""
import httpx
from typing import Dict
from src.config import Config

TRONSCAN_BASE = Config.TRONSCAN_BASE if hasattr(Config, 'TRONSCAN_BASE') else "https://nileapi.tronscan.org/api"

async def execute_skill(**kwargs) -> Dict:
    """
    Execute the main functionality of this skill.
    
    Args:
        **kwargs: Skill-specific parameters
        
    Returns:
        Dict with execution results
    """
    try:
        # TODO: Implement actual logic based on user requirements
        # This is a template - needs to be filled in based on specific needs
        
        result = {{
            'success': True,
            'message': 'Skill executed successfully (template)',
            'data': {{}}
        }}
        
        return result
    
    except Exception as e:
        return {{
            'success': False,
            'error': str(e),
            'message': 'Execution failed'
        }}

# Additional helper functions as needed
'''
    
    return code

def _generate_skill_documentation(plan: Dict, user_request: str) -> str:
    """Generate SKILL.md content."""
    skill_name = plan['skill_name']
    
    # NOTE: We do NOT load from templates here. 
    # User explicitly requested to use the references (Spec) format.
    # We dynamically generate the documentation to ensure it strictly follows 
    # skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md
    
    return f"""---
name: {skill_name}
description: {plan['purpose']}
version: 1.0.0
generated: true
author: AI Agent (Self-Generated)
tags: [auto-generated, blockchain, tron]
---

# {skill_name.replace('-', ' ').title()}

## When to use this skill

Use this skill when: {user_request}

## Prerequisites

- Valid TRON network connection
- API keys configured in config.toml (if needed)
- Python 3.8+

## Features

"""

def _generate_mcp_wrapper(plan: Dict) -> str:
    """Generate MCP tool wrapper code."""
    skill_name = plan['skill_name']
    function_name = skill_name.replace('-', '_')
    
    wrapper = f'''
# Generated skill: {skill_name}
{function_name}_module = _load_skill_module(project_root / "personal-skills/{skill_name}/scripts/main.py")
{function_name}_execute = {function_name}_module.execute_skill

async def tool_{function_name}(**kwargs) -> str:
    """
    {plan['purpose']}
    """
    print(f"\\n🔧 [SKILL CALL] {skill_name}")
    print(f"   Status: Executing generated skill...\\n")
    
    result = await {function_name}_execute(**kwargs)
    
    if result.get('success'):
        return f"✅ Success: {{result.get('message', '')}}"
    else:
        return f"❌ Error: {{result.get('error', 'Unknown error')}}"
'''
    
    return wrapper

def format_plan_for_review(plan: Dict) -> str:
    """Format planning for user review."""
    output = f"""
📋 New Skill Plan: "{plan['skill_name']}"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Purpose: {plan['purpose']}

Key Features:
"""
    for i, feature in enumerate(plan['key_features'], 1):
        output += f"  {i}. {feature}\n"
    
    output += f"\nData Sources:\n"
    for source in plan['data_sources']:
        output += f"  - {source}\n"
    
    output += f"""
Implementation Steps:
"""
    for step in plan['implementation_steps']:
        output += f"  {step}\n"
    
    output += f"""
Files to Create:
"""
    for file in plan['files_to_create']:
        output += f"  ✓ {file}\n"
    
    output += f"""
Files to Modify:
"""
    for file in plan['files_to_modify']:
        output += f"  ⚠️ {file}\n"
    
    output += f"""
Estimated Complexity: {plan['estimated_complexity']}
Estimated Time: {plan['estimated_time']}

❓ Approve this plan? Reply 'yes' to proceed, 'no' to cancel, or provide feedback for refinement.
"""
    
    return output
