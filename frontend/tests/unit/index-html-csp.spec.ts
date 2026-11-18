// @vitest-environment node
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (path: string) =>
  readFileSync(new URL(`../../${path}`, import.meta.url), "utf8");

const inlineScripts = [
  ...read("index.html").matchAll(/<script>([\s\S]*?)<\/script>/g),
].map((match) => match[1]);

const scriptSrc =
  read("nginx-security-headers.conf").match(
    /Content-Security-Policy "[^"]*script-src ([^;"]+)/,
  )?.[1] ?? "";

describe("index.html inline scripts vs the prod CSP", () => {
  it("has the dark-theme script to check", () => {
    expect(inlineScripts).toHaveLength(1);
  });

  it.each(inlineScripts)("allows inline script %# by its sha256", (script) => {
    const hash = createHash("sha256").update(script).digest("base64");

    expect(scriptSrc.split(" ")).toContain(`'sha256-${hash}'`);
  });
});
