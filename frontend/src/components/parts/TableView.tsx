import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";
import type { TablePart } from "../../api/types";

// Short cells stay on one line (so "$84,000" and "Gulfstream Haul" never break mid-word); long text may wrap.
// The container scrolls sideways when a table is wider than the message.
const cellStyle = (text: string): SxProps<Theme> => (text.length > 40 ? { whiteSpace: "normal", minWidth: 220 } : { whiteSpace: "nowrap" });

/** Cells are rendered as text by React, which escapes everything: a cell can never inject markup. */
export function TableView({ part }: { part: TablePart }) {
  const numeric = part.columns.map((_, i) => part.rows.length > 0 && part.rows.every((r) => typeof r[i] === "number" || r[i] === null));
  return (
    <Box sx={{ my: 1.5 }}>
      {part.title && (
        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
          {part.title}
        </Typography>
      )}
      <TableContainer sx={{ overflowX: "auto", border: 1, borderColor: "divider", borderRadius: 2, bgcolor: "background.paper" }}>
        <Table size="small" aria-label={part.title ?? "Table"}>
          <TableHead>
            <TableRow>
              {part.columns.map((c, i) => (
                <TableCell key={i} align={numeric[i] ? "right" : "left"} sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>
                  {c}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {part.rows.map((row, r) => (
              <TableRow key={r}>
                {row.map((cell, i) => (
                  <TableCell key={i} align={numeric[i] ? "right" : "left"} sx={cellStyle(cell === null ? "" : String(cell))}>
                    {cell === null ? "" : String(cell)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
