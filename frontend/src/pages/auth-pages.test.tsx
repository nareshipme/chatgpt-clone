import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { PublicOnly, RequireAuth } from "../auth/RequireAuth";
import { errorBody, jsonResponse, stubFetch } from "../test/helpers";
import { EmptyChatPage } from "./ConversationPages";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";

const user = { id: "1", email: "ada@example.com", display_name: "Ada", created_at: "" };
const session = { access_token: "tok", token_type: "bearer", user };
const noSession = () => jsonResponse(401, errorBody("invalid_refresh_token", "none"));

function renderApp(initial: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
    <MemoryRouter initialEntries={[initial]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
          <Route path="/register" element={<PublicOnly><RegisterPage /></PublicOnly>} />
          <Route path="/" element={<RequireAuth><EmptyChatPage /></RequireAuth>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
    </QueryClientProvider>,
  );
}

// client.ts holds module state (token, in-flight refresh); a fresh module per test keeps tests independent.
beforeEach(() => vi.resetModules());

describe("auth pages", () => {
  it("redirects an anonymous visitor from / to the login page", async () => {
    stubFetch({ "POST /auth/refresh": noSession });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
  });

  it("restores a session from the refresh cookie and shows the home page", async () => {
    stubFetch({ "POST /auth/refresh": () => jsonResponse(200, session) });
    renderApp("/");
    expect(await screen.findByText(/hello, ada/i)).toBeInTheDocument();
  });

  it("keeps the sign-in button disabled until both fields are filled", async () => {
    stubFetch({ "POST /auth/refresh": noSession });
    renderApp("/login");
    const button = await screen.findByRole("button", { name: /sign in/i });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "pw");
    expect(button).toBeEnabled();
  });

  it("shows the server's message when login fails", async () => {
    stubFetch({
      "POST /auth/refresh": noSession,
      "POST /auth/login": () => jsonResponse(401, errorBody("invalid_credentials", "Invalid email or password")),
    });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });

  it("signs in and lands on the home page", async () => {
    stubFetch({
      "POST /auth/refresh": noSession,
      "POST /auth/login": () => jsonResponse(200, session),
    });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "right-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/hello, ada/i)).toBeInTheDocument();
  });

  it("maps a server validation error onto the password field on register", async () => {
    stubFetch({
      "POST /auth/refresh": noSession,
      "POST /auth/register": () =>
        jsonResponse(422, errorBody("validation_error", "Invalid request", [{ field: "password", message: "String should have at least 10 characters" }])),
    });
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText(/display name/i), "Ada");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "short");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/at least 10 characters/i)).toBeInTheDocument();
  });

  it("shows email_taken on the email field", async () => {
    stubFetch({
      "POST /auth/refresh": noSession,
      "POST /auth/register": () => jsonResponse(409, errorBody("email_taken", "An account with this email already exists")),
    });
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText(/display name/i), "Ada");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "a-long-enough-pw");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/already exists/i)).toBeInTheDocument());
  });
});
