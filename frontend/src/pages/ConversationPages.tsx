import { Alert, Box, Button, Container, Skeleton, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { Link as RouterLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Composer } from "../components/Composer";
import { MessageBubble } from "../components/MessageBubble";
import { useChat } from "../hooks/useChat";
import { useConversation, useCreateConversation } from "../hooks/useConversations";
import { usePersonas } from "../hooks/usePersonas";
import { StarterChips } from "../components/StarterChips";
import { textOf } from "../lib/parts";

/** Shown at "/" when no conversation is selected. */
export function EmptyChatPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const create = useCreateConversation();
  const personas = usePersonas();
  const starters = personas.data?.find((p) => p.selected)?.starters ?? [];

  async function start(text: string) {
    const created = await create.mutateAsync(undefined);
    navigate(`/c/${created.id}`, { state: { starter: text } }); // the chat sends it as its first message
  }

  return (
    <Container sx={{ py: 8 }}>
      <Typography variant="h4" gutterBottom>
        Hello, {user?.display_name}
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Pick a conversation from the sidebar, or start a new chat.
      </Typography>
      <StarterChips starters={starters} onPick={(t) => void start(t)} disabled={create.isPending} />
    </Container>
  );
}

/** The thread, the live reply and the composer for one conversation. */
function ChatPane({ conversationId }: { conversationId: string }) {
  const chat = useChat(conversationId);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true); // follow new text only while the user is already at the bottom
  const [showJump, setShowJump] = useState(false);
  const personas = usePersonas();
  const starters = personas.data?.find((p) => p.selected)?.starters ?? [];
  const location = useLocation();
  const navigate = useNavigate();
  const sentStarter = useRef(false);

  // A starter picked on the home page arrives as router state: send it once, then drop it so a reload does not resend.
  useEffect(() => {
    const starter = (location.state as { starter?: string } | null)?.starter;
    if (starter && !sentStarter.current) {
      sentStarter.current = true;
      navigate(location.pathname, { replace: true, state: null });
      void chat.send(starter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
  }, [chat.messages.length, chat.live?.parts, chat.live?.userText]);

  const lastQuestion = [...chat.messages].reverse().find((m) => m.role === "user");
  const lastQuestionText = lastQuestion ? textOf(lastQuestion.parts) : "";
  const empty = !chat.isLoading && chat.messages.length === 0 && !chat.live;

  return (
    <>
      <Box ref={scroller} onScroll={onScroll} sx={{ flex: 1, minHeight: 0, overflowY: "auto", position: "relative" }}>
        <Container maxWidth="md" sx={{ py: 3 }}>
          {chat.isLoading && <Skeleton variant="rounded" height={64} />}
          {chat.loadError && <Alert severity="error">Could not load this conversation&apos;s messages.</Alert>}
          {empty && (
            <Box sx={{ mt: 4, textAlign: "center" }}>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Send a message to start the conversation.
              </Typography>
              <StarterChips starters={starters} onPick={(t) => void chat.send(t)} />
            </Box>
          )}
          {chat.messages.map((m, i) => {
            const next = chat.messages[i + 1];
            const isLast = i === chat.messages.length - 1;
            return (
              <MessageBubble
                key={m.id}
                role={m.role}
                parts={m.parts}
                status={m.status}
                // Choice buttons work only on the newest finished reply with nothing after it; older menus are history.
                actionsActive={m.role === "assistant" && isLast && !chat.streaming && m.status === "complete"}
                answeredWith={next?.role === "user" ? textOf(next.parts) : isLast ? chat.live?.userText : undefined}
                onChoose={(value) => void chat.send(value)}
              />
            );
          })}
          {chat.live && (
            <>
              <MessageBubble role="user" text={chat.live.userText} />
              <MessageBubble role="assistant" parts={chat.live.parts} tools={chat.live.tools} live />
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
        <Alert
          severity="error"
          onClose={chat.dismissError}
          sx={{ mx: 2, mb: 1 }}
          action={
            lastQuestionText && !chat.streaming ? (
              <Button color="inherit" size="small" onClick={() => void chat.send(lastQuestionText)}>
                Retry
              </Button>
            ) : undefined
          }
        >
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
