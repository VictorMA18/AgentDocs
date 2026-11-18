import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCEPTED_EXTENSIONS, fileType, FileTypeBadge } from "./file-type";

describe("fileType", () => {
  it("reconoce cada extensión permitida por su familia y su etiqueta, sin distinguir mayúsculas", () => {
    expect(fileType("manual.PDF")).toMatchObject({ family: "pdf", label: "PDF" });
    expect(fileType("taskflow.md")).toMatchObject({ family: "text", label: "MD" });
    expect(fileType("main.py")).toMatchObject({ family: "code", label: "PY" });
    expect(fileType("config.yml")).toMatchObject({ family: "data", label: "YAML" });
    expect(fileType("datos.json")).toMatchObject({ family: "data", label: "JSON" });
  });

  it("lo desconocido queda como «otro» y nunca sin etiqueta", () => {
    expect(fileType("raro.xyz")).toMatchObject({ family: "other", label: "XYZ" });
    expect(fileType("sin_extension")).toMatchObject({ family: "other", label: "ARCHIVO" });
    expect(fileType(".env")).toMatchObject({ family: "other", label: "ARCHIVO" });
  });

  it("las extensiones aceptadas coinciden con las de la API", () => {
    expect(ACCEPTED_EXTENSIONS).toEqual([".md", ".txt", ".pdf", ".py", ".js", ".ts", ".java", ".json", ".yaml", ".yml"]);
  });

  it("la insignia escribe la etiqueta (el tipo no va solo en el color)", () => {
    const { container } = render(<FileTypeBadge name="manual.pdf" />);
    const badge = container.querySelector(".file-badge")!;
    expect(badge).toHaveTextContent("PDF");
    expect(badge).toHaveAttribute("data-file", "pdf");
  });
});
