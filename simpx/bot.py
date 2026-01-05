import asyncio
import random
import functools
import inspect
import re
from typing import Dict, List, Callable, Optional, Any, Union, TypeVar, Pattern, Awaitable
import traceback

from .client import ChatClient, ChatCommandError
from .command import ChatType
from .response import ChatInfoType, ci_content_text, ChatResponse, ChatItem, ChatInfo, AChatItem
from .profile import BotProfile, ProfileManager

from .extension import (
    SimpleXBotExtensions, ContactWrapper, GroupWrapper, 
    ChatWrapper, UserWrapper, ChatItemWrapper, ScheduledTask
)

T = TypeVar('T')
CommandCallback = Callable[..., Awaitable[Any]]

class SimpleXBot:
    """
    A Pythonic framework for creating SimpleX chat bots.
    
    This class provides an easy-to-use interface for building bots using decorators
    similar to Discord.py, while respecting the SimpleX architecture.
    """
    
    def __init__(self, profile: Optional[BotProfile] = None, server_url: Optional[str] = None):
        """
        Initialize the SimpleX bot.
        
        Args:
            profile: The bot profile to use
            server_url: The WebSocket URL of the SimpleX server (overrides profile's server URL)
        """
        self.profile_manager = ProfileManager()
        self.server_url = server_url
        self.client = None
        self.running = False
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._command_handlers: Dict[Union[str, Pattern], CommandCallback] = {}
        self._command_prefix = "!"
        self._help_command_enabled = True
        self._help_command_text = {}
        self._welcome_message = None
        self._auto_read_messages = True  # Default to auto-read messages

        if profile:
            self.profile_manager.add_profile(profile, "default")
            if profile.welcome_message:
                self._welcome_message = profile.welcome_message
            if profile.command_prefix:
                self._command_prefix = profile.command_prefix
            if not profile.help_message:
                self._help_command_enabled = False
        
        self.ext = None

    async def start(self, profile: Optional[BotProfile] = None):
        """
        Start the bot and connect to the SimpleX server.
        
        This method initializes the ChatClient, checks for an active user profile,
        sets up the bot's address, and starts processing messages.
        
        Args:
            profile: The bot profile to use (overrides the one set in constructor)
        """
        # Set up profile if provided
        if profile:
            self.profile_manager.add_profile(profile, "default")
            if profile.welcome_message:
                self._welcome_message = profile.welcome_message
            if profile.command_prefix:
                self._command_prefix = profile.command_prefix
        
        # Initialize the client with profile - will use existing profile if available
        self.client = await self.profile_manager.initialize(server_url=self.server_url)
        
        # Initialize the extensions now that we have a client
        self.ext = SimpleXBotExtensions(self)
        
        # Update bot configuration from the current profile
        if self.profile_manager.current_profile:
            if self.profile_manager.current_profile.welcome_message and not self._welcome_message:
                self._welcome_message = self.profile_manager.current_profile.welcome_message
            if self.profile_manager.current_profile.command_prefix:
                self._command_prefix = self.profile_manager.current_profile.command_prefix
        
        # Register built-in help command if enabled
        if self._help_command_enabled:
            self._register_help_command()
        
        # Register default welcome message handler if one is set
        if self._welcome_message:
            self._register_welcome_handler()
        
        # Start processing messages
        self.running = True
        await self._process_messages()
    
    def set_auto_read(self, enabled: bool):
        """
        Enable or disable automatic message reading.
        
        When enabled, messages are automatically marked as read after processing.
        
        Args:
            enabled: Whether to enable auto-read
        """
        self._auto_read_messages = enabled

    def _register_help_command(self):
        """Register the built-in help command."""
        async def help_command(chat_info, chat_item, **kwargs):
            command = kwargs.get('args', '').strip()
            if command:
                # Show help for specific command
                help_text = self._help_command_text.get(command)
                if help_text:
                    await self.send_message(chat_info, f"*{self._command_prefix}{command}*\n{help_text}")
                else:
                    await self.send_message(chat_info, f"No help available for command `{command}`")
            else:
                # Show general help
                commands = list(self._help_command_text.keys())
                if commands:
                    help_text = "Available commands:\n" + "\n".join(f"{self._command_prefix}{cmd} - {self._help_command_text[cmd].split('.')[0]}." for cmd in sorted(commands))
                    await self.send_message(chat_info, help_text)
                else:
                    await self.send_message(chat_info, "No commands available.")
        
        self.command("help", help="Shows this help message")(help_command)
    
    def _register_welcome_handler(self):
        """Register the default welcome message handler."""
        @self.event("contactConnected")
        async def on_contact_connected(response):
            contact = response.get("contact", {})
            display_name = contact.get("profile", {}).get("displayName", "Unknown")
            contact_id = contact.get("contactId")
            
            print(f"{display_name} connected")
            
            # Format the welcome message with the contact's display name
            message = self._welcome_message
            if "{name}" in message:
                message = message.format(name=display_name)
            
            # Send welcome message
            await self.client.api_send_text_message(
                ChatType.Direct,
                contact_id,
                message
            )

    async def _process_messages(self):
        """Process incoming messages and dispatch events."""
        while self.running:
            try:
                response = await self.client.msg_q.dequeue()
                
                # Skip processing if we got None or an empty response
                if not response:
                    continue
                    
                # Debug logging to understand the response structure
                print(f"Received message of type: {response.get('type')}")
                
                await self._dispatch_event(response)
            except Exception as e:
                print(f"Error processing message: {e}")
                traceback.print_exc()
                # Add a small delay to prevent tight error loops
                await asyncio.sleep(0.1)

    async def _dispatch_event(self, response: ChatResponse):
        """
        Dispatch an event based on the response type.
        
        Args:
            response: The chat response from the server
        """
        response_type = response.get("type")
        
        # Call registered event handlers for this response type
        handlers = self._event_handlers.get(response_type, [])
        for handler in handlers:
            try:
                await handler(response)
            except Exception as e:
                print(f"Error in event handler for {response_type}: {e}")
        
        # Special handling for new chat items (messages)
        if response_type == "newChatItems":
            await self._handle_new_chat_items(response)

    async def _handle_new_chat_items(self, response: ChatResponse):
        """
        Handle new chat items (messages).
        
        Args:
            response: The 'newChatItems' response
        """
        print(f"Processing {len(response.get('chatItems', []))} new chat items")
        
        for chat_item_data in response.get("chatItems", []):
            try:
                chat_info = chat_item_data.get("chatInfo", {})
                chat_item = chat_item_data.get("chatItem", {})
                
                # Debug message
                dir_type = chat_item.get("chatDir", {}).get("type", "unknown")
                print(f"Processing message with direction: {dir_type}")
                
                # Only process received messages, not ones we sent
                # Skip processing sent messages (those with directSnd or groupSnd direction)
                if dir_type.startswith("directSnd") or dir_type.startswith("groupSnd"):
                    print("Skipping sent message")
                    continue
                
                # Get message content
                content = chat_item.get("content", {})
                msg_text = ci_content_text(content)
                
                if not msg_text:
                    print("Message has no text content, skipping")
                    continue
                    
                print(f"Processing message: {msg_text[:30]}...")
                
                # Check if it's a command
                if msg_text.startswith(self._command_prefix):
                    print(f"Handling command: {msg_text}")
                    await self._handle_command(msg_text[len(self._command_prefix):], chat_info, chat_item)
                
                # Auto-read messages if enabled (after processing)
                if self._auto_read_messages:
                    await self._mark_chat_item_as_read(chat_info, chat_item)
                    
            except Exception as e:
                print(f"Error processing chat item: {e}")
    
    async def _mark_chat_item_as_read(self, chat_info: ChatInfo, chat_item: ChatItem):
        """Mark a specific chat item as read."""
        try:
            chat_type = None
            chat_id = None
            
            if chat_info.get("type") == "direct":
                chat_type = ChatType.Direct
                chat_id = chat_info.get("contact", {}).get("contactId")
            elif chat_info.get("type") == "group":
                chat_type = ChatType.Group
                chat_id = chat_info.get("groupInfo", {}).get("groupId")
            
            if chat_type and chat_id and chat_item.get("meta", {}).get("itemId"):
                item_id = chat_item["meta"]["itemId"]
                
                # Create an item range for this specific message
                item_range = {
                    "fromItem": 0,
                    "toItem": item_id
                }
                
                await self.client.api_chat_read(chat_type, chat_id, item_id)
        except Exception as e:
            print(f"Error marking message as read: {e}")
    
    async def _handle_command(self, command_text: str, chat_info: ChatInfo, chat_item: ChatItem):
        """
        Handle a command message.
        
        Args:
            command_text: The command text without prefix
            chat_info: The chat info
            chat_item: The chat item containing the command
        """
        # Split the command into the command name and arguments
        parts = command_text.split(maxsplit=1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check for exact command matches first
        if command_name in self._command_handlers:
            handler = self._command_handlers[command_name]
            await self._call_command_handler(handler, chat_info, chat_item, args=args)
            return
        
        # Then check for regex pattern matches
        for pattern, handler in self._command_handlers.items():
            if isinstance(pattern, Pattern) and pattern.match(command_text):
                match = pattern.match(command_text)
                if match:
                    kwargs = match.groupdict()
                    await self._call_command_handler(handler, chat_info, chat_item, **kwargs)
                    return
    
    async def _call_command_handler(self, handler: CommandCallback, chat_info: ChatInfo, chat_item: ChatItem, **kwargs):
        """
        Call a command handler with the appropriate arguments.
        
        This method inspects the handler's signature and passes only the
        parameters that it accepts.
        
        Args:
            handler: The command handler function
            chat_info: The chat info
            chat_item: The chat item
            **kwargs: Additional keyword arguments
        """
        try:
            sig = inspect.signature(handler)
            handler_kwargs = {}
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                elif param_name == 'chat_info':
                    handler_kwargs['chat_info'] = chat_info
                elif param_name == 'chat_item':
                    handler_kwargs['chat_item'] = chat_item
                elif param_name == 'bot':
                    handler_kwargs['bot'] = self
                elif param_name == 'client':
                    handler_kwargs['client'] = self.client
                elif param_name == 'profile':
                    handler_kwargs['profile'] = self.profile_manager.current_profile
                elif param_name in kwargs:
                    handler_kwargs[param_name] = kwargs[param_name]
                elif param.default is not inspect.Parameter.empty:
                    # If the parameter has a default value, we don't need to provide it
                    pass
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    # If the handler accepts **kwargs, pass all remaining kwargs
                    handler_kwargs.update(kwargs)
            
            await handler(**handler_kwargs)
        except Exception as e:
            traceback.print_exc()
            print(f"Error in command handler: {e}")
    
    async def get_user(self) -> UserWrapper:
        """Get the current active user."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_user()
    
    async def get_contacts(self) -> List[ContactWrapper]:
        """Get all contacts for the active user."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_contacts()
    
    async def get_contact(self, contact_id: int) -> Optional[ContactWrapper]:
        """Get a specific contact by ID."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_contact(contact_id)
    
    async def find_contact_by_name(self, name: str) -> Optional[ContactWrapper]:
        """Find a contact by name (partial match)."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.find_contact_by_name(name)
    
    async def get_groups(self) -> List[GroupWrapper]:
        """Get all groups for the active user."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_groups()
    
    async def get_group(self, group_id: int) -> Optional[GroupWrapper]:
        """Get a specific group by ID."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_group(group_id)
    
    async def find_group_by_name(self, name: str) -> Optional[GroupWrapper]:
        """Find a group by name (partial match)."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.find_group_by_name(name)
    
    async def get_chats(self) -> List[ChatWrapper]:
        """Get all chats for the active user."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_chats()
    
    async def get_chat(self, entity, chat_type: str = None) -> Optional[ChatWrapper]:
        """Get a chat by entity (contact, group) or ID."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_chat(entity, chat_type)
    
    async def broadcast_message(self, text: str, contacts=None) -> Dict[int, Any]:
        """Send a message to multiple contacts."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.broadcast_message(text, contacts)
    
    async def get_contact_requests(self) -> List[Dict[str, Any]]:
        """Get pending contact requests."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return await self.ext.get_contact_requests()
    
    def schedule_task(self, func, delay=0, repeat=False, interval=0, name: str = None, args=None, kwargs=None):
        """Schedule a task to be executed in the future."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return self.ext.schedule_task(func, delay, repeat, interval, name, args, kwargs)

    def cancel_task(self, name: str):
        """Cancel a task."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return self.ext.cancel_task(name)
    
    def schedule_message(self, recipient, text: str, delay: float):
        """Schedule a message to be sent in the future."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return self.ext.schedule_message(recipient, text, delay)
    
    def schedule_recurring_message(self, recipient, text: str, interval: float, start_delay=0):
        """Schedule a recurring message."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return self.ext.schedule_recurring_message(recipient, text, interval, start_delay)
    
    def cancel_all_scheduled_tasks(self):
        """Cancel all scheduled tasks."""
        if not self.ext:
            raise ValueError("Bot has not been started yet.")
        return self.ext.cancel_all_scheduled_tasks()
    
    async def send_message(self, recipient, text: str, live: bool = False, ttl: Optional[int] = None) -> List[Any]:
        """
        Send a text message to a recipient.
        
        The recipient can be a ContactWrapper, GroupWrapper, ChatWrapper, ChatInfo,
        or a tuple/dict with the necessary information.
        
        Args:
            recipient: The recipient to send the message to
            text: The message text
            
        Returns:
            The list of chat items created
        """
        if isinstance(recipient, ContactWrapper):
            return await recipient.send_message(text,live=live,ttl=ttl)
        elif isinstance(recipient, GroupWrapper):
            return await recipient.send_message(text,live=live,ttl=ttl)
        elif isinstance(recipient, ChatWrapper):
            return await recipient.send_message(text,live=live,ttl=ttl)
        else:
            # Handle the original ChatInfo case and other potential formats
            contact_id = None
            chat_type = ChatType.Direct
            
            if isinstance(recipient, dict):
                if recipient.get("type") == "direct":
                    contact_id = recipient.get("contact", {}).get("contactId")
                elif recipient.get("type") == "group":
                    chat_type = ChatType.Group
                    contact_id = recipient.get("groupInfo", {}).get("groupId")
            
            if not contact_id:
                raise ValueError("Cannot send message: invalid recipient format")
            
            return await self.client.api_send_text_message(
                chat_type,
                contact_id,
                text,
                live=live,
                ttl=ttl
            )
    
    def set_command_prefix(self, prefix: str):
        """
        Set the command prefix.
        
        Args:
            prefix: The new command prefix
        """
        self._command_prefix = prefix
    
    def set_welcome_message(self, message: str):
        """
        Set a welcome message to send when a contact connects.
        
        You can use {name} in the message to include the contact's display name.
        
        Args:
            message: The welcome message template
        """
        self._welcome_message = message
        
        # Update profile if available
        if self.profile_manager.current_profile:
            self.profile_manager.current_profile.welcome_message = message
    
    def set_profile(self, profile: BotProfile, name: str = "default"):
        """
        Set the bot profile.
        
        Args:
            profile: The profile to use
            name: Name to identify the profile
        """
        self.profile_manager.add_profile(profile, name)
        
        # Update bot configuration from profile
        if profile.welcome_message:
            self._welcome_message = profile.welcome_message
        if profile.command_prefix:
            self._command_prefix = profile.command_prefix
    
    async def switch_profile(self, name: str):
        """
        Switch to a different profile.
        
        Args:
            name: Name of the profile to switch to
        """
        profile = await self.profile_manager.switch_profile(name)
        
        # Update bot configuration from profile
        if profile.welcome_message:
            self._welcome_message = profile.welcome_message
        if profile.command_prefix:
            self._command_prefix = profile.command_prefix
            
        # If bot is running, reconnect contacts
        if self.running:
            # Re-register welcome message handler if one is set
            if self._welcome_message:
                self._register_welcome_handler()
    
    async def list_available_profiles(self):
        """
        List all available profiles on the SimpleX server.
        
        Returns:
            Dictionary mapping profile IDs to (display_name, full_name) tuples
        """
        if not self.client:
            raise ValueError("Client not initialized. Bot must be started first.")
        
        return await self.profile_manager.list_available_profiles()
    
    @property
    def current_profile(self) -> Optional[BotProfile]:
        """Get the current bot profile."""
        return self.profile_manager.current_profile
    
    def on_contact_connected(self):
        """
        Decorator to register a custom handler for contact connections.
        This replaces the default welcome message handler.
        
        Returns:
            A decorator function
        """
        def decorator(func):
            if "contactConnected" in self._event_handlers:
                self._event_handlers["contactConnected"] = []
            return self.event("contactConnected")(func)
        return decorator
    
    def event(self, event_type: str = None):
        """
        Decorator to register an event handler.
        
        Args:
            event_type: The type of event to handle. If None, the function name is used.
            
        Returns:
            A decorator function
        """
        def decorator(func):
            nonlocal event_type
            if event_type is None:
                event_type = func.__name__
            
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            
            self._event_handlers[event_type].append(func)
            return func
        
        return decorator
    
    def command(self, name: str = None, *, pattern: str = None, help: str = None):
        """
        Decorator to register a command handler.
        
        Args:
            name: The name of the command
            pattern: A regex pattern to match against the command text
            help: Help text for the command
            
        Returns:
            A decorator function
        """
        def decorator(func):
            nonlocal name
            if name is None:
                name = func.__name__
            
            if pattern:
                compiled_pattern = re.compile(pattern)
                self._command_handlers[compiled_pattern] = func
            else:
                self._command_handlers[name] = func
            
            if help:
                self._help_command_text[name] = help
            
            return func
        
        return decorator
    
    def enable_help_command(self, enabled: bool = True):
        """
        Enable or disable the built-in help command.
        
        Args:
            enabled: Whether the help command should be enabled
        """
        self._help_command_enabled = enabled
    
    async def close(self):
        """Close the bot and disconnect from the SimpleX server."""
        if self.ext:
            # Cancel any scheduled tasks
            self.ext.cancel_all_scheduled_tasks()
        
        if self.client:
            self.running = False
            await self.client.disconnect()
