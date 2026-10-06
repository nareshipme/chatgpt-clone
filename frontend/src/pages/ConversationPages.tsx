import { Alert, Box, Button, Container, Skeleton, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import type { Message } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Composer } from "../components/Composer";
import { MessageBubble } from "../components/MessageBubble";
import { useChat } from "../hooks/useChat";
import { useConversation } from "../hooks/useConversations";

/** Shown at "/" when no conversation is selected. */
export function EmptyChatPage() {
  const { user } = useAuth();
  return (
    <Container sx={{ py: 8 }}>
      <Typography variant="h4" gutterBottom>
        Hello, {user?.display_name}
      </Typography>
      <Typography color="text.secondary">Pick a conversation from the sidebar, or start a new chat.</Typography>
    </Container>
  );
}

const textOf = (m: Message) => m.parts.map((p) => (p.type === "text" ? p.text : "")).join("");

/** The thread, the live reply and the composer for one conversation. */
function ChatPane({ conversationId }: { conversationId: string }) {
  const chat = useChat(conversationId);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true); // follow new text only while the user is already at the bottom
  const [showJump, setShowJump] = useState(false);

  function onScroll() {
    const el = scroller.current!;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stick.current = nearBottom;
    setShowJump(!nearBottom);
  }

  function jumpToLatest() {
    const el = scroller.current!;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [chat.messages.length, chat.live?.assistantText, chat.live?.userText]);

  const empty = !chat.isLoading && chat.messages.length === 0 && !chat.live;

  return (
    <>
      <Box ref={scroller} onScroll={onScroll} sx={{ flex: 1, minHeight: 0, overflowY: "auto", position: "relative" }}>
        <Container maxWidth="md" sx={{ py: 3 }}>
          {chat.isLoading && <Skeleton variant="rounded" height={64} />}
          {chat.loadError && <Alert severity="error">Could not load this conversation&apos;s messages.</Alert>}
          {empty && (
            <Typography color="text.secondary" sx={{ mt: 4, textAlign: "center" }}>
              Send a message to start the conversation.
            </Typography>
          )}
          {chat.messages.map((m) => (
            <MessageBubble key={m.id} role={m.role} text={textOf(m)} status={m.status} />
          ))}
          {chat.live && (
            <>
              <MessageBubble role="user" text={chat.live.userText} />
              <MessageBubble role="assistant" text={chat.live.assistantText} live />
            </>
          )}
        </Container>
      </Box>
      {showJump && (
        <Box sx={{ position: "absolute", bottom: 112, left: 0, right: 0, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
          <Button variant="contained" size="small" onClick={jumpToLatest} sx={{ pointerEvents: "auto" }}>
            Jump to latest
          </Button>
        </Box>
      )}
      {chat.error && (
        <Alert severity="error" onClose={chat.dismissError} sx={{ mx: 2, mb: 1 }}>
          {chat.error}
        </Alert>
      )}
      <Composer streaming={chat.streaming} onSend={(t) => void chat.send(t)} onStop={chat.stop} />
    </>
  );
}

/** Shown at "/c/:id". */
export function ConversationPage() {
  const { conversationId } = useParams();
  const { data, isPending, error } = useConversation(conversationId);

  if (isPending) {
    return (
      <Container sx={{ py: 6 }}>
        <Skeleton width={260} height={48} />
      </Container>
    );
  }
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <Container sx={{ py: 6 }}>
        <Alert severity={notFound ? "warning" : "error"} sx={{ mb: 2 }}>
          {notFound ? "This conversation does not exist or you do not have access to it." : error.message}
        </Alert>
        <Button component={RouterLink} to="/">
          Back to start
        </Button>
      </Container>
    );
  }
  return (
    <Box sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, position: "relative" }}>
      <Box sx={{ px: 3, py: 1.5, borderBottom: 1, borderColor: "divider" }}>
        <Typography component="h1" variant="h6" noWrap>
          {data.title}
        </Typography>
      </Box>
      <ChatPane conversationId={data.id} />
    </Box>
  );
}
