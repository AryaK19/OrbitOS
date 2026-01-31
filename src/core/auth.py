"""
Authentication manager for the Remote MCP Control System.
Handles user whitelisting, permission levels, and authorization.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger, AuditLogger


class PermissionLevel(Enum):
    """Permission levels for users."""
    READONLY = "readonly"
    USER = "user"
    ADMIN = "admin"
    
    @classmethod
    def from_string(cls, value: str) -> "PermissionLevel":
        """Convert string to PermissionLevel."""
        for level in cls:
            if level.value == value.lower():
                return level
        return cls.READONLY  # Default to most restrictive


@dataclass
class UserPermissions:
    """Permissions for a specific user."""
    user_id: int
    level: PermissionLevel
    capabilities: Set[str]
    path_restricted: bool
    command_restricted: bool


class AuthManager:
    """
    Authentication and authorization manager.
    Manages user whitelists, permissions, and access control.
    """
    
    # Capability definitions per level
    CAPABILITY_MAP = {
        PermissionLevel.READONLY: {
            'file_read', 'system_info'
        },
        PermissionLevel.USER: {
            'shell_execute', 'file_read', 'file_write',
            'app_launch', 'python_execute', 'system_info'
        },
        PermissionLevel.ADMIN: {
            'shell_execute', 'file_read', 'file_write', 'file_delete',
            'app_launch', 'python_execute', 'system_info',
            'process_manage', 'config_modify'
        }
    }
    
    
    def __init__(
        self,
        whitelist: List[int],
        admin_users: List[int],
        user_users: List[int],
        readonly_users: List[int],
        password: str = None,
        default_permission: str = "user"
    ):
        self.logger = get_logger()
        self.audit = AuditLogger()
        
        self.whitelist = set(whitelist)
        self.password = password
        self.default_permission = PermissionLevel.from_string(default_permission)
        
        # Build user -> permission level mapping
        self.user_levels: Dict[int, PermissionLevel] = {}
        
        for user_id in admin_users:
            self.user_levels[user_id] = PermissionLevel.ADMIN
            self.whitelist.add(user_id)
            
        for user_id in user_users:
            if user_id not in self.user_levels:
                self.user_levels[user_id] = PermissionLevel.USER
            self.whitelist.add(user_id)
            
        for user_id in readonly_users:
            if user_id not in self.user_levels:
                self.user_levels[user_id] = PermissionLevel.READONLY
            self.whitelist.add(user_id)
        
        self.logger.info(f"AuthManager initialized with {len(self.whitelist)} whitelisted users")
    
    def is_whitelisted(self, user_id: int) -> bool:
        """Check if a user is in the whitelist."""
        return user_id in self.whitelist
    
    def verify_password(self, password: str) -> bool:
        """Verify the provided password."""
        return self.password and password == self.password
    
    def get_permission_level(self, user_id: int) -> PermissionLevel:
        """Get the permission level for a user."""
        if user_id not in self.whitelist:
            return PermissionLevel.READONLY
        return self.user_levels.get(user_id, self.default_permission)
    
    def get_user_permissions(self, user_id: int) -> UserPermissions:
        """Get full permission details for a user."""
        level = self.get_permission_level(user_id)
        capabilities = self.CAPABILITY_MAP.get(level, set())
        
        return UserPermissions(
            user_id=user_id,
            level=level,
            capabilities=capabilities,
            path_restricted=(level != PermissionLevel.ADMIN),
            command_restricted=(level != PermissionLevel.ADMIN)
        )
    
    def authorize(
        self,
        user_id: int,
        username: str,
        capability: str
    ) -> tuple[bool, str]:
        """
        Check if a user is authorized to perform an action.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            capability: The capability being requested
            
        Returns:
            Tuple of (is_authorized, error_message)
        """
        # Check whitelist
        if not self.is_whitelisted(user_id):
            self.audit.log_auth_attempt(
                user_id, username, False,
                reason="User not in whitelist"
            )
            self.logger.warning(f"Unauthorized access attempt by {user_id} ({username})")
            return False, "You are not authorized to use this bot."
        
        # Check capability
        permissions = self.get_user_permissions(user_id)
        if capability not in permissions.capabilities:
            self.audit.log_auth_attempt(
                user_id, username, False,
                reason=f"Missing capability: {capability}"
            )
            self.logger.warning(
                f"User {user_id} attempted {capability} without permission"
            )
            return False, f"You don't have permission to: {capability}"
        
        self.audit.log_auth_attempt(user_id, username, True)
        return True, ""
    
    def add_to_whitelist(self, user_id: int, level: PermissionLevel = None):
        """Add a user to the whitelist (runtime only)."""
        self.whitelist.add(user_id)
        if level:
            self.user_levels[user_id] = level
        self.logger.info(f"Added user {user_id} to whitelist with level {level}")
    
    def remove_from_whitelist(self, user_id: int):
        """Remove a user from the whitelist (runtime only)."""
        self.whitelist.discard(user_id)
        self.user_levels.pop(user_id, None)
        self.logger.info(f"Removed user {user_id} from whitelist")
    
    @classmethod
    def from_config(cls, config: dict) -> "AuthManager":
        """Create AuthManager from configuration dictionary."""
        security = config.get('security', {})
        permissions = config.get('permissions', {})
        
        return cls(
            whitelist=security.get('whitelist', []),
            admin_users=permissions.get('admin', []),
            user_users=permissions.get('user', []),
            readonly_users=permissions.get('readonly', []),
            password=security.get('password'),
            default_permission=security.get('default_permission', 'user')
        )
