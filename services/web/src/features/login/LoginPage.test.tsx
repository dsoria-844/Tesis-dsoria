import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as authApi from "../../app/auth/api";
import { session } from "../../shared/api/session";
import * as loginApi from "./api";
import Login from "./LoginPage";

vi.mock("./api");
vi.mock("../../app/auth/api");

beforeEach(() => vi.resetAllMocks());

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Correo"), "auditor@salta-test.local");
  await user.type(screen.getByLabelText("Contraseña"), "s3cret");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("LoginPage", () => {
  it("submits the entered credentials, stores the token and reports the user", async () => {
    const me = { id: "1", correo: "auditor@salta-test.local", rol: "AUDITOR" as const };
    vi.mocked(loginApi.iniciarSesion).mockResolvedValue({ access_token: "jwt", token_type: "bearer" } as never);
    vi.mocked(authApi.obtenerMe).mockResolvedValue(me);
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<Login onLogin={onLogin} />);
    await fill(user);
    expect(loginApi.iniciarSesion).toHaveBeenCalledWith("auditor@salta-test.local", "s3cret");
    expect(session.token).toBe("jwt");
    expect(onLogin).toHaveBeenCalledWith(me);
  });

  it("shows the error message on failure and does not log in", async () => {
    vi.mocked(loginApi.iniciarSesion).mockRejectedValue(new Error("Credenciales inválidas"));
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<Login onLogin={onLogin} />);
    await fill(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Credenciales inválidas");
    expect(onLogin).not.toHaveBeenCalled();
    expect(session.token).toBeNull();
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled();
  });
});
