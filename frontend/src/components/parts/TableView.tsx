import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import type { TablePart } from "../../api/types";

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
      <TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2, bgcolor: "background.paper" }}>
        <Table size="small" aria-label={part.title ?? "Table"}>
          <TableHead>
            <TableRow>
              {part.columns.map((c, i) => (
                <TableCell key={i} align={numeric[i] ? "right" : "left"} sx={{ fontWeight: 600 }}>
                  {c}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {part.rows.map((row, r) => (
              <TableRow key={r}>
                {row.map((cell, i) => (
                  <TableCell key={i} align={numeric[i] ? "right" : "left"}>
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
