import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { PublicOnly, RequireAuth } from "../auth/RequireAuth";
import { calls, errorBody, jsonResponse, stubFetch } from "../test/helpers";
import { EmptyChatPage } from "./ConversationPages";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";

const user = { id: "1", email: "ada@example.com", display_name: "Ada", tenant_id: "northwind", role: "planner", created_at: "" };
const tenants = [
  { id: "northwind", name: "Northwind Grocers", industry: "Grocery retail" },
  { id: "harbor", name: "Harbor Freight Lines", industry: "Regional logistics" },
];
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

  it("labels itself as a demo and never presents itself under another company's brand", async () => {
    stubFetch({ "POST /auth/refresh": noSession });
    renderApp("/login");
    expect(await screen.findByText("BYond Chat")).toBeInTheDocument();
    expect(screen.getByText(/demo project built for a technical assessment/i)).toBeInTheDocument();
    expect(screen.queryByText(/chatgpt/i)).not.toBeInTheDocument();
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

  it("lets you pick a demo company and sends it with the registration", async () => {
    const mock = stubFetch({
      "POST /auth/refresh": noSession,
      "GET /tenants": () => jsonResponse(200, tenants),
      "POST /auth/register": () => jsonResponse(201, user),
      "POST /auth/login": () => jsonResponse(200, { ...session, user: { ...user, tenant_id: "harbor" } }),
    });
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText(/display name/i), "Ada");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "a-long-enough-pw");
    await userEvent.click(await screen.findByLabelText(/demo company/i));
    await userEvent.click(await screen.findByRole("option", { name: /Harbor Freight Lines/ }));
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(calls(mock, "POST /auth/register")).toHaveLength(1));
    expect(JSON.parse(calls(mock, "POST /auth/register")[0][1]!.body as string).tenant_id).toBe("harbor");
  });

  it("still lets you register when the company list cannot be loaded (server defaults it)", async () => {
    const mock = stubFetch({
      "POST /auth/refresh": noSession,
      "GET /tenants": () => jsonResponse(500, errorBody("internal_error", "boom")),
      "POST /auth/register": () => jsonResponse(201, user),
      "POST /auth/login": () => jsonResponse(200, session),
    });
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText(/display name/i), "Ada");
    await userEvent.type(screen.getByLabelText(/email/i), "ada@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "a-long-enough-pw");
    expect(screen.queryByLabelText(/demo company/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(calls(mock, "POST /auth/register")).toHaveLength(1));
    expect(JSON.parse(calls(mock, "POST /auth/register")[0][1]!.body as string)).not.toHaveProperty("tenant_id");
  });
});
