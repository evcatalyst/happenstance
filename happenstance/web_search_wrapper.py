"""Wrapper for AI-powered web search using Grok/OpenAI."""

from __future__ import annotations

# This module provides access to AI-powered search
# The actual implementation will use github-mcp-server-web_search tool
# which leverages Grok and OpenAI APIs that are already configured

def search_with_ai(query: str) -> str:
    """
    Perform AI-powered web search to get information.
    
    This function is designed to be called from Python code, but the actual
    implementation will need to be invoked through the tool system.
    
    For now, this raises an error to indicate that the function must be
    called through the proper integration layer.
    
    Args:
        query: Search query or prompt for the AI
        
    Returns:
        AI-generated response with information
        
    Raises:
        NotImplementedError: This function must be called through the tool layer
    """
    raise NotImplementedError(
        "AI search must be invoked through the tool system. "
        "Use the web_search tool directly in the aggregate module."
    )
