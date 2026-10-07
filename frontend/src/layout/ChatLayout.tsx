import MenuIcon from "@mui/icons-material/Menu";
import { AppBar, Box, Drawer, IconButton, Toolbar, Typography, useMediaQuery } from "@mui/material";
import { ThemeProvider, useTheme } from "@mui/material/styles";
import { useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { BrandMark } from "../app/BrandMark";
import { BRAND } from "../app/brand";
import { COLORS, sidebarTheme } from "../app/theme";
import { Sidebar } from "../components/Sidebar";

const DRAWER_WIDTH = 300;

/** Sidebar + main area. The drawer is permanent on desktop and slides in on mobile. */
export default function ChatLayout() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const { conversationId } = useParams();

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <Drawer
        variant={isDesktop ? "permanent" : "temporary"}
        open={isDesktop || mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{ width: isDesktop ? DRAWER_WIDTH : 0, flexShrink: 0, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", bgcolor: COLORS.black, color: "#fff", borderRight: 0 } }}
      >
        <ThemeProvider theme={sidebarTheme}>
          <Sidebar activeId={conversationId} onNavigate={() => setMobileOpen(false)} />
        </ThemeProvider>
      </Drawer>
      <Box component="main" sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", height: "100vh" }}>
        {!isDesktop && (
          <AppBar position="static" elevation={0} sx={{ bgcolor: COLORS.black, color: "#fff" }}>
            <Toolbar>
              <IconButton edge="start" color="inherit" aria-label="Open conversations" onClick={() => setMobileOpen(true)} sx={{ mr: 1 }}>
                <MenuIcon />
              </IconButton>
              <BrandMark />
              <Typography variant="h6" sx={{ ml: 1 }}>
                {BRAND}
              </Typography>
            </Toolbar>
          </AppBar>
        )}
        <Outlet />
      </Box>
    </Box>
  );
}
