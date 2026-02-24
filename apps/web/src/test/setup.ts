import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement scrollIntoView — stub it for component tests.
Element.prototype.scrollIntoView = () => {};
