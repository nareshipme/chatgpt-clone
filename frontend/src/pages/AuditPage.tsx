import { Alert, Container, Skeleton, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { listAudit } from "../api/actions";
import { useUserId } from "../hooks/useConversations";

const LABELS: Record<string, string> = {
  "action.proposed": "Proposed",
  "action.approved": "Approved",
  "action.dismissed": "Dismissed",
  "action.expired": "Expired",
};

/** Read-only trail of what was proposed and decided in the signed-in user's company. */
export default function AuditPage() {
  const userId = useUserId();
  const audit = useQuery({ queryKey: ["audit", userId], queryFn: listAudit, retry: false });

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography component="h1" variant="h5" gutterBottom>
        Audit log
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Who proposed and decided what, newest first. This log can be read but never edited.
      </Typography>
      {audit.isPending && <Skeleton variant="rounded" height={120} />}
      {audit.isError && (
        <Alert severity={audit.error instanceof ApiError && audit.error.status === 403 ? "info" : "error"}>
          {audit.error instanceof ApiError ? audit.error.message : "Could not load the audit log."}
        </Alert>
      )}
      {audit.data && audit.data.items.length === 0 && <Typography color="text.secondary">Nothing has been proposed yet.</Typography>}
      {audit.data && audit.data.items.length > 0 && (
        <Table size="small" aria-label="Audit events">
          <TableHead>
            <TableRow>
              <TableCell>When</TableCell>
              <TableCell>Who</TableCell>
              <TableCell>Event</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {audit.data.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell>{new Date(e.created_at).toLocaleString()}</TableCell>
                <TableCell>{e.actor_name ?? "System"}</TableCell>
                <TableCell>{LABELS[e.action] ?? e.action}</TableCell>
                <TableCell>{String((e.payload as { summary?: string }).summary ?? "")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Container>
  );
}
