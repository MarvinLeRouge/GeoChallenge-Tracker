import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockFetchDetail = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());
const mockPost = vi.hoisted(() => vi.fn());
const mockPatch = vi.hoisted(() => vi.fn());
const mockRouterBack = vi.hoisted(() => vi.fn());
const mockToastSuccess = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

// Containers to hold refs created inside the async mock factory
const mockUcRef = vi.hoisted(() => ({ current: null as unknown }));
const mockLoadingRef = vi.hoisted(() => ({ current: null as unknown }));
const mockErrorRef = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("@/composables/useUserChallenge", async () => {
  const { ref } = await import("vue");
  const uc = ref<unknown>(null);
  const loadingDetail = ref(false);
  const errorDetail = ref<string | null>(null);
  mockUcRef.current = uc;
  mockLoadingRef.current = loadingDetail;
  mockErrorRef.current = errorDetail;
  return {
    useUserChallenge: () => ({
      uc,
      loadingDetail,
      errorDetail,
      safeDescription: ref("<p>description</p>"),
      fetchDetail: mockFetchDetail,
    }),
  };
});

vi.mock("@/api/http", () => ({
  default: { get: mockGet, post: mockPost, patch: mockPatch },
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { id: "uc1" } }),
  useRouter: () => ({ back: mockRouterBack }),
}));

vi.mock("vue-sonner", () => ({
  toast: { success: mockToastSuccess, error: mockToastError },
}));

vi.mock("@heroicons/vue/24/outline", () => {
  const s = { template: "<span />" };
  return {
    ArrowLeftIcon: s,
    CheckIcon: s,
    XMarkIcon: s,
    InformationCircleIcon: s,
  };
});

import Details from "@/pages/userChallenges/Details.vue";

const makeUc = (overrides = {}) =>
  ({
    id: "uc1",
    status: "pending",
    computed_status: null,
    effective_status: "pending",
    updated_at: "2023-06-01T00:00:00Z",
    created_at: "2023-01-01T00:00:00Z",
    manual_override: false,
    override_reason: null,
    notes: null,
    challenge: { id: "c1", name: "Test Challenge", description: "<p>desc</p>" },
    cache: { id: "ca1", GC: "GC12345" },
    ...overrides,
  }) as unknown;

const makeProgress = (percent = 50) => ({
  percent,
  tasks_done: 5,
  tasks_total: 10,
  checked_at: "2023-06-01T00:00:00Z",
});

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchDetail.mockResolvedValue(undefined);
  mockGet.mockResolvedValue({ data: { latest: { aggregate: null } } });
  mockPost.mockResolvedValue({ data: {} });
  mockPatch.mockResolvedValue({ data: {} });
  if (mockUcRef.current) mockUcRef.current.value = makeUc();
  if (mockLoadingRef.current) mockLoadingRef.current.value = false;
  if (mockErrorRef.current) mockErrorRef.current.value = null;
});

describe("Details", () => {
  it("calls fetchDetail and fetchProgress on mount", async () => {
    mount(Details);
    await flushPromises();
    expect(mockFetchDetail).toHaveBeenCalledOnce();
    expect(mockGet).toHaveBeenCalledWith("/my/challenges/uc1/progress");
  });

  it("shows progress bar when snapshot is available", async () => {
    mockGet.mockResolvedValue({
      data: { latest: { aggregate: makeProgress(60) } },
    });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.text()).toContain("60%");
  });

  it('shows "Pas encore commencé" when no progress snapshot', async () => {
    mockGet.mockResolvedValue({ data: { latest: { aggregate: null } } });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.text()).toContain("Pas encore commencé");
  });

  it("shows accept button when status is pending", async () => {
    mockUcRef.current.value = makeUc({ status: "pending" });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.find('[title="Accepter"]').exists()).toBe(true);
  });

  it("hides accept button when status is accepted", async () => {
    mockUcRef.current.value = makeUc({ status: "accepted" });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.find('[title="Accepter"]').exists()).toBe(false);
  });

  it("hides dismiss button when status is dismissed", async () => {
    mockUcRef.current.value = makeUc({ status: "dismissed" });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.find('[title="Refuser"]').exists()).toBe(false);
  });

  it("evaluateProgress calls api.post and shows success toast", async () => {
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("button.text-blue-600").trigger("click");
    await flushPromises();

    expect(mockPost).toHaveBeenCalledWith(
      "/my/challenges/uc1/progress/evaluate",
    );
    expect(mockToastSuccess).toHaveBeenCalledWith("Progression évaluée");
  });

  it("evaluateProgress shows error toast on failure", async () => {
    mockPost.mockRejectedValueOnce(new Error("evaluation failed"));
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("button.text-blue-600").trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur d'évaluation",
      expect.any(Object),
    );
  });

  it("patchStatus calls api.patch and shows success toast", async () => {
    mockUcRef.current.value = makeUc({ status: "pending" });
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find('[title="Accepter"]').trigger("click");
    await flushPromises();

    expect(mockPatch).toHaveBeenCalledWith("/my/challenges/uc1", {
      status: "accepted",
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Statut mis à jour");
  });

  it("patchStatus shows error toast on failure", async () => {
    mockPatch.mockRejectedValueOnce(new Error("patch failed"));
    mockUcRef.current.value = makeUc({ status: "pending" });
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find('[title="Accepter"]').trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur de mise à jour",
      expect.any(Object),
    );
  });

  it("saveNotes calls api.patch with notes and override_reason", async () => {
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("textarea").setValue("my note");
    await wrapper.find('input[type="text"]').setValue("manual reason");
    await wrapper.find("button.px-3").trigger("click");
    await flushPromises();

    expect(mockPatch).toHaveBeenCalledWith("/my/challenges/uc1", {
      notes: "my note",
      override_reason: "manual reason",
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Notes enregistrées");
  });

  it("saveNotes sends null for empty fields", async () => {
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("button.px-3").trigger("click");
    await flushPromises();

    expect(mockPatch).toHaveBeenCalledWith("/my/challenges/uc1", {
      notes: null,
      override_reason: null,
    });
  });

  it("saveNotes shows error toast on failure", async () => {
    mockPatch.mockRejectedValueOnce(new Error("save failed"));
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("button.px-3").trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur enregistrement",
      expect.any(Object),
    );
  });

  it("progressBarStyle returns green style at 100% progress", async () => {
    mockGet.mockResolvedValue({
      data: { latest: { aggregate: makeProgress(100) } },
    });
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.find(".h-full").attributes("style")).toContain(
      "rgb(34, 197, 94)",
    );
    expect(wrapper.find(".h-full").attributes("style")).not.toContain(
      "clip-path",
    );
  });

  it("fetchProgress sets snapshot to null when api throws", async () => {
    mockGet.mockRejectedValueOnce(new Error("progress fetch failed"));
    const wrapper = mount(Details);
    await flushPromises();
    expect(wrapper.text()).toContain("Pas encore commencé");
  });

  it("navigates back on Retour click", async () => {
    const wrapper = mount(Details);
    await flushPromises();

    await wrapper.find("button").trigger("click"); // first button is Retour
    expect(mockRouterBack).toHaveBeenCalled();
  });
});
