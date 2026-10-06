import { Alert, Box, Button, Container, Skeleton, Typography } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
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

/** Shown at "/c/:id". Messages and streaming arrive in the next slice. */
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
    <Container sx={{ py: 6 }}>
      <Typography component="h1" variant="h5" gutterBottom>
        {data.title}
      </Typography>
      <Box>
        <Typography color="text.secondary">Messages and streaming responses arrive in the next slices.</Typography>
      </Box>
    </Container>
  );
}
