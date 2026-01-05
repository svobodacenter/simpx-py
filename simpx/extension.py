import asyncio
from typing import List, Dict, Optional, Union, Callable, Any, TypeVar, Awaitable, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from .client import ChatClient, ChatCommandError
from .command import ChatType, MsgContent
from .response import ChatResponse, ChatInfo, Contact, Chat, ChatItem, User, GroupInfo, ci_content_text

# Type for contact or group
EntityType = Union[Contact, GroupInfo]

# Type for a scheduled task
TaskType = TypeVar('TaskType')

@dataclass
class ContactWrapper:
    """Wrapper for Contact with additional helper methods."""
    _contact: Contact
    _client: ChatClient
    
    @property
    def id(self) -> int:
        """Get the contact ID."""
        return self._contact["contactId"]
    
    @property
    def name(self) -> str:
        """Get the contact's display name."""
        return self._contact["localDisplayName"]
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Get the contact's profile."""
        return self._contact["profile"]
    
    @property
    def created_at(self) -> datetime:
        """Get the contact creation time."""
        return self._contact["createdAt"]
    
    async def get_chat(self) -> 'ChatWrapper':
        """Get the chat associated with this contact."""
        chat = await self._client.api_get_chat(ChatType.Direct, self.id)
        return ChatWrapper(chat, self._client)
    
    async def send_message(self, text: str) -> List[Dict[str, Any]]:
        """Send a text message to this contact."""
        return await self._client.api_send_text_message(ChatType.Direct, self.id, text)
    
    async def send_content(self, msg_content: MsgContent) -> List[Dict[str, Any]]:
        """Send complex content to this contact."""
        return await self._client.api_send_messages(
            ChatType.Direct,
            self.id,
            [{"msgContent": msg_content}]
        )
    
    async def update_alias(self, alias: str) -> Contact:
        """Update the alias for this contact."""
        return await self._client.api_set_contact_alias(self.id, alias)
    
    async def get_connection_stats(self):
        """Get connection statistics for this contact."""
        stats, profile = await self._client.api_contact_info(self.id)
        return stats, profile
    
    def __str__(self) -> str:
        return f"Contact({self.name}, ID: {self.id})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class GroupWrapper:
    """Wrapper for GroupInfo with additional helper methods."""
    _group_info: GroupInfo
    _client: ChatClient
    
    @property
    def id(self) -> int:
        """Get the group ID."""
        return self._group_info["groupId"]
    
    @property
    def name(self) -> str:
        """Get the group's display name."""
        return self._group_info["localDisplayName"]
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Get the group's profile."""
        return self._group_info["groupProfile"]
    
    @property
    def created_at(self) -> datetime:
        """Get the group creation time."""
        return self._group_info["createdAt"]
    
    @property
    def membership(self) -> Dict[str, Any]:
        """Get the user's membership in this group."""
        return self._group_info["membership"]
    
    async def get_chat(self) -> 'ChatWrapper':
        """Get the chat associated with this group."""
        chat = await self._client.api_get_chat(ChatType.Group, self.id)
        return ChatWrapper(chat, self._client)
    
    async def send_message(self, text: str) -> List[Dict[str, Any]]:
        """Send a text message to this group."""
        return await self._client.api_send_text_message(ChatType.Group, self.id, text)
    
    async def send_content(self, msg_content: MsgContent) -> List[Dict[str, Any]]:
        """Send complex content to this group."""
        return await self._client.api_send_messages(
            ChatType.Group,
            self.id,
            [{"msgContent": msg_content}]
        )
    
    async def get_members(self) -> List[Dict[str, Any]]:
        """Get the members of this group."""
        return await self._client.api_list_members(self.id)
    
    async def leave(self) -> GroupInfo:
        """Leave this group."""
        return await self._client.api_leave_group(self.id)
    
    async def update_profile(self, profile: Dict[str, Any]) -> GroupInfo:
        """Update the group profile."""
        return await self._client.api_update_group(self.id, profile)
    
    def __str__(self) -> str:
        return f"Group({self.name}, ID: {self.id})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class ChatItemWrapper:
    """Wrapper for ChatItem with additional helper methods."""
    _chat_item: ChatItem
    _chat_info: ChatInfo
    _client: ChatClient
    is_live: bool = False 

    def _get_chat_context(self) -> Tuple[ChatType, int]:
        """Return the chat type and target ID based on chat info."""
        if self._chat_info["type"] == "direct":
            return ChatType.Direct, self._chat_info["contact"]["contactId"]
        elif self._chat_info["type"] == "group":
            return ChatType.Group, self._chat_info["groupInfo"]["groupId"]
        else:
            raise ValueError(f"Unsupported chat type: {self._chat_info['type']}")
    
    @property
    def id(self) -> int:
        """Get the chat item ID."""
        return self._chat_item["meta"]["itemId"]
    
    @property
    def text(self) -> str:
        """Get the text content of the message."""
        return self._chat_item["meta"]["itemText"]
    
    @property
    def timestamp(self) -> datetime:
        """Get the timestamp of the message."""
        return self._chat_item["meta"]["itemTs"]
    
    @property
    def created_at(self) -> datetime:
        """Get the creation time of the message."""
        return self._chat_item["meta"]["createdAt"]
    
    @property
    def is_deleted(self) -> bool:
        """Check if the message is deleted."""
        return self._chat_item["meta"]["itemDeleted"]
    
    @property
    def is_edited(self) -> bool:
        """Check if the message is edited."""
        return self._chat_item["meta"]["itemEdited"]
    
    @property
    def is_editable(self) -> bool:
        """Check if the message is editable."""
        return self._chat_item["meta"]["editable"]
    
    @property
    def direction(self) -> Dict[str, Any]:
        """Get the direction of the message (sent/received)."""
        return self._chat_item["chatDir"]
    
    @property
    def content(self) -> Dict[str, Any]:
        """Get the content of the message."""
        return self._chat_item["content"]
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get the status of the message."""
        return self._chat_item["meta"]["itemStatus"]
    
    @property
    def content_text(self) -> Optional[str]:
        """Get the text content from the message content."""
        return ci_content_text(self._chat_item["content"])
    
    async def update(self, msg_content: MsgContent) -> ChatItem:
        """Update the content of the message."""
        chat_type = ChatType.Direct
        chat_id = 0
        
        if self._chat_info["type"] == "direct":
            chat_id = self._chat_info["contact"]["contactId"]
        elif self._chat_info["type"] == "group":
            chat_type = ChatType.Group
            chat_id = self._chat_info["groupInfo"]["groupId"]
        
        return await self._client.api_update_chat_item(
            chat_type, 
            chat_id, 
            self.id, 
            msg_content
        )

    async def update_live(self, new_text: str) -> 'ChatItemWrapper':
        """
        Update this live message with new text.
        This sends an update with liveType 'update' and updates the internal state.
        """
        chat_type, chat_id = self._get_chat_context()
        updated_live_message = {
            "type": "liveText",
            "text": new_text,
            #"liveType": "update",
            "metadata": {}  # Extend as needed
        }
        updated_item = await self._client.api_update_chat_item(
            chat_type, chat_id, self.id, updated_live_message
        )
        self._chat_item = updated_item
        return self

    async def finish_live(self) -> 'ChatItemWrapper':
        """
        Finish the live message by sending an update with liveType 'end'
        and marking the message as no longer live.
        """
        chat_type, chat_id = self._get_chat_context()
        end_live_message = {
            "type": "text",
            "text": self.text,  # Optionally, you might append a notice like " (ended)"
            #"liveType": "end",
            "metadata": {}
        }
        updated_item = await self._client.api_update_chat_item(
            chat_type, chat_id, self.id, end_live_message
        )
        self._chat_item = updated_item
        self.is_live = False
        return self
    
    async def delete(self, delete_mode: str = "broadcast") -> Optional[ChatItem]:
        """Delete the message."""
        from .command import DeleteMode
        
        chat_type = ChatType.Direct
        chat_id = 0
        
        if self._chat_info["type"] == "direct":
            chat_id = self._chat_info["contact"]["contactId"]
        elif self._chat_info["type"] == "group":
            chat_type = ChatType.Group
            chat_id = self._chat_info["groupInfo"]["groupId"]
        
        delete_mode_enum = DeleteMode.Broadcast if delete_mode == "broadcast" else DeleteMode.Internal
        
        return await self._client.api_delete_chat_item(
            chat_type, 
            chat_id, 
            self.id, 
            delete_mode_enum
        )
    
    def __str__(self) -> str:
        return f"ChatItem(ID: {self.id}, Text: {self.text[:20]}...)"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class ChatWrapper:
    """Wrapper for Chat with additional helper methods."""
    _chat: ChatInfo
    _client: ChatClient
    
    @property
    def info(self) -> ChatInfo:
        """Get the chat info."""
        return self._chat
    
    @property
    def type(self) -> str:
        """Get the chat type."""
        return self._chat["type"]
    
    @property
    def items(self) -> List[ChatItemWrapper]:
        """Get the chat items."""
        return [
            ChatItemWrapper(item, self._chat, self._client) 
            for item in self._chat["chatItems"]
        ]
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get the chat statistics."""
        return self._chat["chatStats"]
    
    @property
    def unread_count(self) -> int:
        """Get the number of unread messages."""
        return self._chat["chatStats"]["unreadCount"]
    
    def get_entity(self) -> Union[ContactWrapper, GroupWrapper]:
        """Get the entity associated with this chat (contact or group)."""
        if self.type == "direct":
            return ContactWrapper(self._chat["contact"], self._client)
        elif self.type == "group":
            return GroupWrapper(self._chat["groupInfo"], self._client)
        else:
            raise ValueError(f"Unsupported chat type: {self.type}")

    async def send_message(self, text: str, live: bool = False, ttl: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
            chat_type = ChatType.Direct
        elif self.type == "group":
            entity_id = self._chat["groupInfo"]["groupId"]
            chat_type = ChatType.Group
        else:
            raise ValueError(f"Cannot send message to chat of type: {self.type}")

        # Use the live message API call.
        resp = await self._client.api_send_text_message(
            chat_type, 
            entity_id, 
            text,
            live=live,
            ttl=ttl
        )

        wrapper = ChatItemWrapper(resp[0]['chatItem'], self._chat, self._client, is_live=live)
        return wrapper
    
    
    async def send_content(self, msg_content: MsgContent) -> List[Dict[str, Any]]:
        """Send complex content to this chat."""
        chat_type = ChatType.Direct
        entity_id = 0
        
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
        elif self.type == "group":
            chat_type = ChatType.Group
            entity_id = self._chat["groupInfo"]["groupId"]
        else:
            raise ValueError(f"Cannot send content to chat of type: {self.type}")
        
        return await self._client.api_send_messages(
            chat_type,
            entity_id,
            [{"msgContent": msg_content}]
        )
    
    async def mark_as_read(self) -> None:
        """Mark all messages in this chat as read."""
        chat_type = ChatType.Direct
        entity_id = 0
        
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
        elif self.type == "group":
            chat_type = ChatType.Group
            entity_id = self._chat["groupInfo"]["groupId"]
        else:
            raise ValueError(f"Cannot mark chat of type {self.type} as read")
        
        await self._client.api_chat_read(chat_type, entity_id)
    
    async def clear(self) -> ChatInfo:
        """Clear the chat history."""
        chat_type = ChatType.Direct
        entity_id = 0
        
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
        elif self.type == "group":
            chat_type = ChatType.Group
            entity_id = self._chat["groupInfo"]["groupId"]
        else:
            raise ValueError(f"Cannot clear chat of type {self.type}")
        
        return await self._client.api_clear_chat(chat_type, entity_id)
    
    async def delete(self) -> None:
        """Delete the chat."""
        chat_type = ChatType.Direct
        entity_id = 0
        
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
        elif self.type == "group":
            chat_type = ChatType.Group
            entity_id = self._chat["groupInfo"]["groupId"]
        elif self.type == "contactRequest":
            chat_type = ChatType.ContactRequest
            entity_id = self._chat["contactRequest"]["contactRequestId"]
        else:
            raise ValueError(f"Cannot delete chat of type {self.type}")
        
        await self._client.api_delete_chat(chat_type, entity_id)
    
    async def refresh(self, pagination: Dict[str, Any] = None, search: str = None) -> 'ChatWrapper':
        """Refresh the chat data."""
        if pagination is None:
            pagination = {"count": 100}
        
        chat_type = ChatType.Direct
        entity_id = 0
        
        if self.type == "direct":
            entity_id = self._chat["contact"]["contactId"]
        elif self.type == "group":
            chat_type = ChatType.Group
            entity_id = self._chat["groupInfo"]["groupId"]
        elif self.type == "contactRequest":
            chat_type = ChatType.ContactRequest
            entity_id = self._chat["contactRequest"]["contactRequestId"]
        else:
            raise ValueError(f"Cannot refresh chat of type {self.type}")
        
        updated_chat = await self._client.api_get_chat(chat_type, entity_id, pagination, search)
        return ChatWrapper(updated_chat, self._client)
    
    def __str__(self) -> str:
        entity = "Unknown"
        if self.type == "direct":
            entity = self._chat["contact"]["localDisplayName"]
        elif self.type == "group":
            entity = self._chat["groupInfo"]["localDisplayName"]
        elif self.type == "contactRequest":
            entity = self._chat["contactRequest"]["localDisplayName"]
        
        return f"Chat({self.type}, {entity}, {len(self._chat['chatItems'])} messages)"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class UserWrapper:
    """Wrapper for User with additional helper methods."""
    _user: User
    _client: ChatClient
    
    @property
    def id(self) -> int:
        """Get the user ID."""
        return self._user["userId"]
    
    @property
    def contact_id(self) -> int:
        """Get the user contact ID."""
        return self._user["userContactId"]
    
    @property
    def display_name(self) -> str:
        """Get the user's display name."""
        return self._user["localDisplayName"]
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Get the user's profile."""
        return self._user["profile"]
    
    async def update_profile(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update the user's profile."""
        return await self._client.api_update_profile(self.id, profile)
    
    async def get_chats(self, include_pending: bool = False) -> List[ChatWrapper]:
        """Get all chats for this user."""
        chats = await self._client.api_get_chats(self.id)
        return [ChatWrapper(chat, self._client) for chat in chats]
    
    def __str__(self) -> str:
        return f"User({self.display_name}, ID: {self.id})"
    
    def __repr__(self) -> str:
        return self.__str__()


class ScheduledTask:
    """A task scheduled for future execution."""
    
    def __init__(self, 
                 func: Callable[..., Awaitable[Any]], 
                 args: tuple = None, 
                 kwargs: dict = None,
                 delay: float = 0, 
                 repeat: bool = False, 
                 interval: float = 0,
                 name: str = None):
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.delay = delay
        self.repeat = repeat
        self.interval = interval
        self.name = name
        self.task = None
        self.cancelled = False
    
    async def _run(self):
        """Execute the task."""
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        
        while not self.cancelled:
            try:
                await self.func(*self.args, **self.kwargs)
            except Exception as e:
                print(f"Error in scheduled task: {e}")
            
            if not self.repeat:
                break
            
            await asyncio.sleep(self.interval)
    
    def start(self):
        """Start the scheduled task."""
        self.task = asyncio.create_task(self._run())
        return self.task
    
    def cancel(self):
        """Cancel the scheduled task."""
        self.cancelled = True
        if self.task and not self.task.done():
            self.task.cancel()


class SimpleXBotExtensions:
    """Extension class for SimpleXBot with additional helper methods."""
    
    def __init__(self, bot):
        """Initialize the extensions with a reference to the bot."""
        self.bot = bot
        self.scheduled_tasks = []
    
    async def get_user(self) -> UserWrapper:
        """Get the current active user."""
        user = await self.bot.client.api_get_active_user()
        if user:
            return UserWrapper(user, self.bot.client)
        return None
    
    async def get_contacts(self) -> List[ContactWrapper]:
        """Get all contacts for the active user."""
        user = await self.get_user()
        if not user:
            return []
        
        chats = await self.bot.client.api_get_chats(user.id)
        contacts = []
        
        for chat in chats:
            if chat["chatInfo"]["type"] == "direct":
                contact = chat["chatInfo"]["contact"]
                contacts.append(ContactWrapper(contact, self.bot.client))
        
        return contacts
    
    async def get_contact(self, contact_id: int) -> Optional[ContactWrapper]:
        """Get a specific contact by ID."""
        contacts = await self.get_contacts()
        for contact in contacts:
            if contact.id == contact_id:
                return contact
        return None
    
    async def find_contact_by_name(self, name: str) -> Optional[ContactWrapper]:
        """Find a contact by name (partial match)."""
        contacts = await self.get_contacts()
        for contact in contacts:
            if name.lower() in contact.name.lower():
                return contact
        return None
    
    async def get_groups(self) -> List[GroupWrapper]:
        """Get all groups for the active user."""
        user = await self.get_user()
        if not user:
            return []
        
        chats = await self.bot.client.api_get_chats(user.id)
        groups = []
        
        for chat in chats:
            if chat["chatInfo"]["type"] == "group":
                group = chat["chatInfo"]["groupInfo"]
                groups.append(GroupWrapper(group, self.bot.client))
        
        return groups
    
    async def get_group(self, group_id: int) -> Optional[GroupWrapper]:
        """Get a specific group by ID."""
        groups = await self.get_groups()
        for group in groups:
            if group.id == group_id:
                return group
        return None
    
    async def find_group_by_name(self, name: str) -> Optional[GroupWrapper]:
        """Find a group by name (partial match)."""
        groups = await self.get_groups()
        for group in groups:
            if name.lower() in group.name.lower():
                return group
        return None
    
    async def get_chats(self) -> List[ChatWrapper]:
        """Get all chats for the active user."""
        user = await self.get_user()
        if not user:
            return []
        
        chats = await self.bot.client.api_get_chats(user.id)
        return [ChatWrapper(chat, self.bot.client) for chat in chats]
    
    async def get_chat(self, entity: Union[ContactWrapper, GroupWrapper, int], chat_type: str = None) -> Optional[ChatWrapper]:
        """Get a chat by entity (contact, group) or ID."""
        if isinstance(entity, ContactWrapper):
            return await entity.get_chat()
        elif isinstance(entity, GroupWrapper):
            return await entity.get_chat()
        elif isinstance(entity, int):
            if chat_type is None:
                raise ValueError("chat_type must be provided when using an ID")
            
            chat_type_enum = ChatType.Direct
            if chat_type.lower() == "group":
                chat_type_enum = ChatType.Group
            elif chat_type.lower() == "contactrequest":
                chat_type_enum = ChatType.ContactRequest
            
            chat = await self.bot.client.api_get_chat(chat_type_enum, entity)
            return ChatWrapper(chat, self.bot.client)
        
        return None
    
    async def broadcast_message(self, text: str, contacts: List[ContactWrapper] = None) -> Dict[int, Any]:
        """Send a message to multiple contacts."""
        if contacts is None:
            contacts = await self.get_contacts()
        
        results = {}
        for contact in contacts:
            try:
                result = await contact.send_message(text)
                results[contact.id] = result
            except Exception as e:
                results[contact.id] = str(e)
        
        return results
    
    async def get_contact_requests(self) -> List[Dict[str, Any]]:
        """Get pending contact requests."""
        user = await self.get_user()
        if not user:
            return []
        
        chats = await self.bot.client.api_get_chats(user.id)
        requests = []
        
        for chat in chats:
            if chat["chatInfo"]["type"] == "contactRequest":
                request = chat["chatInfo"]["contactRequest"]
                requests.append(request)
        
        return requests
    
    def schedule_task(self, 
                      func: Callable[..., Awaitable[Any]], 
                      delay: float = 0, 
                      repeat: bool = False, 
                      interval: float = 0, 
                      name: str = None,
                      args: tuple = None, 
                      kwargs: dict = None) -> ScheduledTask:
        """
        Schedule a task to be executed in the future.
        
        Args:
            func: The async function to execute
            delay: Delay in seconds before first execution
            repeat: Whether to repeat the task
            interval: Interval in seconds between repeated executions
            name: Name of the task
            args: Positional arguments to pass to the function
            kwargs: Keyword arguments to pass to the function
            
        Returns:
            ScheduledTask object that can be used to cancel the task
        """
        task = ScheduledTask(func, args, kwargs, delay, repeat, interval, name)
        task.start()
        self.scheduled_tasks.append(task)
        return task
    
    def schedule_message(self, 
                         recipient: Union[ContactWrapper, GroupWrapper, ChatWrapper], 
                         text: str, 
                         delay: float) -> ScheduledTask:
        """
        Schedule a message to be sent in the future.
        
        Args:
            recipient: The recipient (contact, group, or chat)
            text: The message text
            delay: Delay in seconds
            
        Returns:
            ScheduledTask object that can be used to cancel the task
        """
        async def send_delayed_message():
            try:
                if isinstance(recipient, ContactWrapper):
                    await recipient.send_message(text)
                elif isinstance(recipient, GroupWrapper):
                    await recipient.send_message(text)
                elif isinstance(recipient, ChatWrapper):
                    await recipient.send_message(text)
            except Exception as e:
                print(f"Error sending scheduled message: {e}")
        
        return self.schedule_task(send_delayed_message, delay=delay)
    
    def schedule_recurring_message(self, 
                                  recipient: Union[ContactWrapper, GroupWrapper, ChatWrapper], 
                                  text: str, 
                                  interval: float, 
                                  start_delay: float = 0) -> ScheduledTask:
        """
        Schedule a recurring message.
        
        Args:
            recipient: The recipient (contact, group, or chat)
            text: The message text
            interval: Interval in seconds between messages
            start_delay: Delay in seconds before the first message
            
        Returns:
            ScheduledTask object that can be used to cancel the task
        """
        async def send_recurring_message():
            try:
                if isinstance(recipient, ContactWrapper):
                    await recipient.send_message(text)
                elif isinstance(recipient, GroupWrapper):
                    await recipient.send_message(text)
                elif isinstance(recipient, ChatWrapper):
                    await recipient.send_message(text)
            except Exception as e:
                print(f"Error sending recurring message: {e}")
        
        return self.schedule_task(
            send_recurring_message, 
            delay=start_delay, 
            repeat=True, 
            interval=interval
        )
    
    def cancel_all_scheduled_tasks(self):
        """Cancel all scheduled tasks."""
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks = []

