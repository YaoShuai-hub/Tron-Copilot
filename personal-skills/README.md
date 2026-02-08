# Personal Skills Directory

This directory contains **auto-generated skills** created by the `skill-generator` meta-skill.

## Purpose

Skills in this directory are:
- ✅ Created automatically based on user requests
- ✅ Customized for specific needs
- ✅ Separate from system-provided skills
- ✅ Easy to review, modify, or delete

## Organization

```
personal-skills/
├── README.md          # This file
└── [skill-name]/      # Auto-generated skills
    ├── SKILL.md
    ├── scripts/
    └── metadata.json  # Marks as generated
```

## vs. System Skills

| Feature | System Skills (`skills/`) | Personal Skills (`personal-skills/`) |
|---------|---------------------------|-------------------------------------|
| **Created by** | Developers | AI Agent (auto-generated) |
| **Source** | Pre-built, tested | User requirements |
| **Stability** | Production-ready | May need refinement |
| **Version control** | Git tracked | User-managed |
| **Updates** | Via code updates | Regenerate if needed |

## Discovery

The MCP server automatically discovers skills in both directories:
1. System skills loaded first (from `skills/`)
2. Personal skills loaded second (from `personal-skills/`)

Personal skills can **override** system skills if they have the same name.

## Safety

Generated skills are marked with:
```yaml
# In SKILL.md frontmatter
generated: true
author: AI Agent (Self-Generated)
```

And metadata:
```json
// In metadata.json
{
  "created_at": "2026-02-08T...",
  "generated": true,
  "version": "1.0.0"
}
```

## Management

### Delete a skill
```bash
rm -rf personal-skills/[skill-name]
```

### Regenerate a skill
1. Delete the old one
2. Ask the AI to create it again with updated requirements

### Promote to system skill
If a generated skill is stable and useful:
1. Move it to `skills/`
2. Remove `generated: true` flag
3. Add proper tests
4. Commit to git

## Examples

After asking the AI: *"我想查询NFT持有情况"*

The AI generates:
```
personal-skills/
└── nft-holder-checker/
    ├── SKILL.md
    ├── scripts/
    │   └── main.py
    └── metadata.json
```

## Best Practices

1. ✅ **Review before using**: Check generated code for correctness
2. ✅ **Test thoroughly**: Verify functionality before production use
3. ✅ **Provide feedback**: Tell AI if generated skill needs improvements
4. ✅ **Keep organized**: Delete unused skills
5. ✅ **Document changes**: If you manually edit generated code

## Limitations

Auto-generated skills may:
- Need manual refinement for complex tasks
- Require API key configuration
- Have basic error handling initially
- Need testing with real data

The AI will improve them based on your feedback!

## See Also

- [Skill Generator Documentation](../skills/skill-generator/SKILL.md)
- [Anthropic Skills Specification](../skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md)
- [How to Create Custom Skills](../skills/skill-generator/WORKFLOW.md)
