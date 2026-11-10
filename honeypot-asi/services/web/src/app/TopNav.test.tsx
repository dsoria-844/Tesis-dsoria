import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Rol } from "./auth/types";
import TopNav from "./TopNav";

function renderNav(rol: Rol, path = "/") {
  render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <TopNav me={{ id: "1", correo: "x@salta-test.local", rol }} logout={vi.fn()} />
    </MemoryRouter>,
  );
  const nav = screen.getByRole("navigation", { name: "Secciones" });
  return (href: string) => nav.querySelector(`a[href="${href}"]`);
}

describe("TopNav role gating", () => {
  it("ADMIN_INFRA sees Laboratorio and Usuarios, not Sesiones/Alertas", () => {
    const link = renderNav("ADMIN_INFRA");
    expect(link("/laboratorio")).toHaveTextContent("Laboratorio");
    expect(link("/usuarios")).toHaveTextContent("Usuarios");
    expect(link("/sesiones")).toBeNull();
    expect(link("/alertas")).toBeNull();
  });

  it.each<Rol>(["AUDITOR", "RESPONSABLE_SEGURIDAD"])(
    "%s sees Sesiones and Alertas, not Laboratorio/Usuarios",
    (rol) => {
      const link = renderNav(rol);
      expect(link("/sesiones")).toHaveTextContent("Sesiones");
      expect(link("/alertas")).toHaveTextContent("Alertas");
      expect(link("/laboratorio")).toBeNull();
      expect(link("/usuarios")).toBeNull();
    },
  );

  it.each<Rol>(["ADMIN_INFRA", "AUDITOR", "RESPONSABLE_SEGURIDAD"])("%s always sees Resumen and Actividad", (rol) => {
    const link = renderNav(rol);
    expect(link("/")).toHaveTextContent("Resumen");
    expect(link("/actividad")).toHaveTextContent("Actividad");
  });

  it("marks Actividad active on the IP detail page", () => {
    const link = renderNav("AUDITOR", "/ip/1.2.3.4");
    expect(link("/actividad")).toHaveClass("active");
  });
});
