"""
Asymmetric Encryption Module
Handles RSA key generation and encryption for symmetric key exchange
"""

import os
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend


class AsymmetricCrypto:
    """Manage RSA keypairs and asymmetric encryption"""
    
    @staticmethod
    def generate_keypair(key_size=2048):
        """
        Generate RSA keypair (2048-bit, suitable for key exchange)
        Returns: (private_key, public_key) as cryptography objects
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        return private_key, public_key
    
    @staticmethod
    def save_keypair(username, private_key, public_key, base_dir='users'):
        """
        Save keypair to files: username.priv and username.pub
        Files contain PEM-encoded keys
        """
        os.makedirs(base_dir, exist_ok=True)
        
        # Save private key (PEM format)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_file = os.path.join(base_dir, f"{username}.priv")
        with open(private_file, 'wb') as f:
            f.write(private_pem)
        
        # Save public key (PEM format)
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_file = os.path.join(base_dir, f"{username}.pub")
        with open(public_file, 'wb') as f:
            f.write(public_pem)
        
        return private_file, public_file
    
    @staticmethod
    def load_keypair(username, base_dir='users'):
        """
        Load keypair from files: username.priv and username.pub
        Returns: (private_key, public_key) as cryptography objects or (None, None)
        """
        private_file = os.path.join(base_dir, f"{username}.priv")
        public_file = os.path.join(base_dir, f"{username}.pub")
        
        if not os.path.exists(private_file) or not os.path.exists(public_file):
            return None, None
        
        try:
            # Load private key
            with open(private_file, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Load public key
            with open(public_file, 'rb') as f:
                public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )
            
            return private_key, public_key
        except Exception as e:
            print(f"Error loading keypair: {e}")
            return None, None
    
    @staticmethod
    def serialize_public_key(public_key):
        """
        Serialize public key to base64 string for transmission
        """
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(public_pem).decode('utf-8')
    
    @staticmethod
    def deserialize_public_key(public_key_b64):
        """
        Deserialize public key from base64 string
        Returns: public_key as cryptography object
        """
        try:
            public_pem = base64.b64decode(public_key_b64)
            public_key = serialization.load_pem_public_key(
                public_pem,
                backend=default_backend()
            )
            return public_key
        except Exception as e:
            print(f"Error deserializing public key: {e}")
            return None
    
    @staticmethod
    def encrypt_with_public_key(plaintext, public_key):
        """
        Encrypt plaintext (bytes) with RSA public key
        Returns: ciphertext as bytes
        """
        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return ciphertext
    
    @staticmethod
    def decrypt_with_private_key(ciphertext, private_key):
        """
        Decrypt ciphertext (bytes) with RSA private key
        Returns: plaintext as bytes
        """
        try:
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return plaintext
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    @staticmethod
    def sign_message(message, private_key):
        """
        Sign a message using RSA-PSS with SHA256
        message: bytes or string
        private_key: RSA private key object
        Returns: signature as bytes
        """
        if isinstance(message, str):
            message = message.encode('utf-8')
        
        try:
            signature = private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return signature
        except Exception as e:
            print(f"Signing error: {e}")
            return None
    
    @staticmethod
    def verify_signature(message, signature, public_key):
        """
        Verify a message signature using RSA-PSS with SHA256
        message: bytes or string
        signature: bytes
        public_key: RSA public key object
        Returns: True if valid, False if invalid
        """
        if isinstance(message, str):
            message = message.encode('utf-8')
        
        try:
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            return False
