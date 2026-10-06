import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { useAuth } from "../auth/AuthContext";

// Placeholder until the chat slice. Proves the auth gate, the silent refresh and logout end to end.
export default function HomePage() {
  const { user, logout } = useAuth();
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="static" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            ChatGPT Clone
          </Typography>
          <Typography sx={{ mr: 2 }} color="text.secondary">
            {user?.display_name}
          </Typography>
          <Button onClick={() => void logout()}>Sign out</Button>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 6 }}>
        <Typography variant="h5" gutterBottom>
          Hello, {user?.display_name}
        </Typography>
        <Typography color="text.secondary">
          You are signed in. Conversations and streaming chat arrive in the next slices.
        </Typography>
      </Container>
    </Box>
  );
}
