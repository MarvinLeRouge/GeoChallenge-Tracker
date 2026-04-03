import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "API error" }),
  }),
}));

import { useChallengesStore } from "@/store/challenges";
import type { UserChallengeListItem } from "@/types/challenges";

const makeItem = (id: string): UserChallengeListItem =>
  ({ id, status: "active" }) as unknown as UserChallengeListItem;

const makeResponse = (overrides = {}) => ({
  data: {
    items: [makeItem("1"), makeItem("2")],
    nb_items: 2,
    nb_pages: 1,
    ...overrides,
  },
});

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe("fetchList", () => {
  it("populates items on success", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();

    await store.fetchList();

    expect(store.items).toHaveLength(2);
  });

  it("sets loading true during fetch, false after", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();

    const promise = store.fetchList();
    expect(store.loading).toBe(true);
    await promise;
    expect(store.loading).toBe(false);
  });

  it('does not add status param when filterStatus is "all"', async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();

    await store.fetchList("all");

    const params = mockGet.mock.calls[0][1].params;
    expect(params.status).toBeUndefined();
  });

  it("adds status param for a specific filter", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();

    await store.fetchList("active");

    const params = mockGet.mock.calls[0][1].params;
    expect(params.status).toBe("active");
  });

  it("calculates nbPages when not provided", async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [], nb_items: 45 } });
    const store = useChallengesStore();

    await store.fetchList();

    expect(store.nbPages).toBe(3); // ceil(45/20)
  });

  it("sets error and resets loading on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const store = useChallengesStore();

    await store.fetchList();

    expect(store.error).toBe("API error");
    expect(store.loading).toBe(false);
  });
});

describe("updateItem", () => {
  it("patches the matching item in place", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();
    await store.fetchList();

    store.updateItem("1", {
      status: "completed",
    } as Partial<UserChallengeListItem>);

    expect(store.items[0].status).toBe("completed");
  });

  it("is a no-op when the id does not exist", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    const store = useChallengesStore();
    await store.fetchList();

    expect(() => store.updateItem("nonexistent", {})).not.toThrow();
    expect(store.items).toHaveLength(2);
  });
});
