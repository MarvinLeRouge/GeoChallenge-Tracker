import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockFetchDetail = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());
const mockPost = vi.hoisted(() => vi.fn());
const mockPut = vi.hoisted(() => vi.fn());
const mockRouterBack = vi.hoisted(() => vi.fn());
const mockToastSuccess = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

const mockUcRef = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("@/composables/useUserChallenge", async () => {
  const { ref } = await import("vue");
  const uc = ref<unknown>({
    challenge: { name: "Test" },
    cache: { GC: "GC1" },
  });
  mockUcRef.current = uc;
  return {
    useUserChallenge: () => ({
      uc,
      safeDescription: ref("<p>desc</p>"),
      fetchDetail: mockFetchDetail,
    }),
  };
});

vi.mock("vuedraggable", () => ({
  default: {
    name: "Draggable",
    props: ["modelValue", "itemKey", "handle"],
    emits: ["update:modelValue"],
    template: `<div><slot v-for="(item, i) in modelValue" :key="i" name="item" :element="item" :index="i" /></div>`,
  },
}));

vi.mock("@/api/http", () => ({
  default: { get: mockGet, post: mockPost, put: mockPut },
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
    PlusIcon: s,
    TrashIcon: s,
    Bars3Icon: s,
    ClipboardDocumentCheckIcon: s,
    ArrowUpOnSquareIcon: s,
  };
});

import Tasks from "@/pages/userChallenges/Tasks.vue";

const makeServerTask = (overrides = {}) => ({
  id: "task1",
  title: "Task One",
  expression: { kind: "size_in", sizes: [{ code: "L" }] },
  constraints: { min_count: 2 },
  status: "todo",
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchDetail.mockResolvedValue(undefined);
  mockGet.mockResolvedValue({ data: { tasks: [] } });
  mockPost.mockResolvedValue({ data: {} });
  mockPut.mockResolvedValue({ data: {} });
});

describe("Tasks", () => {
  it("calls fetchDetail and fetchTasks on mount", async () => {
    mount(Tasks);
    await flushPromises();
    expect(mockFetchDetail).toHaveBeenCalledOnce();
    expect(mockGet).toHaveBeenCalledWith("/my/challenges/uc1/tasks");
  });

  it("maps server tasks to UI tasks with expression_json and min_count", async () => {
    const serverTask = makeServerTask();
    mockGet.mockResolvedValue({ data: { tasks: [serverTask] } });
    const wrapper = mount(Tasks);
    await flushPromises();
    // Rendered textarea should contain JSON of the expression
    const textarea = wrapper.find("textarea");
    expect(textarea.element.value).toContain("size_in");
  });

  it("sets min_count from constraints", async () => {
    mockGet.mockResolvedValue({
      data: { tasks: [makeServerTask({ constraints: { min_count: 5 } })] },
    });
    const wrapper = mount(Tasks);
    await flushPromises();
    const numberInput = wrapper.find('input[type="number"]');
    expect(numberInput.element.value).toBe("5");
  });

  it("sets null min_count when constraints.min_count is not a number", async () => {
    mockGet.mockResolvedValue({
      data: { tasks: [makeServerTask({ constraints: {} })] },
    });
    const wrapper = mount(Tasks);
    await flushPromises();
    const numberInput = wrapper.find('input[type="number"]');
    expect(numberInput.element.value).toBe("");
  });

  it("addTask appends a new task with defaults", async () => {
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper.find('[title="Ajouter une tâche"]').trigger("click");
    await flushPromises();

    const textInputs = wrapper.findAll('input[type="text"]');
    expect(textInputs.some((i) => i.element.value === "Nouvelle tâche")).toBe(
      true,
    );
  });

  it("removeTask removes the task at the given index", async () => {
    mockGet.mockResolvedValue({ data: { tasks: [makeServerTask()] } });
    const wrapper = mount(Tasks);
    await flushPromises();

    expect(wrapper.find('[title="Supprimer"]').exists()).toBe(true);
    await wrapper.find('[title="Supprimer"]').trigger("click");
    await flushPromises();

    expect(wrapper.find('[title="Supprimer"]').exists()).toBe(false);
  });

  it("validateAll calls api.post and shows success toast", async () => {
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Valider la liste (sans enregistrer)"]')
      .trigger("click");
    await flushPromises();

    expect(mockPost).toHaveBeenCalledWith(
      "/my/challenges/uc1/tasks/validate",
      expect.objectContaining({ tasks: expect.any(Array) }),
    );
    expect(mockToastSuccess).toHaveBeenCalledWith("Validation réussie");
  });

  it("validateAll shows error toast on failure", async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: "invalid expression" } },
    });
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Valider la liste (sans enregistrer)"]')
      .trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur de validation",
      expect.any(Object),
    );
  });

  it("saveAll calls api.put and shows success toast", async () => {
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Enregistrer toutes les tâches"]')
      .trigger("click");
    await flushPromises();

    expect(mockPut).toHaveBeenCalledWith(
      "/my/challenges/uc1/tasks",
      expect.objectContaining({ tasks: expect.any(Array) }),
    );
    expect(mockToastSuccess).toHaveBeenCalledWith("Tâches enregistrées");
  });

  it("saveAll updates local tasks when backend returns tasks", async () => {
    const updatedTask = makeServerTask({ title: "Updated Task" });
    mockPut.mockResolvedValue({ data: { tasks: [updatedTask] } });
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Enregistrer toutes les tâches"]')
      .trigger("click");
    await flushPromises();

    const textInput = wrapper.find('input[type="text"]');
    expect(textInput.element.value).toBe("Updated Task");
  });

  it("saveAll shows error toast on failure", async () => {
    mockPut.mockRejectedValueOnce(new Error("network error"));
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Enregistrer toutes les tâches"]')
      .trigger("click");
    await flushPromises();

    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur enregistrement",
      expect.any(Object),
    );
  });

  it("buildPayload falls back to null for invalid JSON in expression_json", async () => {
    mockGet.mockResolvedValue({
      data: { tasks: [makeServerTask({ expression: null })] },
    });
    const wrapper = mount(Tasks);
    await flushPromises();

    // Set invalid JSON in the textarea
    await wrapper.find("textarea").setValue("{ invalid json }");
    await wrapper
      .find('[title="Valider la liste (sans enregistrer)"]')
      .trigger("click");
    await flushPromises();

    // Should still call api.post (with expression: null due to parse failure)
    expect(mockPost).toHaveBeenCalledWith(
      "/my/challenges/uc1/tasks/validate",
      expect.objectContaining({
        tasks: expect.arrayContaining([
          expect.objectContaining({ expression: null }),
        ]),
      }),
    );
  });

  it("fetchTasks sets error message for non-Error rejection", async () => {
    mockGet.mockRejectedValueOnce("plain string error");
    const wrapper = mount(Tasks);
    await flushPromises();
    expect(wrapper.text()).toContain("Erreur de chargement");
  });

  it("saveAll with null constraints in returned tasks falls back to empty object", async () => {
    const updatedTask = {
      id: "task1",
      title: "T",
      expression: null,
      constraints: null,
      status: "todo",
    };
    mockPut.mockResolvedValue({ data: { tasks: [updatedTask] } });
    const wrapper = mount(Tasks);
    await flushPromises();

    await wrapper
      .find('[title="Enregistrer toutes les tâches"]')
      .trigger("click");
    await flushPromises();

    expect(mockToastSuccess).toHaveBeenCalledWith("Tâches enregistrées");
  });

  it("navigates back on Retour click", async () => {
    const wrapper = mount(Tasks);
    await flushPromises();

    const retourBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("Retour"));
    await retourBtn!.trigger("click");
    expect(mockRouterBack).toHaveBeenCalled();
  });
});
