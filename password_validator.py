#!/usr/bin/env python3
"""
Password validation module with configurable rules and entropy calculation.
Educational implementation - uses simple charset size estimation for entropy.
"""

import json
import math
import re
import string
from typing import Tuple, List
from pathlib import Path


class PasswordValidator:
    """Validates passwords against configurable rules."""
    
    def __init__(self, rules_file: str = 'password_rules.json'):
        self.rules = self._load_rules(rules_file)
    
    @staticmethod
    def _load_rules(rules_file: str) -> dict:
        """Load password rules from JSON file."""
        try:
            rules_path = Path(rules_file)
            if not rules_path.exists():
                raise FileNotFoundError(f"Rules file not found: {rules_file}")
            
            with open(rules_path, 'r') as f:
                rules = json.load(f)
            
            return rules
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {rules_file}: {e}")
        except Exception as e:
            raise Exception(f"Error loading rules: {e}")
    
    def validate(self, password: str) -> Tuple[bool, List[str], float, str]:
        """
        Validate a password against all enabled rules.
        
        Returns:
            Tuple of (is_valid, errors, entropy_bits, strength_indicator)
            - is_valid: True if password passes all rules
            - errors: List of error messages for each failed rule
            - entropy_bits: Estimated entropy in bits
            - strength_indicator: "weak" | "medium" | "strong" | "very_strong"
        """
        errors = []
        
        # Check minimum length
        if len(password) < self.rules.get('min_length', 8):
            min_len = self.rules.get('min_length', 8)
            errors.append(f"Password must be at least {min_len} characters long")
        
        # Check maximum length
        if len(password) > self.rules.get('max_length', 128):
            max_len = self.rules.get('max_length', 128)
            errors.append(f"Password must not exceed {max_len} characters")
        
        # Check for uppercase letters
        if self.rules.get('require_uppercase', False):
            if not re.search(r'[A-Z]', password):
                errors.append("Password must contain at least one uppercase letter")
        
        # Check for lowercase letters
        if self.rules.get('require_lowercase', False):
            if not re.search(r'[a-z]', password):
                errors.append("Password must contain at least one lowercase letter")
        
        # Check for digits
        if self.rules.get('require_digit', False):
            if not re.search(r'\d', password):
                errors.append("Password must contain at least one digit")
        
        # Check for special characters
        if self.rules.get('require_special', False):
            if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
                errors.append("Password must contain at least one special character")
        
        # Check for forbidden patterns (case-insensitive)
        forbidden = self.rules.get('forbidden_patterns', [])
        password_lower = password.lower()
        for pattern in forbidden:
            if pattern.lower() in password_lower:
                errors.append(f"Password contains forbidden pattern: '{pattern}'")
        
        # Calculate entropy
        entropy_bits = self._calculate_entropy(password)
        strength = self._get_strength_indicator(entropy_bits)
        
        is_valid = len(errors) == 0
        
        return is_valid, errors, entropy_bits, strength
    
    @staticmethod
    def _calculate_entropy(password: str) -> float:
        """
        Calculate password entropy in bits.
        
        Uses character set size estimation:
        - lowercase: 26
        - uppercase: 26
        - digits: 10
        - special: ~32
        
        Formula: entropy = length * log2(charset_size)
        """
        charset_size = 0
        
        # Detect character types present in password
        if re.search(r'[a-z]', password):
            charset_size += 26
        if re.search(r'[A-Z]', password):
            charset_size += 26
        if re.search(r'\d', password):
            charset_size += 10
        if re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
            charset_size += 32
        
        # If no characters detected (shouldn't happen), use minimum
        if charset_size == 0:
            charset_size = 1
        
        # entropy = length * log2(charset_size)
        entropy = len(password) * math.log2(charset_size)
        
        return entropy
    
    @staticmethod
    def _get_strength_indicator(entropy_bits: float) -> str:
        """
        Categorize password strength based on entropy.
        
        - weak: < 28 bits
        - medium: 28-35 bits
        - strong: 36-59 bits
        - very_strong: 60+ bits
        """
        if entropy_bits < 28:
            return "weak"
        elif entropy_bits < 36:
            return "medium"
        elif entropy_bits < 60:
            return "strong"
        else:
            return "very_strong"


def validate_password(password: str, 
                     rules_file: str = 'password_rules.json') -> Tuple[bool, List[str], float, str]:
    """
    Convenience function to validate a password.
    
    Args:
        password: Password string to validate
        rules_file: Path to password rules JSON file
    
    Returns:
        Tuple of (is_valid, errors, entropy_bits, strength_indicator)
    """
    validator = PasswordValidator(rules_file)
    return validator.validate(password)


if __name__ == '__main__':
    # Simple test
    test_passwords = [
        'abc',
        'password123',
        'MyPass123',
        'SuperSecurePassword2024!',
    ]
    
    print("Password Validation Test\n")
    print("=" * 70)
    
    for pwd in test_passwords:
        is_valid, errors, entropy, strength = validate_password(pwd)
        
        print(f"\nPassword: '{pwd}'")
        print(f"Valid: {is_valid}")
        print(f"Entropy: {entropy:.2f} bits ({strength})")
        
        if errors:
            print("Errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✓ Passes all rules")
