"""Example PyPI package for a UAR skill plugin.

Install with: pip install -e .

The entry point ``uar.skills`` tells UAR's plugin loader where to find
the skill module.
"""

from setuptools import setup

setup(
    name="uar-skills-example",
    version="1.0.0",
    description="Example UAR skill plugin",
    py_modules=["uar_skills_example"],
    install_requires=[],
    entry_points={
        "uar.skills": [
            "example = uar_skills_example",
        ],
    },
)
