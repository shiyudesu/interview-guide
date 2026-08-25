from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from interview_guide.common.runtime import BlockingExecutor

DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$6Gya8uTun/WvcVDZ7N1MvA$"
    "qpX2TxFzuigeoFKN0fLAPIZepgHngDur5BbRQqKKDsI"
)


class PasswordService:
    def __init__(self, executor: BlockingExecutor) -> None:
        self._executor = executor
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    async def hash(self, password: str) -> str:
        return await self._executor.run(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        try:
            return await self._executor.run(self._hasher.verify, password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    async def verify_dummy(self, password: str) -> None:
        await self.verify(DUMMY_PASSWORD_HASH, password)

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
