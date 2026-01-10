import asyncio
import json
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, TypeVar, Generic, cast

from .queuex import ABQueue
from .transport import (
    ChatTransport, ChatServer, ChatSrvRequest, ChatSrvResponse, 
    ChatResponseError, local_server, noop
)
from .command import (
    ChatCommand, ChatType, Profile, cmd_string, MsgContent,
    GroupMemberRole, ComposedMessage, DeleteMode, ChatItemId, GroupProfile
)
from .response import (
    ChatResponse, ChatInfo, User, Contact, GroupInfo, GroupMember,
    AChatItem, ChatItem, ConnectionStats, CRChatCmdError, Chat
)

class ConnReqType(str, Enum):
    """Connection request types."""
    Invitation = "invitation"
    Contact = "contact"

class ChatClientConfig:
    """Configuration for the chat client."""
    
    def __init__(self, q_size: int, tcp_timeout: float):
        self.q_size = q_size
        self.tcp_timeout = tcp_timeout

class Request:
    """A request with promise-like resolution methods."""
    
    def __init__(self, 
                 resolve: Callable[[ChatResponse], None], 
                 reject: Callable[[Optional[Union[ChatResponseError, Any]]], None]):
        self.resolve = resolve
        self.reject = reject

class ChatCommandError(Exception):
    """Error in chat command execution."""
    
    def __init__(self, message: str, response: ChatResponse):
        super().__init__(message)
        self.message = message
        self.response = response

class ChatClient:
    """Client for chat service communication."""
    
    default_config = ChatClientConfig(q_size=16, tcp_timeout=4000)
    
    def __init__(self, 
                 server: Union[ChatServer, str], 
                 config: ChatClientConfig,
                 msg_q: ABQueue,
                 client_task: asyncio.Task,
                 transport: ChatTransport):
        self._connected = True
        self.client_corr_id = 0
        self.sent_commands: Dict[str, Request] = {}
        self.server = server
        self.config = config
        self.msg_q = msg_q
        self.client = client_task
        self.transport = transport
    
    @classmethod
    async def create(cls, 
                     server: Union[ChatServer, str] = None, 
                     cfg: ChatClientConfig = None) -> 'ChatClient':
        """Create and initialize a chat client."""
        if server is None:
            server = local_server
        if cfg is None:
            cfg = cls.default_config
        
        transport = await ChatTransport.connect(server, cfg.tcp_timeout / 1000, cfg.q_size)
        msg_q = ABQueue[ChatResponse](cfg.q_size)
        
        # Create instance first so we can reference it in the task
        client = cls(server, cfg, msg_q, None, transport)
        
        # Create and start the client task
        client_task = asyncio.create_task(cls._run_client(client, transport))
        client.client = client_task
        
        return client
    
    @staticmethod
    async def _run_client(client: 'ChatClient', transport: ChatTransport) -> None:
        """Background task to process incoming messages."""
        try:
            async for item in transport:
                if isinstance(item, ChatResponseError):
                    print("Chat response error: ", item)
                else:
                    api_resp = item
                    corr_id = api_resp.corr_id
                    resp = api_resp.resp
                    
                    if corr_id:
                        req = client.sent_commands.get(corr_id)
                        if req:
                            del client.sent_commands[corr_id]
                            req.resolve(resp)
                        else:
                            # TODO: send error to errQ?
                            print("No command sent for chat response: ", api_resp)
                    else:
                        await client.msg_q.enqueue(resp)
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            client._connected = False
    
    async def send_chat_cmd_str(self, cmd: str) -> ChatResponse:
        """Send a chat command as a string."""
        self.client_corr_id += 1
        corr_id = str(self.client_corr_id)
        t = ChatSrvRequest(corr_id, cmd)
        
        # Create future for the response
        future = asyncio.Future()
        
        def resolve(resp):
            if not future.done():
                future.set_result(resp)
        
        def reject(err=None):
            if not future.done():
                future.set_exception(err if err else Exception("Unknown error"))
        
        self.sent_commands[corr_id] = Request(resolve, reject)
        
        # Fire and forget the write operation
        asyncio.create_task(self.transport.write(t))
        
        # Wait for the response
        return await future
    
    async def send_chat_command(self, command: ChatCommand) -> ChatResponse:
        """Send a chat command."""
        return await self.send_chat_cmd_str(cmd_string(command))
    
    async def disconnect(self) -> None:
        """Disconnect from the chat server."""
        await self.transport.close()
        if self.client and not self.client.done():
            await self.client
    
    async def api_get_active_user(self) -> Optional[User]:
        """Get the active user."""
        r = await self.send_chat_command({"type": "showActiveUser"})
        if r["type"] == "activeUser":
            return r["user"]
        elif r["type"] == "chatCmdError":
            if (r["chatError"]["type"] == "error" and 
                r["chatError"]["errorType"]["type"] == "noActiveUser"):
                return None
            raise ChatCommandError("Unexpected response error", r)
        else:
            raise ChatCommandError("Unexpected response", r)
    
    async def api_create_active_user(self, 
                                    profile: Optional[Profile] = None, 
                                    same_servers: bool = True, 
                                    past_timestamp: bool = False) -> User:
        """Create an active user."""
        r = await self.send_chat_command({
            "type": "createActiveUser", 
            "profile": profile, 
            "sameServers": same_servers, 
            "pastTimestamp": past_timestamp
        })
        if r["type"] == "activeUser":
            return r["user"]
        raise ChatCommandError("Unexpected response", r)
    
    async def api_start_chat(self) -> None:
        """Start the chat."""
        r = await self.send_chat_command({"type": "startChat"})
        if r["type"] not in ["chatStarted", "chatRunning"]:
            raise ChatCommandError("Error starting chat", r)
    
    async def api_stop_chat(self) -> None:
        """Stop the chat."""
        r = await self.send_chat_command({"type": "apiStopChat"})
        if r["type"] != "chatStopped":
            raise ChatCommandError("Error stopping chat", r)
    
    async def api_set_incognito(self, incognito: bool) -> None:
        """Set incognito mode."""
        return await self.ok_chat_command({"type": "setIncognito", "incognito": incognito})
    
    async def enable_address_auto_accept(self, 
                                        accept_incognito: bool = False, 
                                        auto_reply: Optional[MsgContent] = None) -> None:
        """Enable auto-accept for contact requests."""
        r = await self.send_chat_command({
            "type": "addressAutoAccept", 
            "autoAccept": {
                "acceptIncognito": accept_incognito, 
                "autoReply": auto_reply
            }
        })
        if r["type"] != "userContactLinkUpdated":
            raise ChatCommandError("Error changing user contact address mode", r)
    
    async def disable_address_auto_accept(self) -> None:
        """Disable auto-accept for contact requests."""
        r = await self.send_chat_command({"type": "addressAutoAccept"})
        if r["type"] != "userContactLinkUpdated":
            raise ChatCommandError("Error changing user contact address mode", r)
    
    async def api_get_chats(self, user_id: int) -> List[Chat]:
        """Get chats for a user."""
        r = await self.send_chat_command({"type": "apiGetChats", "userId": user_id})
        if r["type"] == "apiChats":
            return r["chats"]
        raise ChatCommandError("Error loading chats", r)
    
    async def api_get_chat(self, 
                          chat_type: ChatType, 
                          chat_id: int, 
                          pagination: Dict[str, Any] = None, 
                          search: Optional[str] = None) -> Chat:
        """Get a specific chat."""
        if pagination is None:
            pagination = {"count": 100}
        
        r = await self.send_chat_command({
            "type": "apiGetChat", 
            "chatType": chat_type.value, 
            "chatId": chat_id, 
            "pagination": pagination, 
            "search": search
        })
        if r["type"] == "apiChat":
            return r["chat"]
        raise ChatCommandError("Error loading chat", r)
    
    async def api_send_messages(self, 
                              chat_type: ChatType, 
                              chat_id: int, 
                              messages: List[ComposedMessage],
                              is_live: bool = False) -> List[AChatItem]:
        """Send messages to a chat."""
        r = await self.send_chat_command({
            "type": "apiSendMessage", 
            "chatType": chat_type.value,  # Use the enum value
            "chatId": chat_id, 
            "liveMessage": is_live,
            "messages": messages
        })
        if r["type"] == "newChatItems":
            return r["chatItems"]
        raise ChatCommandError("Unexpected response", r)
    
    async def api_send_text_message(self, 
                                  chat_type: ChatType, 
                                  chat_id: int, 
                                  text: str,
                                  live: bool = False,
                                  ttl: Optional[int] = None) -> List[AChatItem]:
        """Send a text message to a chat."""
        if live:
            # Build a live message using the live text structure
            message = {
                "msgContent": {
                    "type": "liveText",
                    "text": text,
                    "liveType": "start"  # Use "start" to begin a live message session
                },
                "ttl": ttl
            }
        else:
            # Build a standard text message
            message = {
                "msgContent": {
                    "type": "text",
                    "text": text
                }
            }
        return await self.api_send_messages(
            chat_type, 
            chat_id, 
            [message],
            is_live=live
        )
    
    async def api_update_chat_item(self, 
                                 chat_type: ChatType, 
                                 chat_id: int, 
                                 chat_item_id: ChatItemId, 
                                 msg_content: MsgContent) -> ChatItem:
        """Update a chat item."""
        is_live = msg_content.get("type") == "liveText"
        r = await self.send_chat_command({
            "type": "apiUpdateChatItem", 
            "chatType": chat_type.value, 
            "chatId": chat_id, 
            "chatItemId": chat_item_id, 
            "msgContent": msg_content,
            "liveMessage": is_live
        })
        if r["type"] == "chatItemUpdated":
            return r["chatItem"]["chatItem"]
        raise ChatCommandError("Error updating chat item", r)
    
    async def api_delete_chat_item(self, 
                                 chat_type: ChatType, 
                                 chat_id: int, 
                                 chat_item_id: int, 
                                 delete_mode: DeleteMode) -> Optional[ChatItem]:
        """Delete a chat item."""
        r = await self.send_chat_command({
            "type": "apiDeleteChatItem", 
            "chatType": chat_type.value, 
            "chatId": chat_id, 
            "chatItemId": chat_item_id, 
            "deleteMode": delete_mode.value
        })
        if r["type"] == "chatItemDeleted":
            return r.get("toChatItem", {}).get("chatItem")
        raise ChatCommandError("Error deleting chat item", r)
    
    async def api_create_link(self) -> str:
        """Create a connection request link."""
        r = await self.send_chat_command({"type": "addContact"})
        if r["type"] == "invitation":
            return r["connReqInvitation"]
        raise ChatCommandError("Error creating link", r)
    
    async def api_connect(self, conn_req: str) -> ConnReqType:
        """Connect using a connection request."""
        r = await self.send_chat_command({"type": "connect", "connReq": conn_req})
        if r["type"] == "sentConfirmation":
            return ConnReqType.Invitation
        elif r["type"] == "sentInvitation":
            return ConnReqType.Contact
        else:
            raise ChatCommandError("Connection error", r)
    
    async def api_delete_chat(self, chat_type: ChatType, chat_id: int) -> None:
        """Delete a chat."""
        r = await self.send_chat_command({
            "type": "apiDeleteChat", 
            "chatType": chat_type.value, 
            "chatId": chat_id
        })
        
        if chat_type == ChatType.Direct and r["type"] == "contactDeleted":
            return
        elif chat_type == ChatType.Group and r["type"] == "groupDeletedUser":
            return
        elif chat_type == ChatType.ContactRequest and r["type"] == "contactConnectionDeleted":
            return
        
        raise ChatCommandError("Error deleting chat", r)
    
    async def api_clear_chat(self, chat_type: ChatType, chat_id: int) -> ChatInfo:
        """Clear a chat's history."""
        r = await self.send_chat_command({
            "type": "apiClearChat", 
            "chatType": chat_type.value, 
            "chatId": chat_id
        })
        if r["type"] == "chatCleared":
            return r["chatInfo"]
        raise ChatCommandError("Error clearing chat", r)
    
    async def api_update_profile(self, user_id: int, profile: Profile) -> Optional[Profile]:
        """Update a user profile."""
        r = await self.send_chat_command({
            "type": "apiUpdateProfile", 
            "userId": user_id, 
            "profile": profile
        })
        if r["type"] == "userProfileNoChange":
            return None
        elif r["type"] == "userProfileUpdated":
            return r["toProfile"]
        else:
            raise ChatCommandError("Error updating profile", r)
    
    async def api_set_contact_alias(self, contact_id: int, local_alias: str) -> Contact:
        """Set an alias for a contact."""
        r = await self.send_chat_command({
            "type": "apiSetContactAlias", 
            "contactId": contact_id, 
            "localAlias": local_alias
        })
        if r["type"] == "contactAliasUpdated":
            return r["toContact"]
        raise ChatCommandError("Error updating contact alias", r)
    
    async def api_create_user_address(self) -> str:
        """Create a user contact address."""
        r = await self.send_chat_command({"type": "createMyAddress"})
        if r["type"] == "userContactLinkCreated":
            return r["connLinkContact"]["connShortLink"]
        raise ChatCommandError("Error creating user address", r)
    
    async def api_delete_user_address(self) -> None:
        """Delete a user contact address."""
        r = await self.send_chat_command({"type": "deleteMyAddress"})
        if r["type"] == "userContactLinkDeleted":
            return
        raise ChatCommandError("Error deleting user address", r)
    
    async def api_get_user_address(self) -> Optional[str]:
        """Get the user's contact address."""
        r = await self.send_chat_command({"type": "showMyAddress"})
        if r["type"] == "userContactLink":
            link = r["contactLink"]
            if "connLinkContact" in link:
                return link["connLinkContact"]["connFullLink"]
            return r["contactLink"]["connReqContact"]
        elif (r["type"] == "chatCmdError" and 
              r["chatError"]["type"] == "errorStore" and 
              r["chatError"]["storeError"]["type"] == "userContactLinkNotFound"):
            return None
        else:
            raise ChatCommandError("Error loading user address", r)
    
    async def api_accept_contact_request(self, contact_req_id: int) -> Contact:
        """Accept a contact request."""
        r = await self.send_chat_command({
            "type": "apiAcceptContact", 
            "contactReqId": contact_req_id
        })
        if r["type"] == "acceptingContactRequest":
            return r["contact"]
        raise ChatCommandError("Error accepting contact request", r)
    
    async def api_reject_contact_request(self, contact_req_id: int) -> None:
        """Reject a contact request."""
        r = await self.send_chat_command({
            "type": "apiRejectContact", 
            "contactReqId": contact_req_id
        })
        if r["type"] == "contactRequestRejected":
            return
        raise ChatCommandError("Error rejecting contact request", r)
    
    async def api_chat_read(self, 
                          chat_type: ChatType, 
                          chat_id: int, 
                            ids: Union[int,List[int]]) -> None:
        """Mark chat items as read."""
        if ids:
            return await self.ok_chat_command({
                "type": "apiChatItemsRead", 
                "chatType": chat_type.value, 
                "chatId": chat_id, 
                "msgIds": ids
            })
        else:
            return await self.ok_chat_command({
                "type": "apiChatRead", 
                "chatType": chat_type.value, 
                "chatId": chat_id, 
            })
    
    async def api_contact_info(self, contact_id: int) -> Tuple[Optional[ConnectionStats], Optional[Profile]]:
        """Get information about a contact."""
        r = await self.send_chat_command({
            "type": "apiContactInfo", 
            "contactId": contact_id
        })
        if r["type"] == "contactInfo":
            return r.get("connectionStats"), r.get("customUserProfile")
        raise ChatCommandError("Error getting contact info", r)
    
    async def api_group_member_info(self, group_id: int, member_id: int) -> Optional[ConnectionStats]:
        """Get information about a group member."""
        r = await self.send_chat_command({
            "type": "apiGroupMemberInfo", 
            "groupId": group_id, 
            "memberId": member_id
        })
        if r["type"] == "groupMemberInfo":
            return r.get("connectionStats_")
        raise ChatCommandError("Error getting group info", r)
    
    async def api_receive_file(self, file_id: int) -> AChatItem:
        """Accept a file transfer."""
        r = await self.send_chat_command({
            "type": "receiveFile", 
            "fileId": file_id
        })
        if r["type"] == "rcvFileAccepted":
            return r["chatItem"]
        raise ChatCommandError("Error receiving file", r)
    
    async def api_new_group(self, group_profile: GroupProfile) -> GroupInfo:
        """Create a new group."""
        r = await self.send_chat_command({
            "type": "newGroup", 
            "groupProfile": group_profile
        })
        if r["type"] == "groupCreated":
            return r["groupInfo"]
        raise ChatCommandError("Error creating group", r)
    
    async def api_add_member(self, 
                           group_id: int, 
                           contact_id: int, 
                           member_role: GroupMemberRole) -> GroupMember:
        """Add a member to a group."""
        r = await self.send_chat_command({
            "type": "apiAddMember", 
            "groupId": group_id, 
            "contactId": contact_id, 
            "memberRole": member_role
        })
        if r["type"] == "sentGroupInvitation":
            return r["member"]
        raise ChatCommandError("Error adding member", r)
    
    async def api_join_group(self, group_id: int) -> GroupInfo:
        """Join a group."""
        r = await self.send_chat_command({
            "type": "apiJoinGroup", 
            "groupId": group_id
        })
        if r["type"] == "userAcceptedGroupSent":
            return r["groupInfo"]
        raise ChatCommandError("Error joining group", r)
    
    async def api_remove_member(self, group_id: int, member_id: int) -> GroupMember:
        """Remove a member from a group."""
        r = await self.send_chat_command({
            "type": "apiRemoveMember", 
            "groupId": group_id, 
            "memberId": member_id
        })
        if r["type"] == "userDeletedMember":
            return r["member"]
        raise ChatCommandError("Error removing member", r)
    
    async def api_leave_group(self, group_id: int) -> GroupInfo:
        """Leave a group."""
        r = await self.send_chat_command({
            "type": "apiLeaveGroup", 
            "groupId": group_id
        })
        if r["type"] == "leftMemberUser":
            return r["groupInfo"]
        raise ChatCommandError("Error leaving group", r)
    
    async def api_list_members(self, group_id: int) -> List[GroupMember]:
        """List members of a group."""
        r = await self.send_chat_command({
            "type": "apiListMembers", 
            "groupId": group_id
        })
        if r["type"] == "groupMembers":
            return r["group"]["members"]
        raise ChatCommandError("Error getting group members", r)
    
    async def api_update_group(self, group_id: int, group_profile: GroupProfile) -> GroupInfo:
        """Update a group profile."""
        r = await self.send_chat_command({
            "type": "apiUpdateGroupProfile", 
            "groupId": group_id, 
            "groupProfile": group_profile
        })
        if r["type"] == "groupUpdated":
            return r["toGroup"]
        raise ChatCommandError("Error updating group", r)
    
    async def ok_chat_command(self, command: ChatCommand) -> None:
        """Send a command and expect an 'ok' response."""
        r = await self.send_chat_command(command)
        if r["type"] != "itemsReadForChat":
            raise ChatCommandError(f"{command['type']} command error", r)
    
    @property
    def connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected
