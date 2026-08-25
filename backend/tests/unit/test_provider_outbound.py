from __future__ import annotations

from collections.abc import Iterable

import httpcore
import pytest

from interview_guide.common.ai.outbound import (
    GuardedNetworkBackend,
    ProviderOutboundPolicy,
    normalize_outbound_url,
)
from interview_guide.common.errors import BusinessException


class StaticResolver:
    def __init__(self, addresses: tuple[str, ...]) -> None:
        self.addresses = addresses
        self.requests: list[tuple[str, int]] = []

    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        self.requests.append((host, port))
        return self.addresses


class RecordingNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.connections: list[tuple[str, int]] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del timeout, local_address, socket_options
        self.connections.append((host, port))
        return object()  # type: ignore[return-value]

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise AssertionError("unix sockets are not used")

    async def sleep(self, seconds: float) -> None:
        del seconds


@pytest.mark.asyncio
async def test_public_https_is_allowed_and_normalized() -> None:
    resolver = StaticResolver(("93.184.216.34",))
    policy = ProviderOutboundPolicy(resolver)

    result = await policy.validate_http_url(" HTTPS://Example.COM:443/v1/ ")

    assert result.url == "https://example.com/v1"
    assert resolver.requests == [("example.com", 443)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    (
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "192.168.1.10",
        "::1",
        "fc00::1",
    ),
)
async def test_private_and_metadata_addresses_are_rejected(address: str) -> None:
    policy = ProviderOutboundPolicy(StaticResolver((address,)))

    with pytest.raises(BusinessException, match="禁止访问的网络"):
        await policy.validate_http_url("https://provider.example/v1")


@pytest.mark.asyncio
async def test_any_private_dns_answer_rejects_the_whole_host() -> None:
    policy = ProviderOutboundPolicy(StaticResolver(("93.184.216.34", "169.254.169.254")))

    with pytest.raises(BusinessException, match="禁止访问的网络"):
        await policy.validate_http_url("https://provider.example/v1")


@pytest.mark.asyncio
async def test_plain_http_requires_host_and_network_allowlists() -> None:
    resolver = StaticResolver(("192.168.10.20",))
    missing_network = ProviderOutboundPolicy(
        resolver,
        allowed_hosts=("lmstudio.internal",),
    )
    with pytest.raises(BusinessException, match="禁止访问的网络"):
        await missing_network.validate_http_url("http://lmstudio.internal:1234/v1")

    allowed = ProviderOutboundPolicy(
        resolver,
        allowed_hosts=("lmstudio.internal",),
        allowed_networks=("192.168.10.0/24",),
    )
    result = await allowed.validate_http_url("http://lmstudio.internal:1234/v1")
    assert result.url == "http://lmstudio.internal:1234/v1"


@pytest.mark.asyncio
async def test_http_public_host_is_rejected_without_explicit_allowlist() -> None:
    policy = ProviderOutboundPolicy(StaticResolver(("93.184.216.34",)))

    with pytest.raises(BusinessException, match="只允许 https"):
        await policy.validate_http_url("http://provider.example/v1")


@pytest.mark.asyncio
async def test_credentials_and_fragments_are_rejected() -> None:
    policy = ProviderOutboundPolicy(StaticResolver(("93.184.216.34",)))

    for value in (
        "https://user:password@provider.example/v1",
        "https://provider.example/v1#fragment",
    ):
        with pytest.raises(BusinessException, match="用户信息或 fragment"):
            await policy.validate_http_url(value)


@pytest.mark.asyncio
async def test_connection_backend_revalidates_dns_before_connecting() -> None:
    resolver = StaticResolver(("169.254.169.254",))
    policy = ProviderOutboundPolicy(resolver)
    delegate = RecordingNetworkBackend()
    backend = GuardedNetworkBackend(policy, delegate)

    with pytest.raises(BusinessException, match="禁止访问的网络"):
        await backend.connect_tcp("provider.example", 443)

    assert delegate.connections == []


def test_url_identity_ignores_case_default_port_and_trailing_slash() -> None:
    first, _ = normalize_outbound_url("HTTPS://Provider.Example:443/v1/")
    second, _ = normalize_outbound_url("https://provider.example/v1")

    assert first == second
