"""
Message Encryption Module
Handles symmetric encryption of chat messages using AES-CBC
"""

import base64
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class MessageEncryption:
    """Encrypt/decrypt messages using AES-256-CBC"""
    
    @staticmethod
    def encrypt_message(plaintext, key):
        """
        Encrypt message using AES-256-CBC
        key: 128+ bit key (bytes)
        Returns: base64-encoded IV + ciphertext concatenated
        """
        # Generate random 128-bit IV
        iv = secrets.token_bytes(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Pad plaintext to AES block size (16 bytes) using PKCS7
        plaintext_bytes = plaintext.encode('utf-8')
        padding_length = 16 - (len(plaintext_bytes) % 16)
        plaintext_padded = plaintext_bytes + bytes([padding_length] * padding_length)
        
        # Encrypt
        ciphertext = encryptor.update(plaintext_padded) + encryptor.finalize()
        
        # Return: IV + ciphertext, both base64 encoded
        combined = iv + ciphertext
        return base64.b64encode(combined).decode('utf-8')
    
    @staticmethod
    def decrypt_message(encrypted_b64, key):
        """
        Decrypt message using AES-256-CBC
        encrypted_b64: base64-encoded IV + ciphertext
        key: 128+ bit key (bytes)
        Returns: plaintext string
        """
        try:
            # Decode from base64
            combined = base64.b64decode(encrypted_b64)
            
            # Extract IV (first 16 bytes) and ciphertext (rest)
            iv = combined[:16]
            ciphertext = combined[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            plaintext_padded = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove PKCS7 padding
            padding_length = plaintext_padded[-1]
            plaintext = plaintext_padded[:-padding_length]
            
            return plaintext.decode('utf-8')
        except Exception as e:
            return f"[DECRYPTION ERROR: {str(e)}]"
