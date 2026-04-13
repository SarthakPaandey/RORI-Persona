"""Conversation state management."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional


class ConversationState:
    """Manages conversation state for multi-turn interactions."""

    def __init__(self):
        self._conversations: Dict[str, List[Dict]] = {}

    def create_conversation(self) -> str:
        """Create a new conversation and return its ID."""
        conv_id = str(uuid.uuid4())
        self._conversations[conv_id] = []
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str):
        """Add a message to a conversation."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        self._conversations[conversation_id].append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def get_history(self, conversation_id: str, max_messages: int = 20) -> List[Dict]:
        """Get conversation history, limited to recent messages."""
        history = self._conversations.get(conversation_id, [])
        return history[-max_messages:]

    def clear_conversation(self, conversation_id: str):
        """Clear a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]


conversation_manager = ConversationState()
