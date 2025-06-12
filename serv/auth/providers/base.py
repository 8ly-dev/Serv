"""Base provider class for all auth providers."""

from abc import ABC
from typing import Dict, Any

from ..audit.decorators import AuditEnforced


class BaseProvider(AuditEnforced, ABC):
    """Base class for all authentication providers.
    
    Provides common functionality and ensures audit enforcement.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config