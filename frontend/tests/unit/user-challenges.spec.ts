import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUserChallenges } from "@/composables/useUserChallenges";

const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({
  default: { get: mockGet },
}));

vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "API error" }),
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

const makeResponse = (overrides = {}) => ({
  data: {
    items: [{ id: "1" }, { id: "2" }],
    nb_items: 2,
    nb_pages: 1,
    ...overrides,
  },
});

describe("fetchChallenges", () => {
  it("populates challenges on success", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const { challenges, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    expect(challenges.value).toHaveLength(2);
  });

  it("sets loading to true during fetch, false after", async () => {
    mockGet.mockImplementationOnce(async () => {
      return makeResponse();
    });
    const { loading, fetchChallenges } = useUserChallenges();
    const promise = fetchChallenges();
    expect(loading.value).toBe(true);
    await promise;
    expect(loading.value).toBe(false);
  });

  it("sets nbItems and nbPages from response", async () => {
    mockGet.mockResolvedValueOnce(makeResponse({ nb_items: 42, nb_pages: 3 }));
    const { nbItems, nbPages, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    expect(nbItems.value).toBe(42);
    expect(nbPages.value).toBe(3);
  });

  it("calculates nbPages when nb_pages is absent", async () => {
    mockGet.mockResolvedValueOnce({
      data: { items: [], nb_items: 45, nb_pages: undefined },
    });
    const { nbPages, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    // ceil(45 / 20) = 3
    expect(nbPages.value).toBe(3);
  });

  it("falls back to items.length when nb_items is absent", async () => {
    mockGet.mockResolvedValueOnce({
      data: { items: [{ id: "1" }, { id: "2" }, { id: "3" }] },
    });
    const { nbItems, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    expect(nbItems.value).toBe(3);
  });

  it('does not add status param when filterStatus is "all"', async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    await useUserChallenges().fetchChallenges("all");
    const params = mockGet.mock.calls[0][1].params;
    expect(params.status).toBeUndefined();
  });

  it("does not add status param when filterStatus is undefined", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    await useUserChallenges().fetchChallenges(undefined);
    const params = mockGet.mock.calls[0][1].params;
    expect(params.status).toBeUndefined();
  });

  it("adds status param for a specific filter", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    await useUserChallenges().fetchChallenges("active");
    const params = mockGet.mock.calls[0][1].params;
    expect(params.status).toBe("active");
  });

  it("sets error and resets loading on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("Network error"));
    const { error, loading, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    expect(error.value).toBe("API error");
    expect(loading.value).toBe(false);
  });

  it("clears previous error on new fetch", async () => {
    mockGet.mockRejectedValueOnce(new Error("first error"));
    const { error, fetchChallenges } = useUserChallenges();
    await fetchChallenges();
    expect(error.value).toBe("API error");

    mockGet.mockResolvedValueOnce(makeResponse());
    await fetchChallenges();
    expect(error.value).toBeNull();
  });
});
