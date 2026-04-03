import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUserChallenge } from "@/composables/useUserChallenge";
import type { UserChallengeDetail } from "@/types/challenges";

const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({
  default: { get: mockGet },
}));

vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "API error" }),
  }),
}));

vi.mock("dompurify", () => ({
  default: {
    sanitize: vi.fn((html: string) =>
      html.replace(/<script[^>]*?>.*?<\/script>/gi, ""),
    ),
  },
}));

import DOMPurify from "dompurify";

const makeDetail = (description = "<p>Safe content</p>"): UserChallengeDetail =>
  ({
    challenge: { description },
  }) as unknown as UserChallengeDetail;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("safeDescription", () => {
  it("returns empty string when uc is null", () => {
    const { safeDescription } = useUserChallenge("uc-1");
    expect(safeDescription.value).toBe("");
  });

  it("sanitizes HTML from challenge description", () => {
    const { uc, safeDescription } = useUserChallenge("uc-1");
    uc.value = makeDetail("<p>Hello</p><script>alert(1)</script>");
    expect(safeDescription.value).toBe("<p>Hello</p>");
  });

  it("returns raw HTML when DOMPurify throws", () => {
    vi.mocked(DOMPurify.sanitize).mockImplementationOnce(() => {
      throw new Error("DOMPurify failure");
    });
    const { uc, safeDescription } = useUserChallenge("uc-1");
    uc.value = makeDetail("<b>raw</b>");
    expect(safeDescription.value).toBe("<b>raw</b>");
  });

  it("handles null description gracefully", () => {
    const { uc, safeDescription } = useUserChallenge("uc-1");
    uc.value = {
      challenge: { description: null },
    } as unknown as UserChallengeDetail;
    expect(safeDescription.value).toBe("");
  });
});

describe("fetchDetail", () => {
  it("sets uc on success", async () => {
    const detail = makeDetail();
    mockGet.mockResolvedValueOnce({ data: detail });
    const { uc, fetchDetail, loadingDetail } = useUserChallenge("uc-42");
    const promise = fetchDetail();
    expect(loadingDetail.value).toBe(true);
    await promise;
    expect(uc.value).toEqual(detail);
    expect(loadingDetail.value).toBe(false);
  });

  it("sets errorDetail on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("Network error"));
    const { errorDetail, fetchDetail } = useUserChallenge("uc-42");
    await fetchDetail();
    expect(errorDetail.value).toBe("API error");
  });

  it("resets loading to false after failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { loadingDetail, fetchDetail } = useUserChallenge("uc-42");
    await fetchDetail();
    expect(loadingDetail.value).toBe(false);
  });
});
