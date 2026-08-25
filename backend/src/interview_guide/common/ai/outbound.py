from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpcore
import httpx

from interview_guide.common.config.settings import Settings
from interview_guide.common.errors import BusinessException, ErrorCode
from interview_guide.common.runtime import BlockingExecutor


class AddressResolver(Protocol):
    async def resolve(self, host: str, port: int) -> tuple[str, ...]: ...


class SocketAddressResolver:
    def __init__(self, executor: BlockingExecutor) -> None:
        self._executor = executor

    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        try:
            return await self._executor.run(resolve_socket_addresses, host, port)
        except socket.gaierror as error:
            raise BusinessException(
                ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                f"Provider 地址无法解析: {host}",
            ) from error


def resolve_socket_addresses(host: str, port: int) -> tuple[str, ...]:
    records = socket.getaddrinfo(
        host,
        port,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )
    addresses = {str(record[4][0]) for record in records}
    return tuple(sorted(addresses))


def normalized_host(host: str) -> str:
    try:
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise BusinessException(
            ErrorCode.PROVIDER_OUTBOUND_REJECTED,
            "Provider 地址包含无效主机名",
        ) from error


def parse_networks(
    values: Iterable[str],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as error:
            raise ValueError(f"无效 Provider 出站 CIDR: {value}") from error
    return tuple(networks)


@dataclass(frozen=True)
class ValidatedOutboundUrl:
    url: str
    host: str
    port: int


class ProviderOutboundPolicy:
    def __init__(
        self,
        resolver: AddressResolver,
        *,
        allowed_hosts: Iterable[str] = (),
        allowed_networks: Iterable[str] = (),
    ) -> None:
        self._resolver = resolver
        self._allowed_hosts = frozenset(
            normalized_host(value.strip()) for value in allowed_hosts if value.strip()
        )
        self._allowed_networks = parse_networks(allowed_networks)

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        executor: BlockingExecutor,
    ) -> ProviderOutboundPolicy:
        return cls(
            SocketAddressResolver(executor),
            allowed_hosts=settings.provider_outbound_allowed_host_list,
            allowed_networks=settings.provider_outbound_allowed_network_list,
        )

    async def validate_http_url(self, url: str) -> ValidatedOutboundUrl:
        return await self._validate_url(url, secure_scheme="https", insecure_scheme="http")

    async def validate_websocket_url(self, url: str) -> ValidatedOutboundUrl:
        return await self._validate_url(url, secure_scheme="wss", insecure_scheme="ws")

    def guarded_http_transport(
        self,
        *,
        limits: httpx.Limits | None = None,
    ) -> httpx.AsyncHTTPTransport:
        transport = httpx.AsyncHTTPTransport(
            trust_env=False,
            limits=limits or httpx.Limits(),
            retries=0,
        )
        pool = transport._pool
        pool._network_backend = GuardedNetworkBackend(self)
        return transport

    async def resolve_for_connection(self, host: str, port: int) -> tuple[str, ...]:
        normalized = normalized_host(host)
        literal = parse_ip_address(normalized)
        addresses = (
            (str(literal),)
            if literal is not None
            else await self._resolver.resolve(normalized, port)
        )
        if not addresses:
            raise BusinessException(
                ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                f"Provider 地址没有可用 IP: {normalized}",
            )
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as error:
                raise BusinessException(
                    ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                    f"Provider 地址解析结果无效: {normalized}",
                ) from error
            if not self._address_allowed(address):
                raise BusinessException(
                    ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                    f"Provider 地址指向禁止访问的网络: {normalized}",
                )
        return tuple(dict.fromkeys(addresses))

    async def _validate_url(
        self,
        url: str,
        *,
        secure_scheme: str,
        insecure_scheme: str,
    ) -> ValidatedOutboundUrl:
        normalized_url, parsed = normalize_outbound_url(url)
        if parsed.scheme not in {secure_scheme, insecure_scheme}:
            raise BusinessException(
                ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                f"Provider 地址只允许 {secure_scheme} 协议",
            )
        assert parsed.hostname is not None
        host = normalized_host(parsed.hostname)
        literal = parse_ip_address(host)
        if parsed.scheme == insecure_scheme and not (
            host in self._allowed_hosts
            or (literal is not None and self._address_in_allowed_network(literal))
        ):
            raise BusinessException(
                ErrorCode.PROVIDER_OUTBOUND_REJECTED,
                f"Provider 地址只允许 {secure_scheme}；HTTP/WS 仅限部署者 allowlist",
            )
        port = parsed.port or (443 if parsed.scheme == secure_scheme else 80)
        await self.resolve_for_connection(host, port)
        return ValidatedOutboundUrl(normalized_url, host, port)

    def _address_allowed(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return address.is_global or self._address_in_allowed_network(address)

    def _address_in_allowed_network(
        self,
        address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    ) -> bool:
        return any(
            address.version == network.version and address in network
            for network in self._allowed_networks
        )


class GuardedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        policy: ProviderOutboundPolicy,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self._policy = policy
        self._backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await self._policy.resolve_for_connection(host, port)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as error:
                last_error = error
        assert last_error is not None
        raise last_error

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


def parse_ip_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def normalize_outbound_url(url: str) -> tuple[str, SplitResult]:
    value = url.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise BusinessException(
            ErrorCode.PROVIDER_OUTBOUND_REJECTED,
            "Provider 地址格式无效",
        ) from error
    if not parsed.scheme or parsed.hostname is None:
        raise BusinessException(
            ErrorCode.PROVIDER_OUTBOUND_REJECTED,
            "Provider 地址必须包含协议和主机名",
        )
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise BusinessException(
            ErrorCode.PROVIDER_OUTBOUND_REJECTED,
            "Provider 地址不能包含用户信息或 fragment",
        )
    host = normalized_host(parsed.hostname)
    bracketed_host = f"[{host}]" if parse_ip_address(host) and ":" in host else host
    default_port = (parsed.scheme in {"https", "wss"} and port == 443) or (
        parsed.scheme in {"http", "ws"} and port == 80
    )
    authority = bracketed_host if port is None or default_port else f"{bracketed_host}:{port}"
    path = parsed.path.rstrip("/")
    normalized = urlunsplit((parsed.scheme.lower(), authority, path, parsed.query, ""))
    return normalized, urlsplit(normalized)
