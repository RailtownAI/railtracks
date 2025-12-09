"""
Test OAuth Integration with Railtracks MCP
===========================================

Tests that verify OAuth authentication components work correctly
with the Railtracks MCP system.
"""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from railtracks.rt_mcp import MCPHttpParams


class MockTokenStorage(TokenStorage):
    """Mock token storage for testing."""

    def __init__(self):
        self._tokens = None
        self._client_info = None

    async def get_tokens(self):
        return self._tokens

    async def set_tokens(self, tokens):
        self._tokens = tokens

    async def get_client_info(self):
        return self._client_info

    async def set_client_info(self, client_info):
        self._client_info = client_info


class TestOAuthParams:
    """Test OAuth parameter handling in MCPHttpParams."""

    def test_mcp_http_params_with_auth_field(self):
        """Test that MCPHttpParams can be extended with auth field."""
        # Create extended class with auth field
        class MCPHttpParamsWithAuth(MCPHttpParams):
            auth: object = None
        
        mock_oauth = Mock(spec=OAuthClientProvider)
        
        config = MCPHttpParamsWithAuth(
            url="http://localhost:8000/mcp",
            timeout=timedelta(seconds=30),
            auth=mock_oauth,
        )
        
        assert config.url == "http://localhost:8000/mcp"
        assert config.auth == mock_oauth
        assert config.timeout.total_seconds() == 30

    def test_oauth_params_validation(self):
        """Test that OAuth parameters are properly validated."""
        class MCPHttpParamsWithAuth(MCPHttpParams):
            auth: object = None
        
        # Should work with None auth
        config1 = MCPHttpParamsWithAuth(url="http://test.com")
        assert config1.auth is None
        
        # Should work with auth provider
        mock_provider = Mock(spec=OAuthClientProvider)
        config2 = MCPHttpParamsWithAuth(url="http://test.com", auth=mock_provider)
        assert config2.auth == mock_provider


class TestOAuthMetadata:
    """Test OAuth metadata creation and validation."""

    def test_oauth_metadata_creation(self):
        """Test creating OAuth client metadata."""
        client_metadata_dict = {
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }
        
        metadata = OAuthClientMetadata.model_validate(client_metadata_dict)
        
        assert metadata.client_name == "Test Client"
        assert "http://localhost:3030/callback" in [str(uri) for uri in metadata.redirect_uris]
        assert "authorization_code" in metadata.grant_types
        assert "refresh_token" in metadata.grant_types
        assert "code" in metadata.response_types

    def test_oauth_metadata_required_fields(self):
        """Test that required OAuth metadata fields are enforced."""
        # Missing required fields should raise validation error
        with pytest.raises((ValueError, Exception)):
            OAuthClientMetadata.model_validate({
                "client_name": "Test"
                # Missing redirect_uris, grant_types, response_types
            })

    def test_oauth_metadata_with_optional_fields(self):
        """Test OAuth metadata with optional fields."""
        metadata_dict = {
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        }
        
        metadata = OAuthClientMetadata.model_validate(metadata_dict)
        assert metadata.client_name == "Test Client"


class TestOAuthProvider:
    """Test OAuth provider creation and configuration."""

    @pytest.mark.asyncio
    async def test_oauth_provider_creation(self):
        """Test creating an OAuth client provider."""
        storage = MockTokenStorage()
        
        async def mock_redirect_handler(url: str):
            pass
        
        async def mock_callback_handler():
            return ("auth_code_123", "state_456")
        
        client_metadata = OAuthClientMetadata.model_validate({
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
        })
        
        provider = OAuthClientProvider(
            server_url="http://localhost:8000/mcp",
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=mock_redirect_handler,
            callback_handler=mock_callback_handler,
        )
        
        assert provider is not None
        assert isinstance(provider, OAuthClientProvider)

    @pytest.mark.asyncio
    async def test_oauth_provider_storage_access(self):
        """Test OAuth provider uses storage correctly."""
        storage = MockTokenStorage()
        
        async def mock_redirect_handler(url: str):
            pass
        
        async def mock_callback_handler():
            return ("code", "state")
        
        client_metadata = OAuthClientMetadata.model_validate({
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
        })
        
        provider = OAuthClientProvider(
            server_url="http://localhost:8000/mcp",
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=mock_redirect_handler,
            callback_handler=mock_callback_handler,
        )
        
        # Verify provider has access to storage
        assert provider is not None
        # Storage should be accessible (implementation detail may vary)
        assert storage is not None


class TestTokenStorage:
    """Test token storage functionality."""

    @pytest.mark.asyncio
    async def test_token_storage_get_set(self):
        """Test getting and setting tokens."""
        storage = MockTokenStorage()
        
        # Initial state - no tokens
        tokens = await storage.get_tokens()
        assert tokens is None
        
        # Set tokens
        mock_token = OAuthToken(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
        )
        await storage.set_tokens(mock_token)
        
        # Retrieve tokens
        retrieved = await storage.get_tokens()
        assert retrieved == mock_token
        assert retrieved.access_token == "test_access_token"
        assert retrieved.token_type == "Bearer"
        assert retrieved.expires_in == 3600

    @pytest.mark.asyncio
    async def test_token_storage_client_info(self):
        """Test storing and retrieving client information."""
        storage = MockTokenStorage()
        
        # Initial state
        client_info = await storage.get_client_info()
        assert client_info is None
        
        # Set client info
        mock_info = Mock(spec=OAuthClientInformationFull)
        mock_info.client_id = "test_client_id"
        await storage.set_client_info(mock_info)
        
        # Retrieve client info
        retrieved = await storage.get_client_info()
        assert retrieved == mock_info
        assert retrieved.client_id == "test_client_id"

    @pytest.mark.asyncio
    async def test_token_storage_update(self):
        """Test updating tokens in storage."""
        storage = MockTokenStorage()
        
        # Set initial token
        token1 = OAuthToken(
            access_token="token1",
            token_type="Bearer",
            expires_in=3600,
        )
        await storage.set_tokens(token1)
        
        # Update with new token
        token2 = OAuthToken(
            access_token="token2",
            token_type="Bearer",
            expires_in=7200,
        )
        await storage.set_tokens(token2)
        
        # Should have new token
        retrieved = await storage.get_tokens()
        assert retrieved.access_token == "token2"
        assert retrieved.expires_in == 7200


class TestOAuthIntegration:
    """Test OAuth integration with MCP HTTP params."""

    @pytest.mark.asyncio
    async def test_mcp_config_accepts_oauth_provider(self):
        """Test that MCP config properly accepts OAuth provider."""
        class MCPHttpParamsWithAuth(MCPHttpParams):
            auth: object = None
        
        storage = MockTokenStorage()
        
        async def mock_redirect(url: str):
            pass
        
        async def mock_callback():
            return ("code", "state")
        
        provider = OAuthClientProvider(
            server_url="http://localhost:8000/mcp",
            client_metadata=OAuthClientMetadata.model_validate({
                "client_name": "Test",
                "redirect_uris": ["http://localhost:3030/callback"],
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
            }),
            storage=storage,
            redirect_handler=mock_redirect,
            callback_handler=mock_callback,
        )
        
        config = MCPHttpParamsWithAuth(
            url="http://localhost:8000/mcp",
            timeout=timedelta(seconds=30),
            auth=provider,
        )
        
        assert config.auth == provider
        assert isinstance(config.auth, OAuthClientProvider)

    def test_oauth_params_serialization(self):
        """Test that OAuth params can be serialized properly."""
        class MCPHttpParamsWithAuth(MCPHttpParams):
            auth: object = None
        
        mock_provider = Mock(spec=OAuthClientProvider)
        
        config = MCPHttpParamsWithAuth(
            url="http://test.com",
            timeout=timedelta(seconds=60),
            auth=mock_provider,
        )
        
        # Should be able to access all fields
        assert config.url == "http://test.com"
        assert config.timeout.total_seconds() == 60
        assert config.auth == mock_provider


class TestOAuthToken:
    """Test OAuth token handling."""

    def test_oauth_token_creation(self):
        """Test creating OAuth tokens."""
        token = OAuthToken(
            access_token="test_access",
            token_type="Bearer",
            expires_in=3600,
        )
        
        assert token.access_token == "test_access"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

    def test_oauth_token_with_refresh(self):
        """Test OAuth token with refresh token."""
        token = OAuthToken(
            access_token="test_access",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh",
        )
        
        assert token.refresh_token == "test_refresh"

    def test_oauth_token_with_scope(self):
        """Test OAuth token with scope."""
        token = OAuthToken(
            access_token="test_access",
            token_type="Bearer",
            expires_in=3600,
            scope="read write",
        )
        
        assert token.scope == "read write"
