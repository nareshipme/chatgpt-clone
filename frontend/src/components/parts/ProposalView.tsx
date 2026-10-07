import { Alert, Box, Button, Chip, Paper, Skeleton, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { dismissAction, executeAction, getAction, type ActionRecord } from "../../api/actions";
import type { ProposalPart } from "../../api/types";
import { useUserId } from "../../hooks/useConversations";

const STATUS: Record<ActionRecord["status"], { label: string; color: "default" | "success" | "warning" }> = {
  proposed: { label: "Waiting for approval", color: "warning" },
  approved: { label: "Approved", color: "success" },
  dismissed: { label: "Dismissed", color: "default" },
  expired: { label: "Expired", color: "default" },
};

/**
 * A proposal card. The message only stores the action's id; the live status, details and whether this user may
 * decide come from the server, so the buttons can never offer something the server would refuse or that already happened.
 */
export function ProposalView({ part }: { part: ProposalPart }) {
  const qc = useQueryClient();
  const userId = useUserId();
  const key = ["actions", userId, part.action_id] as const;
  const action = useQuery({ queryKey: key, queryFn: () => getAction(part.action_id), retry: 1 });
  const decide = useMutation({
    mutationFn: (kind: "approve" | "dismiss") => (kind === "approve" ? executeAction(part.action_id) : dismissAction(part.action_id)),
    onSuccess: (updated) => {
      qc.setQueryData(key, updated);
      void qc.invalidateQueries({ queryKey: ["audit", userId] });
    },
    onError: () => void qc.invalidateQueries({ queryKey: key }), // the server's view wins: show what really happened
  });

  const a = action.data;
  const status = a ? STATUS[a.status] : null;
  const result = a?.result as { estimated_cost_usd?: number; estimated_co2e_kg?: number; note?: string } | null | undefined;

  return (
    <Paper variant="outlined" sx={{ my: 1.5, p: 2 }} aria-label="Proposed action" role="group">
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1} flexWrap="wrap">
        <Typography variant="subtitle2">Proposed action</Typography>
        {status ? <Chip size="small" label={status.label} color={status.color} /> : <Skeleton width={110} height={24} />}
      </Stack>
      <Typography sx={{ my: 1 }}>{part.summary}</Typography>

      {a?.status === "approved" && result && (
        <Box sx={{ color: "text.secondary", fontSize: 14 }}>
          {typeof result.estimated_cost_usd === "number" && <div>Estimated cost: ${result.estimated_cost_usd}</div>}
          {typeof result.estimated_co2e_kg === "number" && <div>Estimated CO2e: {result.estimated_co2e_kg} kg</div>}
          {result.note && <div>{result.note}</div>}
        </Box>
      )}
      {a?.status === "proposed" && !a.can_decide && (
        <Typography variant="body2" color="text.secondary">
          Your role can view this proposal but not approve it.
        </Typography>
      )}
      {action.isError && <Alert severity="warning">Could not load the current status of this proposal.</Alert>}
      {decide.isError && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {decide.error instanceof ApiError ? decide.error.message : "Something went wrong. Please try again."}
        </Alert>
      )}

      {a?.can_decide && (
        <Stack direction="row" gap={1} sx={{ mt: 1.5 }}>
          <Button variant="contained" size="small" onClick={() => decide.mutate("approve")} disabled={decide.isPending}>
            Approve
          </Button>
          <Button size="small" onClick={() => decide.mutate("dismiss")} disabled={decide.isPending}>
            Dismiss
          </Button>
        </Stack>
      )}
    </Paper>
  );
}
