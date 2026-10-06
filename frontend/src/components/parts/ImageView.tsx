import { Box, Typography } from "@mui/material";
import { useState } from "react";
import type { ImagePart } from "../../api/types";

/** The server already requires https, but the client checks again: defence in depth for something that
 *  makes the browser fetch a third-party URL. No referrer is sent and the image loads lazily. */
export function ImageView({ part }: { part: ImagePart }) {
  const [failed, setFailed] = useState(false);
  if (!/^https:\/\//i.test(part.url) || failed) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
        [image: {part.alt || "unavailable"}]
      </Typography>
    );
  }
  return (
    <Box
      component="img"
      src={part.url}
      alt={part.alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      sx={{ display: "block", maxWidth: "100%", maxHeight: 360, borderRadius: 2, my: 1 }}
    />
  );
}
