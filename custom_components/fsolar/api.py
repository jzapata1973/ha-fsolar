"""Async client for the Fsolar cloud API."""

from __future__ import annotations

import asyncio
import base64
import re
import time
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientResponseError, ClientSession
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .const import API_BASE_URL, SOURCE_PRIORITY_FIELD, WEB_BASE_URL


class FsolarError(Exception):
    """Base Fsolar API error."""


class FsolarAuthenticationError(FsolarError):
    """Authentication failed."""


class FsolarCommandError(FsolarError):
    """A device command failed or could not be verified."""


@dataclass(frozen=True, slots=True)
class FsolarInverter:
    """A supported Fsolar inverter."""

    serial: str
    name: str
    model: str | None = None


class FsolarApi:
    """Small client covering authentication, discovery and cspri control."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._public_key = None

    async def async_login(self) -> None:
        """Authenticate and retain the short-lived API token."""
        encrypted_password = await self._async_encrypt_password()
        payload = {
            "userName": self._username,
            "password": encrypted_password,
            "version": "1.0",
        }
        try:
            data = await self._async_request(
                "/userlogin", payload, authenticated=False
            )
        except FsolarError as err:
            message = str(err).lower()
            if any(
                marker in message
                for marker in (
                    "contraseña",
                    "password",
                    "usuario",
                    "username",
                    "account",
                    "cuenta",
                )
            ):
                raise FsolarAuthenticationError(str(err)) from err
            raise
        token = (data.get("data") or {}).get("token")
        if not token:
            raise FsolarAuthenticationError(
                data.get("message") or "Fsolar login failed"
            )
        self._token = token

    async def async_close_session(self) -> None:
        """Forget the current cloud session token."""
        self._token = None

    async def async_list_inverters(self) -> list[FsolarInverter]:
        """Return account devices that expose inverter settings."""
        data = await self._async_authed_request(
            "/device/list_device_all_type",
            {
                "pageNum": 1,
                "pageSize": 100,
                "deviceSn": "",
                "status": "",
                "sampleFlag": "",
                "oscFlag": "",
            },
        )
        devices = (data.get("data") or {}).get("dataList") or []
        inverters: list[FsolarInverter] = []
        for device in devices:
            serial = str(device.get("deviceSn") or "")
            if not serial:
                continue
            try:
                await self.async_get_source_priority(serial)
            except FsolarError:
                continue
            alias = (
                device.get("alias")
                or device.get("deviceName")
                or f"Inverter {serial[-4:]}"
            )
            model = device.get("deviceModel") or device.get("productModel")
            inverters.append(
                FsolarInverter(serial=serial, name=str(alias), model=model)
            )
        return inverters

    async def async_get_source_priority(self, serial: str) -> int:
        """Read Source Priority Charge (cspri) from an inverter."""
        data = await self._async_authed_request(
            "/deviceCommand/get_command_setting_original_value",
            {"deviceSn": serial, "oldVersion": 1},
        )
        values = data.get("data") or {}
        raw_value = values.get(SOURCE_PRIORITY_FIELD, values.get("cSPri"))
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as err:
            raise FsolarError(f"Device {serial[-4:]} did not return cspri") from err
        if value not in (1, 2, 3):
            raise FsolarError(
                f"Device {serial[-4:]} returned unsupported cspri={value}"
            )
        return value

    async def async_set_source_priority(self, serial: str, value: int) -> None:
        """Set cspri, wait for completion, and verify by reading it back."""
        if value not in (1, 2, 3):
            raise ValueError("Source Priority Charge must be 1, 2 or 3")

        payload = {
            "deviceSn": serial,
            "timeZone": "America/Santiago",
            "timestamp": int(time.time() * 1000),
            "oldVersion": 1,
            "useType": 3,
            "groupId": 0,
            "deviceCommands": [
                {
                    "dataHandlerType": 0,
                    "fieldName": SOURCE_PRIORITY_FIELD,
                    "groupId": 0,
                    "paramType": 1,
                    "useType": 3,
                    "fieldValue": value,
                }
            ],
            "realContentParam": [SOURCE_PRIORITY_FIELD],
        }
        response = await self._async_authed_request(
            "/deviceCommand/create_setting_command", payload
        )
        command_data = response.get("data")
        if isinstance(command_data, list):
            command_data = command_data[0] if command_data else {}
        command_id = str((command_data or {}).get("id") or "")
        if not command_id:
            raise FsolarCommandError("Fsolar did not return a command id")

        await self._async_wait_for_command(command_id, serial, value)
        actual = await self.async_get_source_priority(serial)
        if actual != value:
            raise FsolarCommandError(
                f"Verification failed for {serial[-4:]}: "
                f"expected {value}, received {actual}"
            )

    async def _async_wait_for_command(
        self, command_id: str, serial: str, expected: int
    ) -> None:
        """Wait until the setting reads back or Fsolar reports failure."""
        for _attempt in range(10):
            await asyncio.sleep(2)
            if await self.async_get_source_priority(serial) == expected:
                return
            response = await self._async_authed_request(
                f"/deviceCommand/get_device_command_detail/{command_id}",
                {"id": command_id},
            )
            detail = response.get("data") or {}
            status = str(detail.get("status") or "").upper()
            result = str(detail.get("result") or "").upper()
            if status in {"FAILED", "FAIL", "4", "5"} or result in {
                "FAILED",
                "FAIL",
                "0",
            }:
                raise FsolarCommandError(
                    detail.get("message") or f"Fsolar command {command_id} failed"
                )
        raise FsolarCommandError(f"Fsolar command {command_id} timed out")

    async def _async_authed_request(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Make an authenticated request, refreshing once if needed."""
        if not self._token:
            await self.async_login()
        try:
            return await self._async_request(path, payload)
        except FsolarAuthenticationError:
            self._token = None
            await self.async_login()
            return await self._async_request(path, payload)

    async def _async_request(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "lang": "es_ES",
            "source": "WEB",
        }
        if authenticated:
            if not self._token:
                raise FsolarAuthenticationError("Missing Fsolar token")
            headers["Authorization"] = self._token

        try:
            async with self._session.post(
                f"{API_BASE_URL}{path}",
                json=payload,
                headers=headers,
                timeout=30,
            ) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise FsolarAuthenticationError("Fsolar session expired") from err
            raise FsolarError(f"Fsolar HTTP error {err.status}") from err
        except Exception as err:
            raise FsolarError(f"Fsolar request failed: {err}") from err

        code = data.get("code")
        if code not in (None, 0, 200, "0", "200"):
            message = str(data.get("message") or f"API code {code}")
            if "login" in message.lower() or "token" in message.lower():
                raise FsolarAuthenticationError(message)
            raise FsolarError(message)
        return data

    async def _async_encrypt_password(self) -> str:
        """Fetch the web public key and encrypt the account password."""
        if self._public_key is None:
            async with self._session.get(f"{WEB_BASE_URL}/", timeout=30) as response:
                response.raise_for_status()
                html = await response.text()
            asset_match = re.search(r"assets/index\.[A-Za-z0-9_-]+\.js", html)
            if not asset_match:
                raise FsolarAuthenticationError(
                    "Could not locate the Fsolar web application"
                )
            async with self._session.get(
                f"{WEB_BASE_URL}/{asset_match.group(0)}", timeout=30
            ) as response:
                response.raise_for_status()
                javascript = await response.text()
            key_match = re.search(
                r"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A"
                r"[A-Za-z0-9+/]+IDAQAB",
                javascript,
            )
            if not key_match:
                login_chunk_match = re.search(
                    r'path:"/login".{0,400}?'
                    r'import\("\./([^"]+\.js)"\)',
                    javascript,
                    re.DOTALL,
                )
                if login_chunk_match:
                    async with self._session.get(
                        f"{WEB_BASE_URL}/assets/{login_chunk_match.group(1)}",
                        timeout=30,
                    ) as response:
                        response.raise_for_status()
                        login_javascript = await response.text()
                    key_match = re.search(
                        r"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A"
                        r"[A-Za-z0-9+/]+IDAQAB",
                        login_javascript,
                    )
            if not key_match:
                raise FsolarAuthenticationError(
                    "Could not find the Fsolar login public key"
                )
            try:
                der_key = base64.b64decode(key_match.group(0))
                self._public_key = serialization.load_der_public_key(der_key)
            except (ValueError, TypeError) as err:
                raise FsolarAuthenticationError(
                    "Invalid Fsolar login public key"
                ) from err

        encrypted = self._public_key.encrypt(
            self._password.encode(),
            padding.PKCS1v15(),
        )
        return base64.b64encode(encrypted).decode()
