"""Hook system for extensibility."""

from __future__ import annotations

from openlaoke.types.hooks import HookContext, HookHandler, HookRegistration, HookResult, HookType


class HookManager:
    """Manages the registration and execution of hooks."""

    def __init__(self) -> None:
        self._hooks: dict[HookType, list[HookRegistration]] = {}

    def register(
        self,
        hook_type: HookType,
        handler: HookHandler,
        priority: int = 0,
        name: str = "",
    ) -> None:
        reg = HookRegistration(
            hook_type=hook_type,
            handler=handler,
            priority=priority,
            name=name or getattr(handler, "__name__", str(handler)),
        )
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        self._hooks[hook_type].append(reg)
        self._hooks[hook_type].sort(key=lambda r: r.priority)

    def unregister(self, hook_type: HookType, name: str) -> None:
        if hook_type in self._hooks:
            self._hooks[hook_type] = [r for r in self._hooks[hook_type] if r.name != name]

    async def execute(self, ctx: HookContext) -> HookResult:
        handlers = self._hooks.get(ctx.hook_type, [])
        for reg in handlers:
            try:
                result = await reg.handler(ctx)
                if result.should_abort:
                    return result
            except Exception as e:
                return HookResult(
                    success=False,
                    error=str(e),
                    should_abort=False,
                )
        return HookResult(success=True)

    def get_registered_hooks(self) -> dict[str, list[str]]:
        result = {}
        for hook_type, regs in self._hooks.items():
            result[hook_type.value] = [r.name for r in regs]
        return result
