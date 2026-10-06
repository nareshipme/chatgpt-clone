import AddIcon from "@mui/icons-material/Add";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import SearchIcon from "@mui/icons-material/Search";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Skeleton,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import type { Conversation } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  useConversationList,
  useCreateConversation,
  useDebounced,
  useDeleteConversation,
  useRenameConversation,
} from "../hooks/useConversations";
import { DeleteDialog, RenameDialog } from "./ConversationDialogs";

const messageOf = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

interface Props {
  activeId?: string;
  onNavigate?: () => void; // lets the mobile drawer close after a selection
}

export function Sidebar({ activeId, onNavigate }: Props) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const list = useConversationList(q);
  const create = useCreateConversation();
  const rename = useRenameConversation();
  const remove = useDeleteConversation();

  const [menu, setMenu] = useState<{ anchor: HTMLElement; conversation: Conversation } | null>(null);
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [deleting, setDeleting] = useState<Conversation | null>(null);

  const items = list.data?.pages.flatMap((p) => p.items) ?? [];

  async function newChat() {
    const created = await create.mutateAsync(undefined);
    navigate(`/c/${created.id}`);
    onNavigate?.();
  }

  function open(id: string) {
    navigate(`/c/${id}`);
    onNavigate?.();
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ p: 2 }}>
        <Button fullWidth variant="contained" startIcon={<AddIcon />} onClick={newChat} disabled={create.isPending}>
          New chat
        </Button>
        {create.isError && (
          <Alert severity="error" sx={{ mt: 1 }}>
            {messageOf(create.error)}
          </Alert>
        )}
        <TextField
          fullWidth
          size="small"
          placeholder="Search conversations"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ mt: 2 }}
          slotProps={{
            htmlInput: { "aria-label": "Search conversations" },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>

      <Box sx={{ flex: 1, overflowY: "auto" }} role="navigation" aria-label="Conversations">
        {list.isPending && (
          <Box sx={{ px: 2 }}>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={44} />
            ))}
          </Box>
        )}
        {list.isError && (
          <Alert severity="error" sx={{ mx: 2 }}>
            {messageOf(list.error)}
          </Alert>
        )}
        {list.isSuccess && items.length === 0 && (
          <Typography color="text.secondary" sx={{ px: 2, py: 1 }}>
            {q ? "No conversations match your search." : "No conversations yet. Start a new chat."}
          </Typography>
        )}
        <List dense disablePadding>
          {items.map((c) => (
            <ListItem
              key={c.id}
              disablePadding
              secondaryAction={
                <IconButton
                  edge="end"
                  size="small"
                  aria-label={`Actions for ${c.title}`}
                  onClick={(e) => setMenu({ anchor: e.currentTarget, conversation: c })}
                >
                  <MoreVertIcon fontSize="small" />
                </IconButton>
              }
            >
              <ListItemButton selected={c.id === activeId} onClick={() => open(c.id)} sx={{ pr: 6 }}>
                <ListItemText primary={c.title} slotProps={{ primary: { noWrap: true } }} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        {list.hasNextPage && (
          <Box sx={{ p: 2, textAlign: "center" }}>
            <Button size="small" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
              {list.isFetchingNextPage ? <CircularProgress size={16} /> : "Load more"}
            </Button>
          </Box>
        )}
      </Box>

      <Divider />
      <Box sx={{ p: 2, display: "flex", alignItems: "center", gap: 1 }}>
        <Typography noWrap sx={{ flex: 1 }} title={user?.email}>
          {user?.display_name}
        </Typography>
        <Button size="small" onClick={() => void logout()}>
          Sign out
        </Button>
      </Box>

      <Menu anchorEl={menu?.anchor} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem
          onClick={() => {
            setRenaming(menu!.conversation);
            setMenu(null);
          }}
        >
          Rename
        </MenuItem>
        <MenuItem
          onClick={() => {
            setDeleting(menu!.conversation);
            setMenu(null);
          }}
        >
          Delete
        </MenuItem>
      </Menu>

      <RenameDialog
        conversation={renaming}
        busy={rename.isPending}
        error={rename.isError ? messageOf(rename.error) : null}
        onClose={() => {
          setRenaming(null);
          rename.reset();
        }}
        onSubmit={(title) => rename.mutate({ id: renaming!.id, title }, { onSuccess: () => setRenaming(null) })}
      />
      <DeleteDialog
        conversation={deleting}
        busy={remove.isPending}
        error={remove.isError ? messageOf(remove.error) : null}
        onClose={() => {
          setDeleting(null);
          remove.reset();
        }}
        onConfirm={() =>
          remove.mutate(deleting!.id, {
            onSuccess: () => {
              if (deleting!.id === activeId) navigate("/");
              setDeleting(null);
            },
          })
        }
      />
    </Box>
  );
}
