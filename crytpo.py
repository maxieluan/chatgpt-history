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

        """Generate a random salt value."""
        charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+=<>?/"
        salt = ''.join(secrets.choice(charset) for _ in range(int(length)))
        return salt
    
    @classmethod
    def generate_strong_key(cls, length=32):
        """Generate a strong encryption key."""
        charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+=<>?/"
        key = ''.join(secrets.choice(charset) for _ in range(int(length)))
        return key

import ctypes
import sys

if sys.platform == 'win32':
    libc = ctypes.cdll.msvcrt
elif sys.platform == 'darwin':
    libc = ctypes.cdll.LoadLibrary('libSystem.dylib')
else:
    libc = ctypes.cdll.LoadLibrary('libc.so.6')

class SecureString:
    def __init__(self, value):
        self._buffer = ctypes.create_string_buffer(str(value).encode())
        self._is_wiped = False

    def __str__(self):
        return str(self._buffer.value)

    def wipe(self):
        if not self._is_wiped:
            libc.memset(self._buffer, 0, len(self._buffer))
            self._is_wiped = True
    
## main
if __name__ == '__main__':
    password = SecureString('password')
    print(str(password))

    password.wipe()

    print(str(password))