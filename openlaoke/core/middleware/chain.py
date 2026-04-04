"""Middleware chain implementation."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import Self

from openlaoke.core.middleware.base import Event, Middleware
from openlaoke.core.middleware.context import MiddlewareContext

logger = logging.getLogger(__name__)


class MiddlewareChain:
    """Chain of middleware that process requests in sequence.

    The chain executes middleware in the order they were added.
    Each middleware can:
    - Pre-process before calling next
    - Post-process after next returns
    - Short-circuit by not calling next
    """

    def __init__(self) -> None:
        """Initialize an empty middleware chain."""
        self.middlewares: list[Middleware] = []
        self._setup_complete: bool = False

    def add(self, middleware: Middleware) -> Self:
        """Add a middleware to the chain.

        Args:
            middleware: The middleware to add

        Returns:
            Self for chaining
        """
        self.middlewares.append(middleware)
        return self

    def remove(self, middleware_name: str) -> bool:
        """Remove a middleware by name.

        Args:
            middleware_name: Name of the middleware to remove

        Returns:
            True if removed, False if not found
        """
        for i, mw in enumerate(self.middlewares):
            if mw.name == middleware_name:
                self.middlewares.pop(i)
                return True
        return False

    def insert(self, index: int, middleware: Middleware) -> Self:
        """Insert a middleware at a specific position.

        Args:
            index: Position to insert at
            middleware: The middleware to insert

        Returns:
            Self for chaining
        """
        self.middlewares.insert(index, middleware)
        return self

    def get(self, name: str) -> Middleware | None:
        """Get a middleware by name.

        Args:
            name: Name of the middleware

        Returns:
            The middleware if found, None otherwise
        """
        for mw in self.middlewares:
            if mw.name == name:
                return mw
        return None

    def clear(self) -> Self:
        """Remove all middleware from the chain.

        Returns:
            Self for chaining
        """
        self.middlewares.clear()
        return self

    def process(self, context: MiddlewareContext) -> AsyncGenerator[Event, None]:
        """Process the context through the middleware chain.

        Args:
            context: The middleware context to process

        Yields:
            Events generated during processing
        """
        return self._run_chain(context, 0)

    def _run_chain(
        self,
        context: MiddlewareContext,
        index: int,
    ) -> AsyncGenerator[Event, None]:
        """Recursively run the middleware chain.

        Args:
            context: The middleware context
            index: Current middleware index

        Yields:
            Events from the middleware
        """
        return self._run_chain_impl(context, index)

    async def _run_chain_impl(
        self,
        context: MiddlewareContext,
        index: int,
    ) -> AsyncGenerator[Event, None]:
        """Implementation of chain execution."""
        if context.aborted:
            logger.debug(f"Middleware chain aborted at index {index}")
            return

        if index >= len(self.middlewares):
            logger.debug("Middleware chain complete")
            return

        middleware = self.middlewares[index]
        self._run_setup_single(middleware, context)

        def next_middleware(ctx: MiddlewareContext) -> AsyncGenerator[Event, None]:
            return self._run_chain_impl(ctx, index + 1)

        start_time = time.time()
        try:
            async for event in middleware(context, next_middleware):
                yield event
        except Exception as e:
            logger.exception(f"Error in middleware {middleware.name}: {e}")
            context.error = e
            raise
        finally:
            elapsed = time.time() - start_time
            logger.debug(f"Middleware {middleware.name} took {elapsed:.3f}s")
            self._run_teardown_single(middleware, context)

    def _run_setup_single(self, middleware: Middleware, context: MiddlewareContext) -> None:
        """Run setup for a single middleware."""
        try:
            middleware.setup(context)
        except Exception as e:
            logger.exception(f"Error in setup for {middleware.name}: {e}")
            raise

    def _run_teardown_single(self, middleware: Middleware, context: MiddlewareContext) -> None:
        """Run teardown for a single middleware."""
        try:
            middleware.teardown(context)
        except Exception as e:
            logger.exception(f"Error in teardown for {middleware.name}: {e}")

    def __len__(self) -> int:
        """Get the number of middleware in the chain."""
        return len(self.middlewares)

    def __contains__(self, name: str) -> bool:
        """Check if a middleware is in the chain."""
        return self.get(name) is not None

    def __iter__(self):
        """Iterate over middleware."""
        return iter(self.middlewares)
