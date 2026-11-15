import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderLogo } from "./provider-logo";

describe("ProviderLogo", () => {
  it("dibuja el logo de cada proveedor conocido, oculto al lector de pantalla (el nombre va al lado)", () => {
    render(
      <>
        <ProviderLogo provider="claude" />
        <ProviderLogo provider="gemini" />
      </>,
    );
    for (const id of ["claude", "gemini"]) {
      expect(screen.getByTestId(`logo-${id}`)).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("no dibuja nada para un proveedor sin logo", () => {
    const { container } = render(<ProviderLogo provider="otro" />);
    expect(container).toBeEmptyDOMElement();
  });
});
