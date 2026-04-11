"""Convex-backed storage for the hosted wrapper.

This backend exists so the same agent can run against a cloud-managed data plane
without moving core behavior out of the agent runtime.
"""

from __future__ import annotations


class ConvexStore:
    """Placeholder Convex-backed implementation of the FarmStore protocol."""

    def __init__(self, deployment_url: str, deploy_key: str | None = None):
        self.deployment_url = deployment_url
        self.deploy_key = deploy_key

    def connect(self) -> None:
        """Validate configuration for the remote Convex deployment."""
        raise NotImplementedError("ConvexStore.connect is not implemented yet.")
