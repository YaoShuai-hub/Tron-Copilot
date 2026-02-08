import os
from pathlib import Path
from typing import Dict, List, Any
import yaml

class SkillsLoader:
    """Loads and manages Agent Skills following Anthropic's Skills format.
    
    Scans both system skills (skills/) and personal skills (personal-skills/).
    Personal skills take priority over system skills if names conflict.
    """
    
    def __init__(self, skills_dir: str = "skills", personal_skills_dir: str = "personal-skills"):
        self.skills_dir = Path(skills_dir)
        self.personal_skills_dir = Path(personal_skills_dir)
        self.skills_metadata: Dict[str, Dict[str, Any]] = {}
        self.skills_instructions: Dict[str, str] = {}
        
    def discover_skills(self) -> List[Dict[str, str]]:
        """Discover all available skills by scanning for SKILL.md files.
        
        Scans both system and personal skills directories.
        Personal skills override system skills if they have the same name.
        
        Returns:
            List of skill metadata dicts with 'name' and 'description'
        """
        discovered = []
        
        # First, scan system skills
        system_skills = self._scan_directory(self.skills_dir, skill_type="system")
        discovered.extend(system_skills)
        
        # Then, scan personal skills (can override system skills)
        personal_skills = self._scan_directory(self.personal_skills_dir, skill_type="personal")
        
        # Personal skills override system skills with same name
        for personal_skill in personal_skills:
            # Remove any system skill with same name
            discovered = [s for s in discovered if s['name'] != personal_skill['name']]
            # Add personal skill
            discovered.append(personal_skill)
        
        return discovered
    
    def _scan_directory(self, directory: Path, skill_type: str = "system") -> List[Dict[str, str]]:
        """Scan a directory for skills."""
        found_skills = []
        
        if not directory.exists():
            return found_skills
            
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue
                
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
                
            metadata = self._parse_skill_metadata(skill_file, skill_type)
            if metadata:
                found_skills.append(metadata)
                self.skills_metadata[metadata['name']] = metadata
                
        return found_skills
    
    def _parse_skill_metadata(self, skill_file: Path, skill_type: str = "system") -> Dict[str, Any]:
        """Parse YAML frontmatter from SKILL.md file.
        
        Args:
            skill_file: Path to SKILL.md file
            skill_type: "system" or "personal"
        """
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract YAML frontmatter (between --- markers)
            if not content.startswith('---'):
                return None
                
            parts = content.split('---', 2)
            if len(parts) < 3:
                return None
                
            frontmatter = yaml.safe_load(parts[1])
            markdown_body = parts[2].strip()
            
            # Store the full instructions for later
            skill_name = frontmatter.get('name')
            if skill_name:
                self.skills_instructions[skill_name] = markdown_body
                
            return {
                'name': frontmatter.get('name'),
                'description': frontmatter.get('description'),
                'skill_dir': str(skill_file.parent),
                'skill_type': skill_type,  # Mark as system or personal
                'generated': frontmatter.get('generated', False)  # Auto-generated flag
            }
        except Exception as e:
            print(f"Error parsing {skill_file}: {e}")
            return None
    
    def load_skill_instructions(self, skill_name: str) -> str:
        """Load full instructions for a skill."""
        return self.skills_instructions.get(skill_name, "")
    
    def get_skill_path(self, skill_name: str) -> Path:
        """Get the directory path for a skill."""
        metadata = self.skills_metadata.get(skill_name)
        if metadata:
            return Path(metadata['skill_dir'])
        return None
