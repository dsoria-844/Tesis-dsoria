import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import ReinicioLab from "./ReinicioLab";

vi.mock("./api");

beforeEach(() => vi.resetAllMocks());

async function abrir(user: ReturnType<typeof userEvent.setup>) {
  render(<ReinicioLab />);
  await user.click(screen.getByRole("button", { name: "Confirmar" }));
  return {
    input: screen.getByLabelText("Confirmación"),
    boton: screen.getByRole("button", { name: "Borrar telemetría" }),
  };
}

describe("ReinicioLab", () => {
  it.each(["", "reiniciar", "Reiniciar", "REINICIA", "REINICIAR "])(
    "keeps the confirm button disabled for %j",
    async (texto) => {
      const user = userEvent.setup();
      const { input, boton } = await abrir(user);
      if (texto) await user.type(input, texto);
      expect(boton).toBeDisabled();
    },
  );

  it("enables the button on exact REINICIAR and calls the API with it", async () => {
    vi.mocked(api.reiniciarLaboratorio).mockResolvedValue({
      eliminados: { sesiones: 1500, alertas_seguridad: 2 },
    } as never);
    const user = userEvent.setup();
    const { input, boton } = await abrir(user);
    await user.type(input, "REINICIAR");
    expect(boton).toBeEnabled();
    await user.click(boton);
    expect(api.reiniciarLaboratorio).toHaveBeenCalledTimes(1);
    expect(api.reiniciarLaboratorio).toHaveBeenCalledWith("REINICIAR");
    expect(await screen.findByRole("status")).toHaveTextContent("1.500 sesiones · 2 alertas");
  });

  it("shows the API error and keeps the dialog open on failure", async () => {
    vi.mocked(api.reiniciarLaboratorio).mockRejectedValue(new Error("Sin permiso"));
    const user = userEvent.setup();
    const { input, boton } = await abrir(user);
    await user.type(input, "REINICIAR");
    await user.click(boton);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin permiso");
  });
});
