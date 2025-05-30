### WebSocket Implementation Specification for Serv Framework

---

#### **1. Core Components**
**A. WebSocket Endpoint Class**  
- Inherits from `serv.WebSocket`  
- Configured via class-level attributes:  
  ```python
  class ChatWebsocket(serv.WebSocket, using=MessagePackSerializer):
      ...
  ```
- **Key Methods**:  
  - `on_connect(request: Request)`: Async, called on connection  
  - `on_disconnect()`: Async, called on disconnect  
  - `receive_{action}(self, data: Model) -> ResponseModel`: Async methods for message handling (e.g., `receive_a_message`)  
  - `on_{exception_type}_error(self, exception: ExceptionType) -> ErrorResponseModel`: Error handlers (e.g., `on_name_error`)
  - `close(code: int, reason: str)`: Close the connection

**B. Serializers**  
- Base class: `PacketSerializer` (requires `serialize()`/`deserialize()` and `frame_type`)  
- Built-in implementations:  
  - `JSONSerializer` (text frames)  
  - `MessagePackSerializer` (binary frames)  

---

#### **2. Protocol Flow**
**Connection Lifecycle**  
1. **Handshake**: Framework validates request and initializes serializer  
2. **Mode Selection**: according to the serializer set in the `using` class parameter  
3. **Message Processing**:  
   ```
   Receive → Deserialize → Route → Handle → Serialize → Send
   ```

**Error Handling**  
Error handlers follow the format `on_(?:[a-z0-9_]+_)?error`. The error types they handle are determined by the type 
annotation of the first non-self parameter. This can be a union type and is checked using `isinstance()`.

- **Priority Order**:  
  1. Specific error handlers
  2. Built-in fallback (close connection with status 1011)  

---

#### **3. Routing & Message Dispatch**
**A. Message Routing**  
- Incoming messages are deserialized into model instances according to the possible model types defined in the handler methods.
- Message handlers are indicated by the method name format `receive_(?:[a-z0-9_]+)` and the type they handle is determined by the type annotation of the first non-self parameter (this may be a union):  
  ```python
  async def receive_a_message(self, message: Message): ...
  async def receive_a_reaction(self, reaction: Reaction): ...
  ```
  **No Match**: Raise `UnknownMessageError` → routed to error handlers  
- Handlers must return a model instance that can be serialized by the chosen serializer.
- All models must have attributes that are Python primitives or other model instances.

**B. Path Registration**
Websockets are registered like any other route. Serv handles the connection upgrade and dispatches to the appropriate WebSocket endpoint. This includes support for path parameters and query string parsing along with support for the extension.yaml declarative routers.

---

#### **4. Serialization Requirements**
| Feature              | JSON            | MessagePack     |
|----------------------|-----------------|-----------------|
| Frame Type           | Text            | Binary          |
| Return Type          | Dict → JSON     | Dict → msgpack  |
| Error Handling       | JSONDecodeError | UnpackError     |

Serialization/deserialization errors must be caught and re-raised as `SerializationError` or `DeserializationError`.
---

#### **5. Developer-Facing Rules**
- **Method Naming**:  
  - `receive_{action}`: Reserved prefix for message handlers 
  - `on_{optional_label}_error`: Exception type determined by parameter annotation  
- **Type Enforcement**:  
  - All handler parameters must be
  - Return types must match the method's return type annotation (possibly a union)
- **Async Requirement**: All handlers must be `async`

---

#### **6. Implementation Milestones**
1. **Base WebSocket Class**  
   - Lifecycle hooks  
   - Serializer integration  
   - Async iterator wrapper  

2. **Serializer System**  
   - ABC with validation  
   - JSON/MessagePack implementations  

3. **Dispatcher**  
   - Type-based routing  
   - Error handling pipeline  

4. **Path Registration**  
   - Decorator support (`@websocket_route("/path")`)  
   - Integration with Serv's router  

---

#### **7. Edge Cases & Testing**
- **Malformed Data**: Verify all serializers throw framework-catchable errors  
- **Union Types**: Test parameter resolution

This spec enables type-safe WebSocket handling while maintaining Serv's minimalist ethos. The developer should focus on the dispatcher and serializer integration first, then error handling.