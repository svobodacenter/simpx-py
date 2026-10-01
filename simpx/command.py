from enum import Enum, auto
from typing import Union, Optional, List, Dict, Any, Literal, TypedDict, overload
from dataclasses import dataclass, field

class ChatType(str, Enum):
    """Types of chats."""
    Direct = "@"
    Group = "#"
    ContactRequest = "<@"

class GroupMemberRole(str, Enum):
    """Role of a group member."""
    Member = "member"
    Admin = "admin"
    Owner = "owner"

class DeleteMode(str, Enum):
    """Mode for deleting chat items."""
    Broadcast = "broadcast"
    Internal = "internal"

class ServerProtocol(str, Enum):
    """Protocol for servers."""
    SMP = "smp"
    XFTP = "xftp"

# Type alias for chat item IDs
ChatItemId = int

class SimplePreference(TypedDict):
    """Simple allowed/disabled preference."""
    allow: str

class ChatBotCommand(TypedDict, total=False):
    """A bot command shown in the apps' commands menu."""
    type: Literal["command"]
    keyword: str
    label: str
    params: Optional[str]

class ChatBotCommandMenu(TypedDict):
    """A nested menu of bot commands shown in the apps' commands menu."""
    type: Literal["menu"]
    label: str
    commands: List[ChatBotCommand]

class Preferences(TypedDict, total=False):
    """Partial chat preferences."""
    commands: Optional[List[ChatBotCommand]]
    calls: SimplePreference
    voice: SimplePreference
    files: SimplePreference

class Profile(TypedDict, total=False):
    """User profile information."""
    displayName: str
    fullName: str
    shortDescr: Optional[str]
    description: Optional[str]
    image: Optional[str]
    contactLink: Optional[str]
    preferences: Optional[Preferences]
    peerType: Optional[str]

class LocalProfile(TypedDict, total=False):
    """User's local profile information."""
    profileId: int
    displayName: str
    fullName: str
    image: Optional[str]
    contactLink: Optional[str]
    localAlias: str

class LinkPreview(TypedDict):
    """Link preview information."""
    uri: str
    title: str
    description: str
    image: str

class MCText(TypedDict):
    """Text message content."""
    type: Literal["text"]
    text: str

class MCLink(TypedDict):
    """Link message content."""
    type: Literal["link"]
    text: str
    preview: LinkPreview

class MCImage(TypedDict):
    """Image message content."""
    type: Literal["image"]
    text: str
    image: str  # image preview as base64 encoded data string

class MCFile(TypedDict):
    """File message content."""
    type: Literal["file"]
    text: str

class MCLiveText(TypedDict):
    """Live text message content."""
    type: Literal["liveText"]
    text: str
    liveType: str
    metadata: Optional[Dict[str, Any]]

class LiveMessageType(str, Enum):
    """Types of live messages."""
    START = "start"
    UPDATE = "update"
    END = "end"

class MCUnknown(TypedDict):
    """Unknown message content."""
    type: str
    text: str

# Union type for message content
MsgContent = Union[MCText, MCLink, MCImage, MCFile, MCLiveText, MCUnknown]

class ComposedMessage(TypedDict, total=False):
    """A message to be sent."""
    msgContent: MsgContent
    filePath: Optional[str]
    quotedItemId: Optional[ChatItemId]
    liveMessage: Optional[bool]
    ttl: Optional[int]
    
class ChatPagination(TypedDict, total=False):
    """Pagination for chat messages."""
    count: int
    after: Optional[ChatItemId]
    before: Optional[ChatItemId]

class ServerCfg(TypedDict):
    """Server configuration."""
    server: str
    preset: bool
    tested: Optional[bool]
    enabled: bool

class GroupProfile(TypedDict):
    """Group profile information."""
    displayName: str
    fullName: str
    image: Optional[str]

class AutoAccept(TypedDict, total=False):
    """Auto-accept settings for contact requests."""
    acceptIncognito: bool
    autoReply: Optional[MsgContent]

class ArchiveConfig(TypedDict, total=False):
    """Archive configuration."""
    archivePath: str
    disableCompression: Optional[bool]
    parentTempDirectory: Optional[str]

# Base class for all chat commands
class IChatCommand(TypedDict):
    """Base interface for all chat commands."""
    type: str

# Command type definitions
class ShowActiveUser(IChatCommand):
    type: Literal["showActiveUser"]

class CreateActiveUser(IChatCommand, total=False):
    type: Literal["createActiveUser"]
    profile: Optional[Profile]
    sameServers: bool
    pastTimestamp: bool

class ListUsers(IChatCommand):
    type: Literal["listUsers"]

class StartChat(IChatCommand, total=False):
    type: Literal["startChat"]
    subscribeConnections: Optional[bool]
    enableExpireChatItems: Optional[bool]
    startXFTPWorkers: Optional[bool]

class APIStopChat(IChatCommand):
    type: Literal["apiStopChat"]

class SetIncognito(IChatCommand):
    type: Literal["setIncognito"]
    incognito: bool

class APIGetChats(IChatCommand, total=False):
    type: Literal["apiGetChats"]
    userId: int
    pendingConnections: Optional[bool]

class APIGetChat(IChatCommand):
    type: Literal["apiGetChat"]
    chatType: ChatType
    chatId: int
    pagination: ChatPagination
    search: Optional[str]

class APISendMessage(IChatCommand):
    type: Literal["apiSendMessage"]
    chatType: ChatType
    chatId: int
    messages: List[ComposedMessage]
    liveMessage: bool = False

class APIUpdateChatItem(IChatCommand):
    type: Literal["apiUpdateChatItem"]
    chatType: ChatType
    chatId: int
    chatItemId: ChatItemId
    msgContent: MsgContent
    liveMessage: bool = False

class APIDeleteChatItem(IChatCommand):
    type: Literal["apiDeleteChatItem"]
    chatType: ChatType
    chatId: int
    chatItemId: ChatItemId
    deleteMode: DeleteMode

class APIChatRead(IChatCommand, total=False):
    type: Literal["apiChatRead"]
    chatType: ChatType
    chatId: int

class APIChatItemsRead(IChatCommand, total=False):
    type: Literal["apiChatItemsRead"]
    chatType: ChatType
    chatId: int
    msgIds: Union[int, List[int]]

class APIDeleteChat(IChatCommand):
    type: Literal["apiDeleteChat"]
    chatType: ChatType
    chatId: int

class APIClearChat(IChatCommand):
    type: Literal["apiClearChat"]
    chatType: ChatType
    chatId: int

class APIAcceptContact(IChatCommand):
    type: Literal["apiAcceptContact"]
    contactReqId: int

class APIRejectContact(IChatCommand):
    type: Literal["apiRejectContact"]
    contactReqId: int

class APIUpdateProfile(IChatCommand):
    type: Literal["apiUpdateProfile"]
    userId: int
    profile: Profile

class APISetContactAlias(IChatCommand):
    type: Literal["apiSetContactAlias"]
    contactId: int
    localAlias: str

class NewGroup(IChatCommand):
    type: Literal["newGroup"]
    groupProfile: GroupProfile

class APIAddMember(IChatCommand):
    type: Literal["apiAddMember"]
    groupId: int
    contactId: int
    memberRole: GroupMemberRole

class APIJoinGroup(IChatCommand):
    type: Literal["apiJoinGroup"]
    groupId: int

class APIRemoveMember(IChatCommand):
    type: Literal["apiRemoveMember"]
    groupId: int
    memberId: int

class APILeaveGroup(IChatCommand):
    type: Literal["apiLeaveGroup"]
    groupId: int

class APIListMembers(IChatCommand):
    type: Literal["apiListMembers"]
    groupId: int

class APIUpdateGroupProfile(IChatCommand):
    type: Literal["apiUpdateGroupProfile"]
    groupId: int
    groupProfile: GroupProfile

class APIContactInfo(IChatCommand):
    type: Literal["apiContactInfo"]
    contactId: int

class APIGroupMemberInfo(IChatCommand):
    type: Literal["apiGroupMemberInfo"]
    groupId: int
    memberId: int

class AddContact(IChatCommand):
    type: Literal["addContact"]

class Connect(IChatCommand):
    type: Literal["connect"]
    connReq: str

class CreateMyAddress(IChatCommand):
    type: Literal["createMyAddress"]

class DeleteMyAddress(IChatCommand):
    type: Literal["deleteMyAddress"]

class ShowMyAddress(IChatCommand):
    type: Literal["showMyAddress"]

class AddressAutoAccept(IChatCommand, total=False):
    type: Literal["addressAutoAccept"]
    autoAccept: Optional[AutoAccept]

class ReceiveFile(IChatCommand, total=False):
    type: Literal["receiveFile"]
    fileId: int
    filePath: Optional[str]

# Union type for all chat commands
ChatCommand = Union[
    ShowActiveUser,
    CreateActiveUser,
    ListUsers,
    StartChat,
    APIStopChat,
    SetIncognito,
    APIGetChats,
    APIGetChat,
    APISendMessage,
    APIUpdateChatItem,
    APIDeleteChatItem,
    APIChatRead,
    APIChatItemsRead,
    APIDeleteChat,
    APIClearChat,
    APIAcceptContact,
    APIRejectContact,
    APIUpdateProfile,
    APISetContactAlias,
    NewGroup,
    APIAddMember,
    APIJoinGroup,
    APIRemoveMember,
    APILeaveGroup,
    APIListMembers,
    APIUpdateGroupProfile,
    APIContactInfo,
    APIGroupMemberInfo,
    AddContact,
    Connect,
    CreateMyAddress,
    DeleteMyAddress,
    ShowMyAddress,
    AddressAutoAccept,
    ReceiveFile,
]

# Helper functions for command string formatting
def maybe(value: Optional[Any]) -> str:
    """Format optional value as string with leading space if present."""
    return f" {value}" if value is not None else ""

def maybe_json(value: Optional[Any]) -> str:
    """Format optional value as JSON string with leading space if present."""
    import json
    return f' json {json.dumps(value)}' if value is not None else ""

def on_off(value: Optional[bool], default: bool = True) -> str:
    """Convert boolean to 'on' or 'off' string."""
    if value is None:
        value = default
    return "on" if value else "off"

def pagination_str(cp: ChatPagination) -> str:
    """Format pagination parameters as string."""
    if 'after' in cp:
        base = f" after={cp['after']}"
    elif 'before' in cp:
        base = f" before={cp['before']}"
    else:
        base = ""
    return f"{base} count={cp['count']}"

def auto_accept_str(auto_accept: Optional[AutoAccept]) -> str:
    """Format auto-accept settings as string."""
    if not auto_accept:
        return "off"
    
    import json
    msg = auto_accept.get("autoReply")
    result = "on"
    
    if auto_accept.get("acceptIncognito"):
        result += " incognito=on"
    
    if msg:
        result += f" json {json.dumps(msg)}"
    
    return result

def wrappify(d):
    if 'msgContent' in d:
        return {'msgContent':d['msgContent'], 'mentions':{}}

def cmd_string(cmd: ChatCommand) -> str:
    """Convert a command object to a string."""
    import json
    
    cmd_type = cmd["type"]

    # Command string builders using a dictionary for dispatch
    cmd_builders = {
        "showActiveUser": lambda _: "/u",
        "createActiveUser": lambda c: f"/_create user {json.dumps({'profile': c.get('profile'), 'sameServers': c['sameServers'], 'pastTimestamp': c['pastTimestamp']})}",
        "listUsers": lambda _: "/users",
        "startChat": lambda c: f"/_start subscribe={on_off(c.get('subscribeConnections'), False)} expire={on_off(c.get('enableExpireChatItems'), False)}",
        "apiStopChat": lambda _: "/_stop",
        "setIncognito": lambda c: f"/incognito {on_off(c['incognito'])}",
        "apiGetChats": lambda c: f"/_get chats pcc={on_off(c.get('pendingConnections'), False)}",
        "apiGetChat": lambda c: f"/_get chat {c['chatType']}{c['chatId']}{pagination_str(c['pagination'])}" + (f" {c['search']}" if c.get('search') else ""),

        "apiSendMessage": lambda c: f"/_send {c['chatType']}{c['chatId']}" + (" live=on" if c.get("liveMessage") else "") + f" json {json.dumps(c['messages'])}",
        #"apiSendMessage": lambda c: f"/_send {c['chatType']}{c['chatId']} json {json.dumps(c['messages'])}",
        "apiUpdateChatItem": lambda c: f"/_update item {c['chatType']}{c['chatId']} {c['chatItemId']}" + (" live=on" if c.get("liveMessage") else "") + f" json {json.dumps(wrappify(c))}",
        "apiDeleteChatItem": lambda c: f"/_delete item {c['chatType']}{c['chatId']} {c['chatItemId']} {c['deleteMode']}",
        "apiChatRead": lambda c: f"/_read chat {c['chatType']}{c['chatId']}" + (f" from={c['itemRange']['fromItem']} to={c['itemRange']['toItem']}" if c.get('itemRange') else ""),
        "apiChatItemsRead": lambda c: f"/_read chat items {c['chatType']}{c['chatId']} " + (str(c['msgIds']) if isinstance(c['msgIds'], int) else ' '.join(str(i) for i in c['msgIds'])),
        "apiDeleteChat": lambda c: f"/_delete {c['chatType']}{c['chatId']}",
        "apiClearChat": lambda c: f"/_clear chat {c['chatType']}{c['chatId']}",
        "apiAcceptContact": lambda c: f"/_accept {c['contactReqId']}",
        "apiRejectContact": lambda c: f"/_reject {c['contactReqId']}",
        "apiUpdateProfile": lambda c: f"/_profile {c['userId']} {json.dumps(c['profile'])}",
        "apiSetContactAlias": lambda c: f"/_set alias @{c['contactId']} {c['localAlias'].strip()}",
        "newGroup": lambda c: f"/_group {json.dumps(c['groupProfile'])}",
        "apiAddMember": lambda c: f"/_add #{c['groupId']} {c['contactId']} {c['memberRole']}",
        "apiJoinGroup": lambda c: f"/_join #{c['groupId']}",
        "apiRemoveMember": lambda c: f"/_remove #{c['groupId']} {c['memberId']}",
        "apiLeaveGroup": lambda c: f"/_leave #{c['groupId']}",
        "apiListMembers": lambda c: f"/_members #{c['groupId']}",
        "apiUpdateGroupProfile": lambda c: f"/_group_profile #{c['groupId']} {json.dumps(c['groupProfile'])}",
        "apiContactInfo": lambda c: f"/_info @{c['contactId']}",
        "apiGroupMemberInfo": lambda c: f"/_info #{c['groupId']} {c['memberId']}",
        "addContact": lambda _: "/connect",
        "connect": lambda c: f"/connect {c['connReq']}",
        "createMyAddress": lambda _: "/address",
        "deleteMyAddress": lambda _: "/delete_address",
        "showMyAddress": lambda _: "/show_address",
        "addressAutoAccept": lambda c: f"/auto_accept {auto_accept_str(c.get('autoAccept'))}",
        "receiveFile": lambda c: f"/freceive {c['fileId']}{' ' + c['filePath'] if c.get('filePath') else ''}",
    }
    
    if cmd_type in cmd_builders:
        return cmd_builders[cmd_type](cmd)
    
    raise ValueError(f"Unknown command type: {cmd_type}")
