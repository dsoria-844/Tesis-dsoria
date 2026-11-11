import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import ThemeToggle from "./ThemeToggle";
import { fijarTema, temaActual } from "./tema";

describe("tema", () => {
  it("defaults to light when <html> has no data-theme", () => {
    expect(temaActual()).toBe("light");
  });

  it("fijarTema applies data-theme and persists hp_tema", () => {
    fijarTema("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("hp_tema")).toBe("dark");
    expect(temaActual()).toBe("dark");
  });

  it("ThemeToggle flips the theme back and forth", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button", { name: "Activar tema oscuro" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("hp_tema")).toBe("dark");
    await user.click(screen.getByRole("button", { name: "Activar tema claro" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("hp_tema")).toBe("light");
  });
});
