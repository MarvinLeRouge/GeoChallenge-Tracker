import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockPatch = vi.hoisted(() => vi.fn());
const mockRouterPush = vi.hoisted(() => vi.fn());
const mockRouterReplace = vi.hoisted(() => vi.fn());
const mockFetchList = vi.hoisted(() => vi.fn());
const mockUpdateItem = vi.hoisted(() => vi.fn());
const mockHandleApiError = vi.hoisted(() =>
  vi.fn().mockReturnValue({ message: "error msg" }),
);
const mockToastSuccess = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

const mockStore = vi.hoisted(() => ({
  error: null as string | null,
  loading: false,
  items: [] as unknown[],
  page: 1,
  nbPages: 3,
  fetchList: mockFetchList,
  updateItem: mockUpdateItem,
}));

vi.mock("@/api/http", () => ({ default: { patch: mockPatch } }));
vi.mock("@/store/challenges", () => ({ useChallengesStore: () => mockStore }));
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: mockRouterPush, replace: mockRouterReplace }),
  useRoute: () => ({ query: {} }),
}));
vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({ handleApiError: mockHandleApiError }),
}));
vi.mock("vue-sonner", () => ({
  toast: { success: mockToastSuccess, error: mockToastError },
}));
vi.mock("@heroicons/vue/24/outline", () => {
  const s = { template: "<span />" };
  return {
    CheckCircleIcon: s,
    XCircleIcon: s,
    ClockIcon: s,
    TrophyIcon: s,
    AdjustmentsHorizontalIcon: s,
  };
});

// Stub renders buttons that trigger every event — no findComponent needed
vi.mock("@/components/userChallenges/UserChallengeCard.vue", () => ({
  default: {
    name: "UserChallengeCard",
    props: ["challenge"],
    emits: ["details", "accept", "dismiss", "reset", "tasks"],
    template: `
      <div class="uc-card">
        <button class="emit-details" @click="$emit('details', challenge)">Details</button>
        <button class="emit-accept"  @click="$emit('accept',  challenge)">Accept</button>
        <button class="emit-dismiss" @click="$emit('dismiss', challenge)">Dismiss</button>
        <button class="emit-reset"   @click="$emit('reset',   challenge)">Reset</button>
        <button class="emit-tasks"   @click="$emit('tasks',   challenge)">Tasks</button>
      </div>
    `,
  },
}));

import List from "@/pages/userChallenges/List.vue";
import type { UserChallengeListItem } from "@/types/challenges";

const makeChallenge = (id = "uc1"): UserChallengeListItem =>
  ({
    id,
    status: "pending",
    computed_status: null,
    effective_status: "pending",
    progress: null,
    updated_at: null,
    challenge: { id: "c1", name: "Test Challenge" },
    cache: { id: "ca1", GC: "GC1" },
  }) as unknown as UserChallengeListItem;

beforeEach(() => {
  vi.clearAllMocks();
  mockStore.error = null;
  mockStore.loading = false;
  mockStore.items = [];
  mockStore.page = 1;
  mockStore.nbPages = 3;
  mockFetchList.mockResolvedValue(undefined);
  mockPatch.mockResolvedValue({ data: {} });
});

describe("List", () => {
  it("calls fetchList on mount", async () => {
    mount(List);
    await flushPromises();
    expect(mockFetchList).toHaveBeenCalledWith("all");
  });

  it("setFilter changes filterStatus and resets page to 1", async () => {
    mockStore.page = 3;
    const wrapper = mount(List);
    await flushPromises();

    const acceptedBtn = wrapper
      .findAll("button")
      .find((b) => b.attributes("title") === "Acceptés");
    await acceptedBtn!.trigger("click");
    await flushPromises();

    expect(mockStore.page).toBe(1);
    expect(mockFetchList).toHaveBeenCalledWith("accepted");
  });

  it("prevPage decrements page", async () => {
    mockStore.page = 2;
    const wrapper = mount(List);
    await flushPromises();

    const prev = wrapper
      .findAll("button")
      .find((b) => b.text() === "Précédent");
    await prev!.trigger("click");

    expect(mockStore.page).toBe(1);
  });

  it("nextPage increments page", async () => {
    mockStore.page = 1;
    const wrapper = mount(List);
    await flushPromises();

    const next = wrapper.findAll("button").find((b) => b.text() === "Suivant");
    await next!.trigger("click");

    expect(mockStore.page).toBe(2);
  });

  it("showDetails navigates to challenge details page", async () => {
    const ch = makeChallenge("uc42");
    mockStore.items = [ch];
    const wrapper = mount(List);
    await flushPromises();

    await wrapper.find(".emit-details").trigger("click");
    await flushPromises();

    expect(mockRouterPush).toHaveBeenCalledWith({
      name: "userChallengeDetails",
      params: { id: "uc42" },
    });
  });

  it("patchChallenge calls API and updates store on success", async () => {
    const ch = makeChallenge("uc1");
    mockStore.items = [ch];
    const wrapper = mount(List);
    await flushPromises();

    await wrapper.find(".emit-accept").trigger("click");
    await flushPromises();

    expect(mockPatch).toHaveBeenCalledWith("/my/challenges/uc1", {
      status: "accepted",
    });
    expect(mockUpdateItem).toHaveBeenCalledWith("uc1", { status: "accepted" });
    expect(mockToastSuccess).toHaveBeenCalled();
  });

  it("patchChallenge shows error toast on failure", async () => {
    mockPatch.mockRejectedValueOnce(new Error("fail"));
    const ch = makeChallenge();
    mockStore.items = [ch];
    const wrapper = mount(List);
    await flushPromises();

    await wrapper.find(".emit-dismiss").trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalled();
  });

  it("resetChallenge patches with pending status", async () => {
    const ch = makeChallenge("uc5");
    mockStore.items = [ch];
    const wrapper = mount(List);
    await flushPromises();

    await wrapper.find(".emit-reset").trigger("click");
    await flushPromises();

    expect(mockPatch).toHaveBeenCalledWith("/my/challenges/uc5", {
      status: "pending",
    });
    expect(mockToastSuccess).toHaveBeenCalled();
  });

  it("prevPage does not decrement when already at page 1", async () => {
    // Component always resets page to 1 from route.query (which is empty)
    const wrapper = mount(List);
    await flushPromises();

    const prev = wrapper
      .findAll("button")
      .find((b) => b.text() === "Précédent");
    await prev!.trigger("click");

    expect(mockStore.page).toBe(1);
  });

  it("nextPage does not increment when already at last page", async () => {
    mockStore.nbPages = 1; // with page=1 (reset by component), canNext=false
    const wrapper = mount(List);
    await flushPromises();

    const next = wrapper.findAll("button").find((b) => b.text() === "Suivant");
    await next!.trigger("click");

    expect(mockStore.page).toBe(1);
  });

  it("manageTasks navigates to tasks page", async () => {
    const ch = makeChallenge("uc7");
    mockStore.items = [ch];
    const wrapper = mount(List);
    await flushPromises();

    await wrapper.find(".emit-tasks").trigger("click");
    await flushPromises();

    expect(mockRouterPush).toHaveBeenCalledWith({
      name: "userChallengeTasks",
      params: { id: "uc7" },
    });
  });
});
