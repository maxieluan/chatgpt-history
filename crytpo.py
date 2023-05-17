from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets, base64

class EncryptionWrapper:
    def __init__(self, password, salt):
        self.password = password
        self.salt = salt
        self.key = self._derive_key()

    def _derive_key(self):
        salt = self.salt.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # Adjust the number of iterations as per your requirements
        )
        return kdf.derive(self.password.encode('utf-8'))

    def encrypt(self, plaintext):
        base64_key = base64.urlsafe_b64encode(self.key)
        cipher_suite = Fernet(base64_key)
        ciphertext = cipher_suite.encrypt(plaintext.encode('utf-8'))
        return ciphertext

    def decrypt(self, ciphertext):        
        base64_key = base64.urlsafe_b64encode(self.key)
        cipher_suite = Fernet(base64_key)
        plaintext = cipher_suite.decrypt(ciphertext).decode('utf-8')
        return plaintext

    @classmethod
    def generate_salt(cls, length=16):
        print(type(length))

        """Generate a random salt value."""
        charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+=<>?/"
        salt = ''.join(secrets.choice(charset) for _ in range(int(length)))
        return salt