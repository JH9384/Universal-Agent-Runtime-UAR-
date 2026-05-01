import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders main UI shell", () => {
    render(<App />);
    expect(screen.getByText(/UAR/i)).toBeInTheDocument();
    expect(screen.getByText(/Objects/i)).toBeInTheDocument();
  });
});
