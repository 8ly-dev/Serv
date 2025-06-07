"""
Ommi models for authentication data storage.

This module defines the database models used by the bundled authentication
implementations, following Ommi's model patterns and best practices.
"""

from dataclasses import dataclass
from typing import Annotated

from ommi import Key, ommi_model
from ommi.models.collections import ModelCollection

# Create auth collection for organizing authentication models
auth_collection = ModelCollection()


@ommi_model(collection=auth_collection)
@dataclass
class SessionModel:
    """Session storage model for Ommi."""

    session_id: str
    user_id: str
    user_context: str  # JSON string
    device_fingerprint: str
    created_at: str  # ISO format datetime
    expires_at: str  # ISO format datetime
    last_activity: str  # ISO format datetime
    metadata: str = "{}"  # JSON string
    id: Annotated[int, Key] = None  # Auto-generated primary key


@ommi_model(collection=auth_collection)
@dataclass
class CredentialModel:
    """Credential storage model for Ommi."""

    credential_id: str
    user_id: str
    credential_type: str
    credential_data: str  # JSON string
    created_at: str  # ISO format datetime
    updated_at: str  # ISO format datetime
    is_active: bool = True
    metadata: str = "{}"  # JSON string
    id: Annotated[int, Key] = None  # Auto-generated primary key


@ommi_model(collection=auth_collection)
@dataclass
class RateLimitModel:
    """Rate limit tracking model for Ommi."""

    identifier: str
    action: str
    request_time: str  # ISO format datetime
    metadata: str = "{}"  # JSON string
    id: Annotated[int, Key] = None  # Auto-generated primary key
