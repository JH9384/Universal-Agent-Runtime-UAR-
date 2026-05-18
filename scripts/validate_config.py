#!/usr/bin/env python3
"""
UAR Configuration Validator

Validates .env configuration and provides helpful guidance.
Turns configuration complexity into a strength by:
- Checking required variables
- Detecting common issues
- Providing actionable fixes
- Suggesting optional features
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ConfigValidator:
    """Validates UAR configuration and provides guidance."""

    REQUIRED_VARS = {
        "SECRET_KEY": {
            "description": "Security key for encryption",
            "default_warning": "Using default key - change in production",
            "fix": (
                "Generate a secure key: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            ),
        },
        "API_KEYS": {
            "description": "API authentication keys",
            "default_warning": "No API keys configured - auth disabled",
            "fix": "Add API keys in format: key:user:tier,key2:user2:tier2",
        },
    }

    OPTIONAL_FEATURES = {
        "OLLAMA_HOST": {
            "name": "Ollama AI",
            "description": "Local AI model generation",
            "benefit": "Enable ollama_generate skill for AI analysis",
        },
        "AUTONOMI_PRIVATE_KEY": {
            "name": "Autonomi Storage",
            "description": "Decentralized storage",
            "benefit": "Enable autonomi_upload/download for storage",
        },
        "ALM_SERVICE_URL": {
            "description": "ALM service endpoint",
            "default": "http://localhost:5001/api/v1",
        },
        "ALM_TIMEOUT_SEC": {
            "description": "ALM request timeout in seconds",
            "default": "30",
        },
    }

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.env_vars = self._load_env()
        self.issues: List[Tuple[str, str, str]] = []
        self.warnings: List[Tuple[str, str]] = []
        self.suggestions: List[str] = []

    def _load_env(self) -> Dict[str, str]:
        """Load environment variables from file."""
        if not self.env_file.exists():
            return {}

        env_vars = {}
        with open(self.env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars

    def validate_required(self) -> None:
        """Check required configuration variables."""
        for var, info in self.REQUIRED_VARS.items():
            if var not in self.env_vars:
                self.issues.append(
                    (
                        var,
                        "Missing",
                        f"{info['description']}\nFix: {info['fix']}",
                    )
                )
            elif var == "SECRET_KEY" and self.env_vars[var] in [
                "your-secret-key-here-must-be-changed-in-production",
                "dev-secret-key-change-in-production",
            ]:
                self.warnings.append((var, info["default_warning"]))

    def check_optional_features(self) -> None:
        """Check optional features and suggest benefits."""
        for var, info in self.OPTIONAL_FEATURES.items():
            if var not in self.env_vars:
                self.suggestions.append(
                    f"{info['name']}: {info['description']}\n"
                    f"  → {info['benefit']}\n"
                    f"  → Set {var} to enable"
                )

    def check_common_issues(self) -> None:
        """Check for common configuration mistakes."""
        # Check for deprecated variable names
        deprecated = {
            "ENABLE_METRICS": "METRICS_ENABLED",
            "enable_metrics": "metrics_enabled",
        }

        for old, new in deprecated.items():
            if old in self.env_vars:
                self.issues.append(
                    (
                        old,
                        "Deprecated",
                        f"Variable name changed to {new}\n"
                        f"Fix: Rename {old} to {new}",
                    )
                )

        # Check port ranges
        if "API_PORT" in self.env_vars:
            try:
                port = int(self.env_vars["API_PORT"])
                if port < 1 or port > 65535:
                    self.issues.append(
                        (
                            "API_PORT",
                            "Invalid",
                            (
                                f"Port {port} is out of valid range (1-65535)\n"
                                "Fix: Use a port between 1 and 65535"
                            ),
                        )
                    )
            except ValueError:
                self.issues.append(
                    (
                        "API_PORT",
                        "Invalid",
                        (
                            f"Port must be a number, got '{self.env_vars['API_PORT']}'\n"
                            "Fix: Use a valid port number"
                        ),
                    )
                )

    def validate(self) -> bool:
        """Run all validation checks."""
        print(f"🔍 Validating {self.env_file}...")
        print()

        if not self.env_file.exists():
            print(f"⚠️  {self.env_file} not found")
            print("💡 Copy .env.minimal to .env for a quick start:")
            print("   cp .env.minimal .env")
            return False

        self.validate_required()
        self.check_common_issues()
        self.check_optional_features()

        # Print results
        self._print_results()

        return len(self.issues) == 0

    def _print_results(self) -> None:
        """Print validation results in a user-friendly format."""
        # Issues
        if self.issues:
            print("❌ Issues Found:")
            print()
            for var, severity, message in self.issues:
                print(f"   {severity.upper()}: {var}")
                for line in message.split("\n"):
                    print(f"   {line}")
                print()

        # Warnings
        if self.warnings:
            print("⚠️  Warnings:")
            print()
            for var, message in self.warnings:
                print(f"   {var}: {message}")
            print()

        # Suggestions
        if self.suggestions:
            print("💡 Optional Features (disabled):")
            print()
            for suggestion in self.suggestions:
                for line in suggestion.split("\n"):
                    print(f"   {line}")
                print()

        # Summary
        if not self.issues and not self.warnings:
            print("✅ Configuration is valid!")
        elif not self.issues:
            print("✅ No critical issues, but see warnings above")


def main():
    """Main entry point."""
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    validator = ConfigValidator(env_file)
    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
