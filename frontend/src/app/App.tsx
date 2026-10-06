import { CssBaseline, ThemeProvider } from "@mui/material";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import StatusPage from "../pages/StatusPage";
import { theme } from "./theme";

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/status" element={<StatusPage />} />
          <Route path="*" element={<StatusPage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
