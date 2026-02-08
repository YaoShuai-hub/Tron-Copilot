"""
Demo: Skill Generator in Action
Shows how the self-evolution system works
"""
import asyncio
from skills.skill_generator.scripts.generator import (
    analyze_requirement,
    generate_skill_plan,
    generate_skill_code,
    save_generated_skill,
    format_plan_for_review
)

async def demo_skill_generation():
    """Demonstrate the full skill generation workflow."""
    
    print("=" * 70)
    print("🚀 SKILL GENERATOR DEMO - Self-Evolving AI Agent")
    print("=" * 70)
    print()
    
    # Simulated user request
    user_request = "我想查询某个地址持有的所有NFT，包括NFT的元数据和价值"
    
    print(f"👤 User Request: \"{user_request}\"")
    print()
    
    # Step 1: Analyze if new skill is needed
    print("Step 1: Analyzing requirement...")
    print("-" * 70)
    
    existing_skills = [
        'token-price', 'wallet-balance', 'swap-tokens',
        'energy-rental', 'transfer-tokens', 'address-risk-checker'
    ]
    
    analysis = await analyze_requirement(user_request, existing_skills)
    
    if analysis['needs_new_skill']:
        print(f"✓ New skill needed: {analysis['reason']}")
        print(f"✓ Suggested name: {analysis['suggested_name']}")
        print(f"✓ Complexity: {analysis['complexity']}")
    else:
        print("✓ Can use existing skills")
        return
    
    print()
    input("Press Enter to continue to planning...")
    print()
    
    # Step 2: Generate planning
    print("Step 2: Generating skill planning...")
    print("-" * 70)
    
    plan = await generate_skill_plan(
        user_request,
        analysis['suggested_name'],
        existing_skills
    )
    
    # Show plan to user
    plan_text = format_plan_for_review(plan)
    print(plan_text)
    
    # Simulate user approval
    approval = input("\n👉 Your decision (yes/no): ").strip().lower()
    
    if approval != 'yes':
        print("❌ Skill generation cancelled")
        return
    
    print()
    print("✅ Plan approved! Proceeding...")
    print()
    input("Press Enter to generate code...")
    print()
    
    # Step 3: Generate code
    print("Step 3: Generating skill code...")
    print("-" * 70)
    print("🔨 Creating SKILL.md...")
    print("🔨 Writing Python implementation...")
    print("🔨 Generating MCP wrapper...")
    
    generated = await generate_skill_code(plan, user_request)
    
    print("✅ Code generation complete!")
    print()
    
    # Show preview
    print("📄 SKILL.md Preview:")
    print("-" * 70)
    print(generated['skill_md'][:400] + "...\n")
    
    print("🐍 Implementation Preview:")
    print("-" * 70)
    print(generated['skill_py'][:400] + "...\n")
    
    # Ask to save
    save_approval = input("💾 Save this skill permanently? (yes/no): ").strip().lower()
    
    if save_approval != 'yes':
        print("❌ Skill not saved (you can regenerate later)")
        return
    
    print()
    input("Press Enter to save skill...")
    print()
    
    # Step 4: Save skill
    print("Step 4: Saving skill to disk...")
    print("-" * 70)
    
    result = save_generated_skill(generated)
    
    if result['success']:
        print(f"✅ Success! Skill '{result['skill_name']}' created!")
        print()
        print("Created files:")
        for file in result['created_files']:
            print(f"  ✓ {file}")
        print()
        print("💡 Next steps:")
        print("  1. Review the generated code")
        print("  2. Add to src/tool_wrappers.py (or use auto-registration)")
        print("  3. Register in src/main.py")
        print("  4. Restart MCP server")
        print("  5. Test the new skill!")
        print()
        print("🎉 Your agent just evolved! 🚀")
    else:
        print("❌ Save failed")
    
    print()
    print("=" * 70)
    print("Demo Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(demo_skill_generation())
