"""Inter-agent communication system."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class MessageType(StrEnum):
    """Types of messages in the agent communication system."""

    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    SYSTEM = "system"
    BROADCAST = "broadcast"
    QUERY = "query"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    CONTROL = "control"


class MessagePriority(StrEnum):
    """Priority levels for messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """Message structure for inter-agent communication."""

    sender: str
    content: Any
    message_type: MessageType = MessageType.TASK
    recipients: list[str] = field(default_factory=list)
    priority: MessagePriority = MessagePriority.NORMAL
    message_id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "content": self.content,
            "message_type": self.message_type.value,
            "recipients": self.recipients,
            "priority": self.priority.value,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            sender=data["sender"],
            content=data["content"],
            message_type=MessageType(data["message_type"]),
            recipients=data.get("recipients", []),
            priority=MessagePriority(data.get("priority", "normal")),
            message_id=data["message_id"],
            timestamp=data["timestamp"],
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


class AgentMailbox:
    """Message mailbox for inter-agent communication.

    Provides:
    - Message queue per agent
    - Publish-subscribe pattern
    - Broadcast notifications
    - Message persistence
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        max_queue_size: int = 1000,
    ):
        """Initialize the mailbox system.

        Args:
            persist_dir: Directory for message persistence (optional).
            max_queue_size: Maximum messages per queue.
        """
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.max_queue_size = max_queue_size

        self._queues: dict[str, asyncio.Queue] = defaultdict(
            lambda: asyncio.Queue(maxsize=max_queue_size)
        )
        self._subscribers: dict[str, list[str]] = defaultdict(list)
        self._message_history: dict[str, list[Message]] = defaultdict(list)
        self._lock = asyncio.Lock()

        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_history()

    async def send(self, message: Message) -> None:
        """Send a message to recipients.

        Args:
            message: Message to send.
        """
        async with self._lock:
            for recipient in message.recipients:
                queue = self._queues[recipient]

                if queue.full():
                    await queue.get()
                    logger.warning(f"Queue full for {recipient}, dropped oldest message")

                await queue.put(message)

                self._message_history[recipient].append(message)
                if len(self._message_history[recipient]) > self.max_queue_size:
                    self._message_history[recipient] = self._message_history[recipient][
                        -self.max_queue_size :
                    ]

            if message.correlation_id:
                corr_queue = self._queues[f"corr_{message.correlation_id}"]
                if not corr_queue.full():
                    await corr_queue.put(message)

            logger.debug(
                f"Message {message.message_id} sent to {len(message.recipients)} recipients"
            )

            if self.persist_dir:
                self._persist_message(message)

    async def receive(
        self,
        agent_id: str,
        timeout: float | None = None,
    ) -> Message | None:
        """Receive a message for an agent.

        Args:
            agent_id: Agent ID to receive message for.
            timeout: Optional timeout in seconds.

        Returns:
            Message if available, None otherwise.
        """
        queue = self._queues[agent_id]

        try:
            if timeout:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                msg = await queue.get()

            if isinstance(msg, Message):
                return msg
            return None
        except TimeoutError:
            return None

    async def get_messages(
        self,
        agent_id: str,
        message_type: MessageType | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages for an agent from history.

        Args:
            agent_id: Agent ID to get messages for.
            message_type: Optional message type filter.
            limit: Optional limit on number of messages.

        Returns:
            List of messages.
        """
        async with self._lock:
            messages = self._message_history.get(agent_id, [])

            if message_type:
                messages = [m for m in messages if m.message_type == message_type]

            if limit:
                messages = messages[-limit:]

            return messages

    async def broadcast(
        self,
        sender: str,
        content: Any,
        message_type: MessageType = MessageType.BROADCAST,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Broadcast a message to all subscribers.

        Args:
            sender: Sender agent ID.
            content: Message content.
            message_type: Message type.
            priority: Message priority.

        Returns:
            Message ID.
        """
        subscribers = self._subscribers.get(sender, [])

        message = Message(
            sender=sender,
            content=content,
            message_type=message_type,
            recipients=subscribers,
            priority=priority,
        )

        await self.send(message)
        return message.message_id

    def subscribe(self, subscriber_id: str, topic: str) -> None:
        """Subscribe an agent to a topic.

        Args:
            subscriber_id: Agent ID to subscribe.
            topic: Topic to subscribe to.
        """
        if subscriber_id not in self._subscribers[topic]:
            self._subscribers[topic].append(subscriber_id)
            logger.info(f"Agent {subscriber_id} subscribed to {topic}")

    def unsubscribe(self, subscriber_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic.

        Args:
            subscriber_id: Agent ID to unsubscribe.
            topic: Topic to unsubscribe from.
        """
        if subscriber_id in self._subscribers[topic]:
            self._subscribers[topic].remove(subscriber_id)
            logger.info(f"Agent {subscriber_id} unsubscribed from {topic}")

    async def send_and_wait(
        self,
        sender: str,
        recipient: str,
        content: Any,
        timeout: float = 60.0,
    ) -> Message | None:
        """Send a message and wait for response.

        Args:
            sender: Sender agent ID.
            recipient: Recipient agent ID.
            content: Message content.
            timeout: Timeout in seconds.

        Returns:
            Response message if received.
        """
        correlation_id = f"corr_{uuid4().hex[:8]}"

        message = Message(
            sender=sender,
            content=content,
            recipients=[recipient],
            correlation_id=correlation_id,
        )

        await self.send(message)

        corr_queue = self._queues[f"corr_{correlation_id}"]
        try:
            response = await asyncio.wait_for(corr_queue.get(), timeout=timeout)
            if isinstance(response, Message):
                return response
            return None
        except TimeoutError:
            logger.warning(f"Timeout waiting for response to {correlation_id}")
            return None

    def clear_history(self, agent_id: str | None = None) -> None:
        """Clear message history.

        Args:
            agent_id: Optional agent ID to clear history for. If None, clears all.
        """
        if agent_id:
            self._message_history[agent_id] = []
        else:
            self._message_history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get mailbox statistics.

        Returns:
            Dictionary with mailbox statistics.
        """
        return {
            "queue_count": len(self._queues),
            "total_messages": sum(len(msgs) for msgs in self._message_history.values()),
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values()),
            "topic_count": len(self._subscribers),
        }

    def _persist_message(self, message: Message) -> None:
        """Persist a message to disk.

        Args:
            message: Message to persist.
        """
        if not self.persist_dir:
            return

        try:
            date_str = datetime.fromtimestamp(message.timestamp).strftime("%Y-%m-%d")
            persist_file = self.persist_dir / f"messages_{date_str}.jsonl"

            with open(persist_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

    def _load_history(self) -> None:
        """Load message history from disk."""
        if not self.persist_dir:
            return

        try:
            for msg_file in self.persist_dir.glob("messages_*.jsonl"):
                with open(msg_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                msg_data = json.loads(line)
                                message = Message.from_dict(msg_data)
                                for recipient in message.recipients:
                                    self._message_history[recipient].append(message)
                            except Exception as e:
                                logger.error(f"Failed to load message: {e}")
        except Exception as e:
            logger.error(f"Failed to load message history: {e}")
