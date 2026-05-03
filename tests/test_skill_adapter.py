from pathlib import Path
from uar.skills.adapter import parse_skill_md, convert_to_template


def test_parse_basic_skill(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("name | Test Skill\ndescription | A test skill\n\nTrigger:\n- test\n")

    parsed = parse_skill_md(skill_file)

    assert parsed["name"] == "Test Skill"
    assert "test" in parsed["trigger"].lower()


def test_convert_template():
    skill = {
        "name": "Example",
        "description": "Example skill",
        "trigger": "",
        "raw": "",
    }

    template = convert_to_template(skill)

    assert template["id"] == "example"
    assert template["planner"] == "llm"
